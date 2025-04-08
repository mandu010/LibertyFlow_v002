import json
from app.utils.logging import get_logger
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import builtins


class LibertyTrigger():
    def __init__(self, db, fyers):
        self.logger = get_logger("trigger")
        self.db = db
        self.fyers = fyers

    async def pct_trigger(self, range) -> bool:
        try:
            data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                  "resolution":"1",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min1_data = self.fyers.history(data)
            if min1_data['code'] == 200  and "candles" in min1_data:
                self.logger.info(f"pct_trigger(): Fetched min1 candle data.")
                df = pd.DataFrame(
                    min1_data["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                change = round((df.iloc[0]['open'] - range['pdc']) / range['pdc'] * 100, 2)
                if change > 0:
                    if change >=0.4:
                        self.logger.info(f"pct_trigger(): Triggered")
                        return True
                    else:
                        self.logger.info(f"pct_trigger(): Not Triggered. Go to ATR Trigger")
                        return False
                else:
                    if change <= -0.4:
                        self.logger.info(f"pct_trigger(): Triggered")
                        return True
                    else:
                        self.logger.info(f"pct_trigger(): Not Triggered. Go to ATR Trigger")
                        return False
            else:
                self.logger.warning(f"pct_trigger(): Error fetching 1min candles: {min1_data}")
                return False         
        except Exception as e:
            self.logger.error(f"pct_trigger(): Error fetching min1 data: {e}", exc_info=True)
            return False
        
    async def ATR(self, range) -> bool:
        try:
            ### Getting Today's Data
            data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                  "resolution":"5",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min5_data_today = self.fyers.history(data)
            if min5_data_today['code'] == 200  and "candles" in min5_data_today:
                self.logger.info(f"ATR(): Fetched today's 5min candle data.")
                df_today = pd.DataFrame(
                    min5_data_today["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )            

            ### Getting Previous Day's Data
            for i in builtins.range(1, 6):
                    data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                            "resolution":"5",
                            "date_format":"1",
                            "range_from":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                            "range_to":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                            "cont_flag":1
                            }
                    min5_data_prevDay = self.fyers.history(data)
                    if min5_data_prevDay['code'] == 200  and "candles" in min5_data_prevDay and min5_data_prevDay['s'] !="no_data":
                        self.logger.info(f"ATR(): Fetched previous day's 5min candle data.")
                        df_prevDay = pd.DataFrame(
                            min5_data_prevDay["candles"], 
                            columns=["timestamp", "open", "high", "low", "close", "volume"]
                            )
                        break
            average_prev_body = (df_prevDay['close'] - df_prevDay['open']).abs().tail(10).mean()
            if average_prev_body != 0:
                atrVal = round(((abs(df_today.iloc[0]['close'] - df_today.iloc[0]['open']) - average_prev_body) / average_prev_body) * 100,2)
            else:
                atrVal = 0
            self.logger.info(f"ATR(): ATR Value: {atrVal}")
            if atrVal >= 300:
                return True
            else:
                self.logger.info(f"ATR(): ATR Value not met. Go to Range break trigger.")
                return False
        except Exception as e:
            self.logger.error(f"ATR(): Error fetching today 5min candle data: {e}", exc_info=True)
            return False    