import asyncio
import threading
from datetime import datetime, time
import pandas as pd
import math

from app.utils.logging import get_logger
from app.config import settings
from fyers_apiv3.FyersWebsocket import data_ws
from app.slack import slack
from app.fyers.oms.nifty_tf_oms import Nifty_OMS
from app.nifty_tf.market_data import LibertyMarketData
from app.nifty_tf.trigger import LibertyTrigger

class LibertyBreakout:
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertyBreakout")
        self.db = db
        self.fyers = fyers
        self.symbol = settings.trade.NIFTY_SYMBOL
        self.LibertyMarketData = LibertyMarketData(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)

        # thresholds (set via monitor_breakouts)
        self.swh_price = None
        self.swl_price = None

        # breakout state (updated on first breach)
        self.state = {
            "triggered": False,
            "direction": None,
            "price": None
        }

        # Internal control
        self._monitor_started = False
        self._done_event: asyncio.Event = None

        # Fyers connection details
        self.access_token = settings.fyers.FYERS_ACCESS_TOKEN
        self.futures_symbol = self.symbol

        # Trail & SL Settings
        self.sl_percent = settings.trade.NIFTY_SL_PCT # 0.3 %
        self.sl_lock = threading.Lock()
        self.sl_state = {
            "active": False,
            "side": None,
            "symbol": None,
            "sl_price": 0,
            "exit_executed": False
        }

        # OMS
        self.place_order = Nifty_OMS(db, fyers)
        

    async def monitor_breakouts(self, *, swh_price=None, swl_price=None):
        """
        Register new thresholds. On first call only, spins up a single
        background WebSocket thread that watches both SWH and SWL.
        Subsequent calls just update the thresholds immediately.
        """
        if swh_price is not None:
            self.swh_price = swh_price
            self.logger.info(f"Registered SWH → {self.swh_price}")
        if swl_price is not None:
            self.swl_price = swl_price
            self.logger.info(f"Registered SWL → {self.swl_price}")

        if not self._monitor_started:
            self._monitor_started = True
            self._done_event = asyncio.Event()
            # Launch the watcher on its own asyncio task
            asyncio.create_task(self._watch_for_breakout())
            asyncio.create_task(self.db.update_status(status='Awaiting Breakout'))

    async def wait_for_breakout(self):
        """
        Await the first threshold breach. Must have called monitor_breakouts()
        at least once beforehand.
        """
        if not self._done_event:
            raise RuntimeError("Breakout watcher not started")
        self.logger.info("Awaiting breakout event …")
        await self._done_event.wait()
        self.logger.info("Breakout event received")
        return self.state  # so caller can inspect direction & price

    async def _watch_for_breakout(self):
        """
        Internally fire a thread that connects to Fyers WebSocket and
        signals the asyncio Event on the first breach.
        """
        loop = asyncio.get_event_loop()
        thread = threading.Thread(
            target=self._run_ws_thread,
            args=(self._done_event, loop),
            daemon=True
        )
        thread.start()
        self.logger.info("_watch_for_breakout(): Breakout watcher started")
        await slack.send_message(f"_watch_for_breakout(): Breakout watcher started")

    def _run_ws_thread(self, done_event: asyncio.Event, loop: asyncio.AbstractEventLoop):
        """
        Background thread: subscribes to SymbolUpdate and
        calls done_event.set() thread‐safely upon breakout.
        """
        def on_message(msg):
            
            if not isinstance(msg, dict) or msg.get("type") != "sf":
                return

            ltp = msg.get("ltp")
            if self.state["triggered"]:
                return

            # print(ltp)
            # check Buy
            if self.swh_price is not None and ltp > self.swh_price:
                direction, price = "Buy", ltp
            # check Sell
            elif self.swl_price is not None and ltp < self.swl_price:
                direction, price = "Sell", ltp
            else:
                return

            self.logger.info(f"Breakout → {direction} at {price}")
            self.state.update({
                "triggered": True,
                "direction": direction,
                "price": price
            })
            try:
                ws.unsubscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
            except Exception as e:
                self.logger.error(f"Error unsubscribing: {e}")

            # signal the asyncio waiter
            loop.call_soon_threadsafe(done_event.set)

        def on_error(err):
            self.logger.error(f"WebSocket error: {err}")
            loop.call_soon_threadsafe(done_event.set)

        def on_close(msg):
            self.logger.info("WebSocket closed")

        def on_connect():
            self.logger.info(f"WebSocket connected—subscribing {self.futures_symbol}")
            ws.subscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
            ws.keep_running()

        ws = data_ws.FyersDataSocket(
            access_token=self.access_token,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_connect,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )
        ws.connect()  # blocks until closed

    async def sl(self, side, symbol):
        try:
            if side == "Buy":
                entry_price = await self.db.fetch_swing_price(swing="swhPrice")
                if entry_price is None:
                    raise Exception("swhPrice not found in database")
                sl_price = round(entry_price - (entry_price * self.sl_percent))            
            else:  # Sell
                entry_price = await self.db.fetch_swing_price(swing="swlPrice")
                if entry_price is None:
                    raise Exception("swlPrice not found in database")
                sl_price = round(entry_price + (entry_price * self.sl_percent))
                self.logger.info(f"SL price set at {sl_price} for Sell position")

            self.logger.info(f"Starting SL monitor for {side} position at entry price {entry_price}")
            await slack.send_message(f"Starting SL monitor for {side} position at entry price {entry_price}")
            
            # Update state with lock for thread safety
            with self.sl_lock:
                self.sl_state = {
                    "active": True,
                    "side": side,
                    "symbol": symbol,
                    "sl_price": sl_price,
                    "exit_executed": False
                }

            # Start WebSocket in separate thread
            ws_thread = threading.Thread(
                target=self._start_sl_websocket,
                daemon=True
            )
            print(side, symbol, entry_price, sl_price,self.sl_lock)
            ws_thread.start()
            
            self.logger.info(f"SL websocket started in background thread")

            #The below is a place holder until Trailing is implemented, later in Strategy main we will 
            # await breakout.trailing_sl().done()
            while datetime.now().time() < time(15, 0):
                print(side, symbol, entry_price, sl_price,self.sl_lock)
                await asyncio.sleep(3600)
            return True
        except Exception as e:
            self.logger.error(f"sl(): Error in SL: {e}")
            await slack.send_message(f"sl(): Error in SL: {e}")
            return False
    
    def _start_sl_websocket(self):
        def on_message(msg):
            # Skip if not relevant message
            if not isinstance(msg, dict) or msg.get("type") != "sf":
                return

            ltp = msg.get("ltp")
            if ltp is None:
                return
                
            # Thread-safe access to SL state
            with self.sl_lock:
                # Skip if not active or already exited
                if not self.sl_state["active"] or self.sl_state["exit_executed"]:
                    return
                    
                side = self.sl_state["side"]
                sl_price = self.sl_state["sl_price"]
                symbol = self.sl_state["symbol"]
                if (side == "Buy" and ltp <= sl_price) or (side == "Sell" and ltp >= sl_price):
                    self.logger.info(f"SL hit for position. LTP: {ltp}, SL: {sl_price}")
                    asyncio.run(self.place_order.exit_single_position(symbol=symbol))
        
        def on_error(err):
            self.logger.error(f"SL WebSocket error: {err}")
        
        def on_close(msg):
            self.logger.info("SL WebSocket closed")
        
        def on_connect():
            self.logger.info(f"SL WebSocket connected—subscribing {self.futures_symbol}")
            ws.subscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
            ws.keep_running()
        
        # Create and connect WebSocket
        ws = data_ws.FyersDataSocket(
            access_token=self.access_token,
            log_path="",
            litemode=False,
            write_to_file=False,
            reconnect=True,
            on_connect=on_connect,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            reconnect_retry=10
        )        
        ws.connect()

    def update_sl_price(self, new_sl_price):        
        with self.sl_lock:
            side = self.sl_state["side"]
            if side == "Buy":
                if new_sl_price > self.sl_state["sl_price"]:
                    self.sl_state["sl_price"] = new_sl_price
            else:
                if new_sl_price < self.sl_state["sl_price"]:
                    self.sl_state["sl_price"] = new_sl_price
        self.logger.info(f"Updated SL price to {new_sl_price}")


    async def trail_sl(self, orderID):        
        try:
            self.logger.info(f"trail_sl(): Starting SL monitor for {side} position")
            await slack.send_message(f"trail_sl(): Starting SL monitor for {side} position")
            ### Add code to fetch orderDateTime from DB using orderID
            order_time = datetime.strptime(order_time, '%d-%b-%Y %H:%M:%S').replace(second=0)
            order_time = pd.Timestamp(order_time).tz_localize('Asia/Kolkata')
            with self.sl_lock:
                initial_sl_price = self.sl_state["sl_price"]
                side = self.sl_state["side"]
            if side == "Buy":
                entry_price = self.db.fetch_swing_price(swing="swhPrice") + 1
                initial_sl_points = round(entry_price - initial_sl_price)
            else:
                entry_price = self.db.fetch_swing_price(swing="swlPrice") - 1
                initial_sl_points = round(entry_price + initial_sl_price)

            maxRR = 0
            rrFlag = False
            while datetime.now().time() < time(15, 10):

                # Until 1:30 PM Trail
                while datetime.now().time() < time(13, 30):
                    min1_data_df = await self.LibertyMarketData.fetch_1min_data()
                    min1_data_df['timestamp'] = pd.to_datetime(min1_data_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                    filtered_df = min1_data_df[min1_data_df['timestamp'] >= order_time]
                    if not len(filtered_df[1:]) > 0:
                        next_check = await self.trigger.get_next_1min_interval()
                        await self.trigger.wait_until_time(next_check)                        
                    if side == "Buy":
                        curr_RR = filtered_df[1:]['high'].max() - entry_price
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 until 1.30 PM")
                                new_sl_price = math.floor(entry_price - (initial_sl_points * 0.5)) # Trailing 50%
                                self.update_sl_price(new_sl_price=new_sl_price)
                    else:
                        curr_RR = entry_price - filtered_df[1:]['low'].min()
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 until 1.30 PM")
                                new_sl_price = math.floor(entry_price + (initial_sl_points * 0.5)) # Trailing 50%
                                self.update_sl_price(new_sl_price=new_sl_price)
                    next_check = await self.trigger.get_next_1min_interval()
                    await self.trigger.wait_until_time(next_check)

                # 1:30 - 2:30 PM Trail
                maxRR = 0 # Resetting max RR
                rrFlag = False # Resetting RR Flag to get notified Once if RR crosses thresholds
                while datetime.now().time() > time(13, 30) and datetime.now().time() < time(14, 30):
                    min1_data_df = await self.LibertyMarketData.fetch_1min_data()
                    min1_data_df['timestamp'] = pd.to_datetime(min1_data_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                    filtered_df = min1_data_df[min1_data_df['timestamp'] >= order_time]
                    if not len(filtered_df[1:]) > 0:
                        next_check = await self.trigger.get_next_1min_interval()
                        await self.trigger.wait_until_time(next_check)
                    if side == "Buy":
                        curr_RR = filtered_df[1:]['high'].max() - entry_price
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            new_sl_price = math.floor(entry_price - (initial_sl_points * 0.5)) # Trailing 50%
                            self.update_sl_price(new_sl_price=new_sl_price)
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 until 1.30 PM")

                    else:
                        curr_RR = entry_price - filtered_df[1:]['low'].min()
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            new_sl_price = math.floor(entry_price - (initial_sl_points * 0.5)) # Trailing 50%
                            self.update_sl_price(new_sl_price=new_sl_price)                            
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 between 1:30 - 2:30 PM")
                    
                    next_check = await self.trigger.get_next_1min_interval()
                    await self.trigger.wait_until_time(next_check)

                # 2:30 - 3:08 PM Trail
                maxRR = 0 # Resetting max RR
                rrFlag = False # Resetting RR Flag to get notified Once if RR crosses thresholds
                while datetime.now().time() > time(14, 30) and datetime.now().time() < time(15, 8):
                    min1_data_df = await self.LibertyMarketData.fetch_1min_data()
                    min1_data_df['timestamp'] = pd.to_datetime(min1_data_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                    filtered_df = min1_data_df[min1_data_df['timestamp'] >= order_time]
                    if not len(filtered_df[1:]) > 0:
                        next_check = await self.trigger.get_next_1min_interval()
                        await self.trigger.wait_until_time(next_check)                        
                    if side == "Buy":
                        curr_RR = filtered_df[1:]['high'].max() - entry_price
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            new_sl_price = math.floor(entry_price - (initial_sl_points * 0.5)) # Trailing 50%
                            self.update_sl_price(new_sl_price=new_sl_price)                            
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 between 2:30 - 3:08 PM Trail")
                    else:
                        curr_RR = entry_price - filtered_df[1:]['low'].min()
                        maxRR = max(maxRR,curr_RR)
                        if maxRR >= 2:
                            if not rrFlag:
                                rrFlag = True
                                await slack.send_message(f"trail_sl(): Found Max RR > 2 until 1.30 PM")
                                new_sl_price = math.floor(entry_price + (initial_sl_points * 0.5)) # Trailing 50%
                                self.update_sl_price(new_sl_price=new_sl_price)
                    next_check = await self.trigger.get_next_1min_interval()
                    await self.trigger.wait_until_time(next_check)
            return
            
        except Exception as e:
            self.logger.error(f"trail_sl(): Error in SL: {e}")
            await slack.send_message(f"trail_sl(): Error in SL: {e}")
            return False
