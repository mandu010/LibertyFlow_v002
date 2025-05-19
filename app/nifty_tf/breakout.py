import asyncio
import threading
from datetime import datetime, time

from app.utils.logging import get_logger
from app.config import settings
from fyers_apiv3.FyersWebsocket import data_ws
from app.slack import slack
from app.fyers.oms.nifty_tf_oms import Nifty_OMS

class LibertyBreakout:
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertyBreakout")
        self.db = db
        self.fyers = fyers
        self.symbol = settings.trade.NIFTY_SYMBOL

        # thresholds (set via monitor_breakouts)
        self.swh_price = None
        self.swl_price = None

        # breakout state (updated on first breach)
        self.state = {
            "triggered": False,
            "direction": None,
            "price": None
        }

        # internal control
        self._monitor_started = False
        self._done_event: asyncio.Event = None

        # Fyers connection details
        self.access_token = settings.fyers.FYERS_ACCESS_TOKEN
        self.futures_symbol = self.symbol

        # Trail & SL Settings
        self.sl_percent = settings.trade.NIFTY_SL_PCT # 0.3 %
        self.position = {
            "active": False,
            "side": None,
            "entry_price": None,
            "sl_price": None
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

    async def sl(self, side, entry_price):
        self.logger.info(f"Starting SL monitor for {side} position at entry price {entry_price}")
        await slack.send_message(f"Starting SL monitor for {side} position at entry price {entry_price}")

        if side == "Buy":
            sl_price = round(entry_price - (entry_price * self.sl_percent))
            self.logger.info(f"SL price set at {sl_price} for Buy position")
        else:  # Sell
            sl_price = round(entry_price + (entry_price * self.sl_percent))
            self.logger.info(f"SL price set at {sl_price} for Sell position")
        
        self.position = {
                    "active": True,
                    "side": side,
                    "entry_price": entry_price,
                    "sl_price": sl_price
                }

        self._sl_hit_event = asyncio.Event()        

        loop = asyncio.get_event_loop()
        thread = threading.Thread(
            target=self._run_sl_ws_thread,
            args=(side, sl_price, self._sl_hit_event, loop),
            daemon=True
        )
        thread.start()
        self.logger.info(f"SL watcher started for {side} position")
        
        # Wait for the SL process to complete
        await self._sl_hit_event.wait()
        self.logger.info("SL monitoring completed")
        
        return True
    def _run_sl_ws_thread(self, side, sl_price, symbol, sl_hit_event, loop):
        """
        Background thread: subscribes to SymbolUpdate and
        executes stop loss IMMEDIATELY when threshold is crossed.
        """
        # Flag to ensure we only exit once
        exit_executed = False
        
        def on_message(msg):
            nonlocal exit_executed
            
            # Skip if we've already executed the exit
            if exit_executed:
                return
                
            if not isinstance(msg, dict) or msg.get("type") != "sf":
                return

            ltp = msg.get("ltp")
            if ltp is None:
                return
                
            # Check if SL is hit and execute immediately
            if (side == "Buy" and ltp < sl_price) or (side == "Sell" and ltp > sl_price):
                # Set flag immediately to prevent multiple executions
                exit_executed = True
                
                # Log the SL hit
                if side == "Buy":
                    self.logger.info(f"SL hit for Buy position. LTP: {ltp}, SL: {sl_price}")
                else:
                    self.logger.info(f"SL hit for Sell position. LTP: {ltp}, SL: {sl_price}")
                
                try:
                    # CRITICAL: Call exit_single_position directly with the symbol
                    # This is the simplest and fastest approach as requested
                    response = self.place_order.exit_single_position(symbol)
                    
                    # Log the exit
                    self.logger.info(f"SL Exit executed for {symbol}: {response}")
                    
                    # Unsubscribe from WebSocket
                    ws.unsubscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
                    
                    # Update DB via a task in the main event loop
                    loop.call_soon_threadsafe(
                        lambda: asyncio.create_task(
                            self.db.update_status(status=f'Exited - SL_HIT')
                        )
                    )
                    
                    # Signal the asyncio waiter that we're done
                    loop.call_soon_threadsafe(sl_hit_event.set)
                    
                except Exception as e:
                    self.logger.error(f"Error executing SL exit: {e}", exc_info=True)
                    loop.call_soon_threadsafe(sl_hit_event.set)

        def on_error(err):
            self.logger.error(f"SL WebSocket error: {err}")
            loop.call_soon_threadsafe(sl_hit_event.set)

        def on_close(msg):
            self.logger.info("SL WebSocket closed")

        def on_connect():
            self.logger.info(f"SL WebSocket connected—subscribing {self.futures_symbol}")
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