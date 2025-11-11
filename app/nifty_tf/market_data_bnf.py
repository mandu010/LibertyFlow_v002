from datetime import datetime
import pandas as pd
import builtins

from app.utils.logging import get_logger
from datetime import datetime, timedelta
from app.config import settings
from app.slack import slack

class LibertyMarketData:
    def __init__(self, db, fyers):
        self.logger= get_logger("Market Data BNF")
        self.db= db
        self.fyers= fyers
        #self.symbol = "MCX:NATURALGAS25APRFUT" ### For Testing outside of market hours ### Remove this later
        self.symbol = settings.trade.BANKNIFTY_SYMBOL

    async def fetch_5min_data(self):
        try:
            data={
                  "symbol":self.symbol,
                  "resolution":"5",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min5_data_today = self.fyers.history(data)
            if min5_data_today['code'] == 200  and "candles" in min5_data_today:
                self.logger.info(f"fetch_5min_data(): Fetched today's 5min candle data.")
                min5_data_df = pd.DataFrame(
                    min5_data_today["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )     
                #min5_data_df['timestamp'] = pd.to_datetime(min5_data_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata') 
                return min5_data_df 
            self.logger.info(f"fetch_5min_data(): Error fetching range from DB: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"fetch_5min_data(): Error fetching range from DB: {e}", exc_info=True)
            return None 
                   
    async def fetch_1min_data(self):
        try:
            data={
                  "symbol":self.symbol,
                  "resolution":"1",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min1_data_today = self.fyers.history(data)
            if min1_data_today['code'] == 200  and "candles" in min1_data_today:
                self.logger.info(f"fetch_1min_data(): Fetched today's 1min candle data.")
                min1_data_df = pd.DataFrame(
                    min1_data_today["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    ) 
                #min1_data_df['timestamp'] = pd.to_datetime(min1_data_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')      
                return min1_data_df       
            self.logger.info(f"fetch_1min_data(): Error fetching range from DB: {e}", exc_info=True)
        except Exception as e:
            self.logger.error(f"fetch_1min_data(): Error fetching range from DB: {e}", exc_info=True)
            return None       
             
    async def fetch_prevDay_5min_data(self):
        try:
            for i in builtins.range(1, 6):
                data={
                        "symbol":self.symbol,
                        "resolution":"5",
                        "date_format":"1",
                        "range_from":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                        "range_to":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                        "cont_flag":1
                        }                   
                min5_data_prevDay = self.fyers.history(data)
                if min5_data_prevDay['code'] == 200  and "candles" in min5_data_prevDay and min5_data_prevDay['s'] !="no_data":
                    self.logger.info(f"fetch_prevDay_5min_data(): Fetched previous day's 5min candle data.")
                    df_prevDay = pd.DataFrame(
                        min5_data_prevDay["candles"], 
                        columns=["timestamp", "open", "high", "low", "close", "volume"]
                        )
                    break
            return  df_prevDay  
        except Exception as e:
            self.logger.error(f"fetch_prevDay_5min_data(): Error fetching data from Fyers: {e}", exc_info=True)
            return None  

    async def fetch_quick_LTP(self):
        try:
            data={
                  "symbol":self.symbol,
                  "resolution":"1",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min1_data_today = self.fyers.history(data)
            if min1_data_today['code'] == 200  and "candles" in min1_data_today:
                self.logger.info(f"fetch_quick_LTP(): Fetching quick LTP.")
                min1_data_df = pd.DataFrame(
                    min1_data_today["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    ) 
                return float(min1_data_df.iloc[-1]['close'])
        except Exception as e:
            self.logger.error(f"fetch_quick_LTP(): Error fetching last LTP: {e}", exc_info=True)
            return None
        
    async def fetch_quick_quote(self, symbol):
        try:
            response = self.fyers.quotes(data={"symbols": symbol})
            if response.get('code') == 200 and response.get('d') and len(response['d']) > 0:
                quote_data = response['d'][0].get('v', {})
                self.logger.info(f"fetch_quick_quote(): Fetched {self.symbol} Quote: LTP:{quote_data.get('lp')} ASK:{quote_data.get('ask')}")
                return {
                    'lp': quote_data.get('lp'),
                    'ask': quote_data.get('ask'),
                    'bid': quote_data.get('bid')
                }
            else:
                error_msg = response.get('message', 'Unknown error')
                self.logger.error(f"fetch_quick_quote(): API Error: {error_msg}")
                return {'lp': None, 'ask': None}
        except Exception as e:
            self.logger.error(f"fetch_quick_quote(): Exception occurred: {str(e)}")
            return {'lp': None, 'ask': None}                           
        
    async def insert_order_data(self, orderID):
        try:
            response = self.fyers.get_orders({'id':str(orderID)})
            if response.get('code') == 200 and len(response['orderBook']) > 0:
                order = response['orderBook'][0]
                sql =f'''
                    INSERT INTO nifty.orders ("symbol", "qty", "orderID", "timestamp", "date","fullSymbol")
                    VALUES ('{order['description'].split(":")[-1]}','{order['qty']}','{order['id']}','{order['orderDateTime']}',CURRENT_DATE,'{order['symbol']}')
                    '''
                await self.db.execute_query(sql=sql)
                await slack.send_message(f"insert_order_data(): Order {order['description'].split(":")[-1]} inserted into DB successfully")
            else:
                error_msg = "Order Not Placed Probably"
                self.logger.error(f"insert_order_data(): Order Error: {error_msg}")
                return 
        except Exception as e:
            self.logger.error(f"insert_order_data(): Exception occurred: {str(e)}")
            return 
        
    async def fetch_quick_order_status(self, orderID):
        try:
            response = self.fyers.get_orders({'id':str(orderID)})
            if response.get('code') == 200 and len(response['orderBook']) > 0:
                order = response['orderBook'][0]
                return order['status']
            else:
                error_msg = "Failed to fetch Order Status"
                self.logger.error(f"fetch_quick_order_status(): Order Status Fetch Error: {error_msg}")
                return 0
        except Exception as e:
            self.logger.error(f"fetch_quick_order_status(): Exception occurred: {str(e)}")
            return 0
