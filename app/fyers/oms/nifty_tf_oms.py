import math
from datetime import datetime
import pandas as pd
import asyncio
import threading
import time

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData
from app.config import settings
from app.slack import slack
from fyers_apiv3.FyersWebsocket import order_ws

class Nifty_OMS:
    def __init__(self, db, fyers):
        self.logger= get_logger("Nifty OMS")
        self.db= db
        self.fyers= fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)
        self.qty = settings.trade.NIFTY_LOT * settings.trade.NIFTY_LOT_SIZE
        self.access_token = settings.fyers.FYERS_ACCESS_TOKEN
        self.nifty_symbol = settings.trade.NIFTY_SYMBOL
        self.nifty_product_type = settings.trade.NIFTY_PRODUCT_TYPE
        self.max_price_pct = 0.05
        self.limit_price_pct = 0.005
        self.buy_side = settings.trade.BUY_TYPE
        self.sell_side = settings.trade.SELL_TYPE
        self.limit_type = settings.trade.LIMIT_TYPE
        self.market_type = settings.trade.MARKET_TYPE

    @staticmethod
    def round_to_nearest_half(value):
        return math.ceil(value * 2) / 2
    
    @staticmethod
    def round_to_nearest_0025(value):
        return round(value)
    
    async def calculateATM(self, strike_interval=50):
        ltp = self.LibertyMarketData.fetch_quick_LTP
        if ltp is not None:
            return round(ltp/strike_interval)*strike_interval
        else:
            raise Exception
        
    async def place_nifty_order(self,side):
        try:
            symbol = await self.get_symbol(side)
            self.logger.info(f"Placing order for: {symbol}")
            data={
                'productType':self.nifty_product_type,
                'side': self.buy_side,
                'symbol': symbol,
                'qty': self.qty,
                'type': 2,
                'validity':'DAY'
            }
            response = self.fyers.place_order(data)
            self.logger.info(f"Order Placed. Response:{response}\n")
        except Exception as e:
            print(f"Error: {e}")
    
    async def get_symbol(self,side,strike_interval=50):
        try:
            # ltp = await self.LibertyMarketData.fetch_quick_LTP()
            ltp = await self.LibertyMarketData.fetch_quick_quote(self.nifty_symbol)
            ltp = ltp['lp']
            print(f"ltp:{ltp}",type(ltp))
            self.logger.info(f"get_symbol(): LTP: {ltp}")
            print(ltp)            
            if ltp is not None:
                ATM =  round(ltp/strike_interval)*strike_interval
                ### Stepping 1 Down in ATM strike
                if side == "Buy":
                    ATM = ATM - 50
                else:
                    ATM = ATM + 50
                print(ATM)

            else:
                raise Exception
            url = 'https://public.fyers.in/sym_details/NSE_FO.csv'
            df = pd.read_csv(url, header=None)
            if side == "Buy":
                optionType="CE"
            else:
                optionType="PE"
            df_filtered = df[df[9].str.startswith(f"NSE:NIFTY") & df[9].str.contains(f"{ATM}{optionType}")]
            expiry_date = datetime.strptime(f"{df_filtered.iloc[0][1].split(" ")[3]} {df_filtered.iloc[0][1].split(" ")[2]} {datetime.now().year}", "%d %b %Y").date()
            if expiry_date != datetime.today().date():
                return str(df_filtered.iloc[0][9])
            else:
                return str(df_filtered.iloc[1][9])
        except Exception as e:
            self.logger.error(f"get_symbol(): Error Getting Symbol for {side} {ATM}. Error: {e}")
            return None

    async def place_nifty_order_new(self,side) -> str:
        # This returns symbol and order date time, both in string
        try:
            symbol = await self.get_symbol(side)
            # symbol='MCX:GOLDPETAL25MAYFUT' # Remove this later
            self.logger.info(f"Placing order for: {symbol}")
            initial_quote = await self.LibertyMarketData.fetch_quick_quote(symbol)
            ask_price = initial_quote['ask']
            limit_price = self.round_to_nearest_half(ask_price + ask_price * self.limit_price_pct) # Setting Limit Price at 1% of ask price
            counter = 1
            data={
                'productType':self.nifty_product_type,
                'side': self.buy_side,
                'symbol': symbol,
                'qty': self.qty,
                'type': self.limit_type,
                'validity':'DAY',
                'limitPrice': limit_price,
                'orderTag': 'NiftyTF'
            }
            response = self.fyers.place_order(data)
            print(response)
            if response['s'] == "ok":
                order_id = response['id']
                asyncio.create_task(self.LibertyMarketData.insert_order_data(orderID=order_id))
            else:
                self.logger.error("place_nifty_order_new(): Failed to Place Order")
                await slack.send_message(f"place_nifty_order_new(): Failed to Place Order \n Place order manually for {symbol} Response: {response}")
                return False
            
            self.logger.info(f"Order Placed. Response:{response}\n")

            await asyncio.sleep(3.5)  # Waiting for a second for order to process, maybe will need to increase later
            placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
            print(f"placed_order_status:{placed_order_status}, {type(placed_order_status)}")
            if placed_order_status == 2:
                await slack.send_message(f"place_nifty_order_new(): Order Filled Successfully for {symbol} Response: {response}")
                return symbol,order_id
            else:
                while counter < 6:
                    counter += 1
                    placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)                         
                    if placed_order_status == 2:
                        await slack.send_message(f"place_nifty_order_new(): Order Filled Successfully for {symbol}")
                        return symbol,order_id
                    fresh_quote = await self.LibertyMarketData.fetch_quick_quote(symbol) ### Getting new quote
                    ask_price = fresh_quote['ask']                                        
                    limit_price = self.round_to_nearest_half(ask_price + ask_price * (self.limit_price_pct * counter))
                    data = {
                            "id":order_id, 
                            "type":self.limit_type, 
                            "limitPrice": limit_price
                        }
                    self.fyers.modify_order(data=data) ### Not Error Checking here
                    await asyncio.sleep(5)
                # Going for Market Order
                self.logger.info("place_nifty_order_new(): Going for Market Order")
                data = {
                        "id":order_id, 
                        "type":self.market_type # <- Market Order
                    }  
                self.fyers.modify_order(data=data) ### Not Error Checking here
                await asyncio.sleep(2)
                placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                if placed_order_status == 2:
                    await slack.send_message(f"place_nifty_order_new(): Exited At Market Price Successfully for {symbol}.")
                    return symbol,order_id                     
                else:
                    self.logger.error("place_nifty_order_new(): Failed to Place Order")
                    await slack.send_message(f"place_nifty_order_new(): Failed to Place Order at Market \n Place order manually for {symbol}")
                    return False                

        except Exception as e:
            print(f"Error: {e}")
            self.logger.error(f"place_nifty_order_new(): {e}")

    async def _monitor_order_websocket(self, order_id, symbol, initial_ask, counter, order_complete_event):
        """
        Monitor order status via WebSocket and modify as needed
        """
        loop = asyncio.get_event_loop()
        
        # Start the WebSocket in a separate thread
        thread = threading.Thread(
            target=self._run_order_monitor_thread,
            args=(order_id, initial_ask, counter, order_complete_event, loop),
            daemon=True
        )
        thread.start()
        self.logger.info(f"Order monitor started for order ID: {order_id}")

    def _run_order_monitor_thread(self, order_id, initial_ask, counter, order_complete_event, loop):
        """
        Background thread for order monitoring and modification
        """
        def on_order(message):
            nonlocal counter
            
            if not isinstance(message, dict) or message.get("s") != "ok" or "orders" not in message:
                return
                
            order_info = message.get("orders", {})
            
            # Check if this is our order
            if order_info.get("id") != order_id:
                return
                
            status = order_info.get("status")
            self.logger.info(f"Order {order_id} status update: {status}")
            
            # If order complete (status 2 in Fyers API), signal completion
            if status == 2:
                self.logger.info(f"Order {order_id} completed successfully!")
                # Signal the asyncio waiter
                loop.call_soon_threadsafe(order_complete_event.set)
                try:
                    ws.unsubscribe(data_type="OnOrders")
                except Exception as e:
                    self.logger.error(f"Error unsubscribing: {e}")
                return
                
            # If order not complete, wait 2 seconds and then modify if needed
            time.sleep(2)
            
            if counter < 10:
                # Increment counter and adjust price
                counter += 1
                new_price = initial_ask * (1 + (counter * 0.01))
                
                # Modify order with new price
                modify_data = {
                    'id': order_id,
                    'type': self.limit_type,  # Market order
                    'limitPrice': new_price
                }
                
                try:
                    modify_response = self.fyers.modify_order(modify_data)
                    self.logger.info(f"Modified order {order_id} to price {new_price}. Response: {modify_response}")
                except Exception as e:
                    self.logger.error(f"Error modifying order: {e}")
            
            elif counter == 10:
                # Convert to market order
                modify_data = {
                    'id': order_id,
                    'type': self.market_type  # Market order
                }
                
                try:
                    modify_response = self.fyers.modify_order(modify_data)
                    self.logger.info(f"Converted order {order_id} to market order. Response: {modify_response}")
                except Exception as e:
                    self.logger.error(f"Error converting to market order: {e}")
        
        def on_error(message):
            self.logger.error(f"WebSocket error: {message}")
            loop.call_soon_threadsafe(order_complete_event.set)
            
        def on_close(message):
            self.logger.info(f"WebSocket closed: {message}")
            
        def on_open():
            self.logger.info(f"WebSocket connected, subscribing to orders for {order_id}")
            ws.subscribe(data_type="OnOrders")
            ws.keep_running()
            
        # Create and connect the WebSocket
        ws = order_ws.FyersOrderSocket(
            access_token=self.access_token,
            log_path="",
            write_to_file=False,
            on_connect=on_open,
            on_orders=on_order,
            on_error=on_error,
            on_close=on_close
        )
        ws.connect() 

    async def exit_position(self):
        try:
            self.logger.info(f"exit_position(): Starting to Exit Postions")
            openPositions=[]
            positions = self.fyers.positions()
            for position in positions['netPositions']:
                if position['netQty'] > 0 and position['productType'] == self.nifty_product_type:
                    openPositions.append(position)
            self.logger.info(f"exit_position(): Found {len(openPositions)} Open Positions")
            for exitPosition in openPositions:
                print(exitPosition)
                symbol = exitPosition['symbol']
                try:
                    positionQty = exitPosition['qty']
                except:
                    positionQty = exitPosition['netQty']
                initial_quote = await self.LibertyMarketData.fetch_quick_quote(symbol)
                print(f"Initial Quote: {initial_quote}")
                bid_price = initial_quote['bid']
                limit_price = self.round_to_nearest_half(bid_price - bid_price * self.limit_price_pct) # Setting Limit Price at 0.5% of ask price
                counter = 1
                data={
                    'productType':self.nifty_product_type,
                    'side': self.sell_side,
                    'symbol': symbol,
                    'qty': positionQty,
                    'type': self.limit_type,
                    'validity':'DAY',
                    'limitPrice': limit_price,
                    'orderTag': 'NiftyTF'
                }
                self.logger.info(f"Data sending to fyers: {data}")
                response = self.fyers.place_order(data)
                print(response)
                if response['s'] == "ok":
                    order_id = response['id']
                else:
                    self.logger.error("exit_position(): Failed to Place Exit Order")
                    await slack.send_message(f"exit_position(): Failed to Place Exit Order \n Exit manually for {symbol} Response: {response}")
                    #return False
                    continue ### Going to next position
                
                self.logger.info(f"Exit Order Placed. Response:{response}\n")

                await asyncio.sleep(1.5)  # Waiting for a second for order to process, maybe will need to increase later
                placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                print(f"exit_position():{placed_order_status}, {type(placed_order_status)}")
                if placed_order_status == 2:
                    await slack.send_message(f"exit_position(): Exited Successfully for {symbol} Response: {response}")
                    return True
                else:
                    while counter < 6:
                        counter += 1
                        placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                        if placed_order_status == 2:
                            await slack.send_message(f"exit_position(): Exited Successfully for {symbol}.")
                            return True                     
                        fresh_quote = await self.LibertyMarketData.fetch_quick_quote(symbol)
                        print(f"Fresh Quote: {fresh_quote}")
                        bid_price = fresh_quote['bid']            
                        limit_price = self.round_to_nearest_half(bid_price - bid_price * (self.limit_price_pct * counter)) ### Exponential Backoff
                        data = {
                                "id":order_id, 
                                "type":self.limit_type, 
                                "limitPrice": limit_price
                            }
                        self.fyers.modify_order(data=data) ### Not Error Checking here
                        await asyncio.sleep(5)
                    # Going for Market Order
                    data = {
                            "id":order_id, 
                            "type":self.market_type # <- Market Order
                        }  
                    self.fyers.modify_order(data=data) ### Not Error Checking here
                    await asyncio.sleep(2)
                    placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                    if placed_order_status == 2:
                        await slack.send_message(f"exit_position(): Exited At Market Price Successfully for {symbol}.")
                        return True            
            if len(openPositions) == 0:
                await slack.send_message(f"exit_position(): No Open Positions to Exit")
        except Exception as e:
            print(f"Error: {e}")
            self.logger.error(f"exit_position(): {e}")                

    async def exit_single_position(self,symbol):
        try:
            self.logger.info(f"exit_single_position(): Starting to Exit ")
            initial_quote = await self.LibertyMarketData.fetch_quick_quote(symbol)
            print(f"Initial Quote: {initial_quote}")
            bid_price = initial_quote['bid']
            limit_price = self.round_to_nearest_half(bid_price - bid_price * self.limit_price_pct) # Setting Limit Price at 0.5% of bid price
            counter = 1
            data={
                'productType':self.nifty_product_type,
                'side': self.sell_side,
                'symbol': symbol,
                'qty': self.qty,
                'type': self.limit_type,
                'validity':'DAY',
                'limitPrice': limit_price,
                'orderTag': 'NiftyTF'
            }
            self.logger.info(f"exit_single_position(): Data sending to fyers: {data}")
            response = self.fyers.place_order(data) ### Placing Order here
            print(response)
            if response['s'] == "ok":
                order_id = response['id']
            else:
                self.logger.error("exit_single_position(): Failed to Place Exit Order")
                await slack.send_message(f"exit_single_position(): Failed to Place Exit Order \n Exit manually for {symbol} Response: {response}")
                return False
                
            self.logger.info(f"exit_single_position(): Exit Order Placed. Response:{response}\n")
            await asyncio.sleep(3.5)  # Waiting for a second for order to process, maybe will need to increase later


            placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
            print(f"exit_single_position():{placed_order_status}, {type(placed_order_status)}")


            if placed_order_status == 2:
                await slack.send_message(f"exit_single_position(): Exited Successfully for {symbol} Response: {response}")
                return True
            else:
                while counter < 6:
                    counter += 1
                    placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                    if placed_order_status == 2:
                        await slack.send_message(f"exit_single_position(): Exited Successfully for {symbol}.")
                        return True                     
                    fresh_quote = await self.LibertyMarketData.fetch_quick_quote(symbol)
                    print(f"Fresh Quote: {fresh_quote}")
                    bid_price = fresh_quote['bid']            
                    limit_price = self.round_to_nearest_half(bid_price - bid_price * (self.limit_price_pct * counter)) ### Exponential Backoff
                    data = {
                            "id":order_id, 
                            "type":self.limit_type, 
                            "limitPrice": limit_price
                        }
                    self.fyers.modify_order(data=data) ### Not Error Checking here
                    await asyncio.sleep(5)
                # Going for Market Order
                data = {
                        "id":order_id, 
                        "type":self.market_type # <- Market Order
                    }  
                self.fyers.modify_order(data=data) ### Not Error Checking here
                await asyncio.sleep(2)
                placed_order_status = await self.LibertyMarketData.fetch_quick_order_status(orderID=order_id)
                if placed_order_status == 2:
                    await slack.send_message(f"exit_single_position(): Exited At Market Price Successfully for {symbol}.")
                    return True     
        except Exception as e:
            print(f"Error: {e}")
            self.logger.error(f"exit_position(): {e}")                          