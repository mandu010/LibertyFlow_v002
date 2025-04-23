import asyncio
import threading
from datetime import datetime, time

from app.utils.logging import get_logger
from app.config import settings
from fyers_apiv3.FyersWebsocket import data_ws


class LibertyBreakout:
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertyBreakout")
        self.db = db
        self.fyers = fyers

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
        self.futures_symbol = f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT" # "NSE:NIFTY25APRFUT"  # TODO: derive dynamically

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
        self.logger.info("Breakout watcher started")

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

    # ——————————————————————————————————————————————————————————
    # Your existing order placement helpers can remain exactly as they are:
    #   process_buy_breakout(), process_sell_breakout(),
    #   calculate_atm_strike(), find_delta_option(), update_db_with_order(), etc.
    # ——————————————————————————————————————————————————————————
