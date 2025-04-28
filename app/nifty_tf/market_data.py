from app.utils.logging import get_logger
from datetime import datetime
import pandas as pd
import builtins
from datetime import datetime, timedelta

class LibertyMarketData:
    def __init__(self, db, fyers):
        self.logger= get_logger("Market Data")
        self.db= db
        self.fyers= fyers
        #self.symbol = f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT"
        #self.symbol = "MCX:NATURALGAS25APRFUT" ### For Testing outside of market hours ### Remove this later
        self.symbol = "NSE:NIFTY25MAYFUT" ### For Testing outside of market hours ### Remove this later

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
