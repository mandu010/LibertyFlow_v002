import json
from datetime import datetime
import pandas as pd
import numpy as np
import asyncio

from app.utils.logging import get_logger
from app.config import settings
from app.slack import slack

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

class LibertyRange:
    def __init__(self, db, fyers):
        self.logger= get_logger("bnf_range")
        self.db= db
        self.fyers= fyers
        self.symbol = settings.trade.BANKNIFTY_SYMBOL
        self.range_pct = 0.001 #0.1 %

    async def read_range(self):
        try:
            sql = '''
                SELECT range FROM banknifty.range
                order by ctid DESC
                limit 1
            '''
            range = json.loads((await self.db.fetch_query(sql))[0]['range'])
            self.logger.info(f"read_range(): Fetched range from DB: {range}")
            return range
        except Exception as e:
            self.logger.error(f"read_range(): Error fetching range from DB: {e}", exc_info=True)
            return None
        
    
    async def update_range(self, range) -> bool:
        try:
            data = {"symbol": self.symbol,
                    "resolution": "1D",
                    "date_format": "1",
                    "range_from": datetime.now().strftime('%Y-%m-%d'),
                    "range_to": datetime.now().strftime('%Y-%m-%d'),
                    "cont_flag": 1
                    }
            today_candle_data = self.fyers.history(data)
            
            if today_candle_data['code'] == 200 and "candles" in today_candle_data:
                self.logger.info(f"update_range(): Fetched today candle data: {today_candle_data}")
                df = pd.DataFrame(
                    today_candle_data["candles"],
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                
                # Create a function to handle NumPy types for JSON serialization
                def convert_to_json_serializable(obj):
                    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
                        return int(obj)
                    elif isinstance(obj, (np.float64, np.float32, np.float16)):
                        return float(obj)
                    return obj
                
                # Define value outside the conditions to avoid UnboundLocalError
                value = None
                
                # Within Range
                if (df.iloc[0]['close'] < (range['high'] + range['high']*self.range_pct) and 
                    df.iloc[0]['close'] > (range['low'] - range['low']*self.range_pct)):
                    self.logger.info(f"update_range(): Today's candle is within the range")
                    await slack.send_message("Closed Within Range Today",webhook_name="banknifty")
                    value = {
                            "datetime": datetime.now().strftime('%Y-%m-%d'),
                            "high": convert_to_json_serializable(range['high']),
                            "low": convert_to_json_serializable(range['low']),
                            "pdc": convert_to_json_serializable(df.iloc[0]['close'])
                            }
                    
                # Above Range
                elif (df.iloc[0]['close'] > (range['high'] + range['high']*self.range_pct)):
                    self.logger.info(f"update_range(): Today's candle is above the range")
                    await slack.send_message("Closed Above Range Today",webhook_name="banknifty")
                    value = {
                            "datetime": datetime.now().strftime('%Y-%m-%d'),
                            "high": convert_to_json_serializable(df.iloc[0]['high']),
                            "low": convert_to_json_serializable(df.iloc[0]['low']),
                            "pdc": convert_to_json_serializable(df.iloc[0]['close'])
                            }
                    
                # Below Range
                elif (df.iloc[0]['close'] < (range['low'] - range['low']*self.range_pct)):
                    self.logger.info(f"update_range(): Today's candle is below the range")
                    await slack.send_message("Closed Below Range Today",webhook_name="banknifty")
                    value = {
                            "datetime": datetime.now().strftime('%Y-%m-%d'),
                            "high": convert_to_json_serializable(df.iloc[0]['high']),
                            "low": convert_to_json_serializable(df.iloc[0]['low']),
                            "pdc": convert_to_json_serializable(df.iloc[0]['close'])
                            }
                    
                
                # Check if value was set in any of the conditions
                if value:
                    # Use a custom JSON encoder that handles NumPy types
                    sql = f"""
                        INSERT INTO banknifty.range (range)
                        VALUES ('{json.dumps(value, cls=NumpyEncoder)}')
                        """
                    await self.db.execute_query(sql)
                    self.logger.info(f"update_range(): Range updated successfully in DB with Value: {value}")
                    await slack.send_message(f"Updated: {value}",webhook_name="banknifty")
                    return True
                else:
                    self.logger.warning("update_range(): No condition met for updating range")
                    return False
            else:
                self.logger.warning(f"update_range(): Error fetching today candle data: {today_candle_data}")
                return False                    
        except Exception as e:
            self.logger.error(f"update_range(): Error updating range in DB: {e}", exc_info=True)
            return None
        
    async def read_trigger_status(self):
        try:
            sql = '''
                SELECT pct_trigger, atr, range FROM nifty.trigger_status
                where date = CURRENT_DATE
                order by ctid DESC
                limit 1
            '''
            trigger_status = await self.db.fetch_query(sql)
            if trigger_status is None:
                self.logger.info(f"read_trigger_status(): No trigger status found in DB")
                return None
            trigger_status = json.loads(trigger_status[0]['trigger_status'])
            self.logger.info(f"read_trigger_status(): Fetched current trigger from DB")
            return trigger_status
        except Exception as e:
            self.logger.error(f"read_trigger_status(): Error fetching current trigger status from DB: {e}", exc_info=True)
            return None