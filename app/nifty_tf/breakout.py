from datetime import datetime
import asyncio
import math
from typing import Optional, Dict, Any
import threading

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData
from app.config import settings
from fyers_apiv3.FyersWebsocket import data_ws

class LibertyBreakout:
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertyBreakout")
        self.db = db
        self.fyers = fyers
        self.market_data = LibertyMarketData(db, fyers)
        self.is_running = False
        self.stop_monitoring = False
        self.swh_price = None
        self.swl_price = None
        self.websocket = None
        self.ws_thread = None
        self.state = {
            "triggered": False,
            "breakout_direction": None,
            "breakout_price": None
        }
        self.access_token = settings.fyers.FYERS_ACCESS_TOKEN
        
        # Get the futures symbol - would need to be determined dynamically in real implementation
        #self.futures_symbol = "NSE:NIFTY25APRFUT"  # Example - should be current month
        self.futures_symbol = "MCX:NATURALGAS25APRFUT"  ### Remove this later
    
    async def monitor_breakouts(self, swh_price=None, swl_price=None):
        """
        Monitor price action for breakouts of swing high or low levels.
        This function can be called with initial swing values and then
        additional calls can update the values.
        
        Parameters:
        - swh_price: Optional swing high price to monitor
        - swl_price: Optional swing low price to monitor
        """
        try:
            # Update prices if provided
            if swh_price is not None:
                self.swh_price = swh_price
                self.logger.info(f"Updated swing high price: {self.swh_price}")
            
            if swl_price is not None:
                self.swl_price = swl_price
                self.logger.info(f"Updated swing low price: {self.swl_price}")
            
            # If already running, just update the prices and return
            if self.is_running:
                self.logger.info(f"Breakout monitoring already running, updated with SWH: {self.swh_price}, SWL: {self.swl_price}")
                return
            
            # Start monitoring
            self.is_running = True
            self.stop_monitoring = False
            
            self.logger.info(f"Starting breakout monitoring with SWH: {self.swh_price}, SWL: {self.swl_price}")
            
            # Create an event to wait for websocket completion
            done_event = asyncio.Event()
            
            # Start websocket in a separate thread for both SWH and SWL if they exist
            if self.swh_price is not None:
                asyncio.create_task(self.start_breakout_websocket(
                    price=self.swh_price,
                    side="Buy",
                    access_token=self.access_token,
                    done_event=done_event
                ))
            
            if self.swl_price is not None:
                asyncio.create_task(self.start_breakout_websocket(
                    price=self.swl_price,
                    side="Sell",
                    access_token=self.access_token,
                    done_event=done_event
                ))
            
            # Wait for the done event to be set when a breakout occurs
            await done_event.wait()            
            
            # Process the breakout if it occurred
            if self.state["triggered"]:
                if self.state["breakout_direction"] == "Buy":
                    print("BUY NOW!!")
                    #await self.process_buy_breakout(self.state["breakout_price"])
                else:
                    print("SELL NOW!!")
                    #await self.process_sell_breakout(self.state["breakout_price"])
            
            self.logger.info("Breakout monitoring completed")
            self.is_running = False
            
        except Exception as e:
            self.logger.error(f"Error in breakout monitoring: {e}", exc_info=True)
            self.is_running = False
    
    async def start_breakout_websocket(self, price, side, access_token, done_event):
        """
        Start the Fyers websocket in a separate thread to monitor for breakouts.
        
        Parameters:
        - price: Price level to monitor for breakout
        - side: "Buy" for SWH breakout, "Sell" for SWL breakout
        - access_token: Fyers API access token
        - done_event: asyncio.Event to signal when a breakout occurs
        """
        try:
            self.logger.info(f"Starting {side} breakout monitor at price {price}")
            
            # Define the callbacks for the websocket
            def onmessage(message):
                if not isinstance(message, dict):
                    return
                if message.get("type") != "sf":
                    return  # skip if not symbol feed
                
                ltp = message.get("ltp")
                self.logger.info(f"[{side}] LTP: {ltp} | Target: {price}")
                
                # Check for breakout
                if not self.state["triggered"]:
                    if side == "Buy" and ltp > price + 1:  # 1 point above SWH
                        self.logger.info(f"Breakout! LTP {ltp} > {price}")
                        self.state["triggered"] = True
                        self.state["breakout_direction"] = "Buy"
                        self.state["breakout_price"] = ltp
                        fyers.unsubscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
                        fyers.close_connection()
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(done_event.set)
                    elif side == "Sell" and ltp < price - 1:  # 1 point below SWL
                        self.logger.info(f"Breakdown! LTP {ltp} < {price}")
                        self.state["triggered"] = True
                        self.state["breakout_direction"] = "Sell"
                        self.state["breakout_price"] = ltp
                        fyers.unsubscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
                        fyers.close_connection()
                        loop = asyncio.get_event_loop()
                        loop.call_soon_threadsafe(done_event.set)
            
            def onerror(message):
                self.logger.error(f"Websocket error: {message}")
            
            def onclose(message):
                self.logger.info(f"Websocket connection closed: {message}")
            
            def onopen():
                self.logger.info(f"Connected to websocket. Subscribing to: {self.futures_symbol}")
                fyers.subscribe(symbols=[self.futures_symbol], data_type="SymbolUpdate")
                fyers.keep_running()
            
            # Create socket instance
            fyers = data_ws.FyersDataSocket(
                access_token=access_token,
                log_path="",
                litemode=False,
                write_to_file=False,
                reconnect=True,
                on_connect=onopen,
                on_close=onclose,
                on_error=onerror,
                on_message=onmessage
            )
            
            # Connect in a separate thread to not block asyncio event loop
            self.ws_thread = threading.Thread(target=fyers.connect)
            self.ws_thread.daemon = True  # Make thread daemon so it exits when main thread exits
            self.ws_thread.start()
            
            self.logger.info(f"Started {side} websocket monitor in background thread")
            
        except Exception as e:
            self.logger.error(f"Error starting breakout websocket: {e}", exc_info=True)
            # Signal the event in case of error to prevent hanging
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(done_event.set)
    
    async def process_buy_breakout(self, ltp):
        """Process a buy breakout."""
        try:
            self.logger.info(f"Processing buy breakout at price: {ltp}")
            # Calculate ATM option
            atm_strike = await self.calculate_atm_strike(ltp)
            # Calculate option with delta ~0.5
            option_symbol = await self.find_delta_option(atm_strike, "CE", target_delta=0.5)
            # Place order
            order_result = await self.order.place_buy_order(option_symbol, ltp + 5)  # LTP + 5 to ensure execution
            # Update DB
            await self.update_db_with_order(order_result, "BUY", ltp, option_symbol)
            self.stop_monitoring = True
        except Exception as e:
            self.logger.error(f"Error processing buy breakout: {e}", exc_info=True)
    
    async def process_sell_breakout(self, ltp):
        """Process a sell breakout."""
        try:
            self.logger.info(f"Processing sell breakout at price: {ltp}")
            # Calculate ATM option
            atm_strike = await self.calculate_atm_strike(ltp)
            # Calculate option with delta ~0.5
            option_symbol = await self.find_delta_option(atm_strike, "PE", target_delta=0.5)
            # Place order
            order_result = await self.order.place_sell_order(option_symbol, ltp - 5)  # LTP - 5 to ensure execution
            # Update DB
            await self.update_db_with_order(order_result, "SELL", ltp, option_symbol)
            self.stop_monitoring = True
        except Exception as e:
            self.logger.error(f"Error processing sell breakout: {e}", exc_info=True)
    
    async def calculate_atm_strike(self, current_price):
        """Calculate the at-the-money strike price."""
        # Round to nearest 50 for Nifty
        return round(current_price / 50) * 50
    
    async def find_delta_option(self, atm_strike, option_type, target_delta=0.5):
        """
        Find an option contract with delta close to the target.
        For simplicity, this example just returns the ATM option.
        In a real implementation, you would query option chain and find the contract with delta closest to 0.5.
        """
        # This is simplified - in reality you'd need to query option chain data 
        # and calculate or retrieve delta values
        expiry = await self.get_current_expiry()
        option_symbol = f"NSE:NIFTY{expiry}{atm_strike}{option_type}"
        self.logger.info(f"Selected option with target delta ~{target_delta}: {option_symbol}")
        return option_symbol
    
    async def get_current_expiry(self):
        """Get the current expiry date in the format required for option symbols."""
        # Simplified - you'd need to implement logic to determine the current expiry date
        # This would typically be the nearest Thursday
        return "25APR"  # Example format
    
    async def update_db_with_order(self, order_result, direction, trigger_price, option_symbol):
        """Update database with order details."""
        try:
            sql = f"""
            UPDATE nifty.trigger_status 
            SET 
                breakout_time = NOW(),
                breakout_price = {trigger_price},
                order_direction = '{direction}',
                option_symbol = '{option_symbol}',
                order_id = '{order_result.get("order_id", "unknown")}',
                status = 'Exited'
            WHERE date = CURRENT_DATE
            """
            await self.db.execute_query(sql)
            self.logger.info(f"Updated DB with {direction} order details")
        except Exception as e:
            self.logger.error(f"Error updating DB with order: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the breakout monitoring."""
        self.stop_monitoring = True
        self.logger.info("Stopping breakout monitoring")
        
        # Close any active websocket connections
        if self.ws_thread and self.ws_thread.is_alive():
            # This is simplified - in a real implementation you would need 
            # a proper way to signal the websocket to close
            pass  # The thread is daemon so it will exit when main thread exits