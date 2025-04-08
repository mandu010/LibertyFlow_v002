import json
from app.utils.logging import get_logger
from datetime import datetime
import pandas as pd

class LibertyRange:
    def __init__(self, db, fyers):
        self.logger= get_logger("range")
        self.db= db
        self.fyers= fyers

    async def read_range(self):
        try:
            sql = '''
                SELECT range FROM nifty.range
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
            symbol = f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT"
            data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                  "resolution":"1D",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            today_candle_data = self.fyers.history(data)

            if today_candle_data['code'] == 200  and "candles" in today_candle_data:
                self.logger.info(f"update_range(): Fetched today candle data: {today_candle_data}")
                df = pd.DataFrame(
                    today_candle_data["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                ### Withing Range
                if df.iloc[0]['close'] < (range['high'] + range['high']*.001) and df.iloc[0]['close'] > (range['low'] + range['low']*.001):
                    self.logger.info(f"update_range(): Today's candle is within the range")
                    value = {
                            "datetime":datetime.now().strftime('%Y-%m-%d'),
                            "open":range['open'],
                            "high":range['high'],
                            "low":range['low'],
                            "pdc":df.iloc[0]['close']
                            }
                    sql = f"""
                        INSERT INTO nifty.range (range)
                        VALUES ('{json.dumps(value)}')
                        """
                    await self.db.execute_query(sql)

                ### Above Range
                if df.iloc[0]['close'] > (range['high'] + range['high']*.001) and \
                    df.iloc[0]['close'] > (range['low'] + range['low']*.001):
                    self.logger.info(f"update_range(): Today's candle is above the range")
                    value = {
                            "datetime":datetime.now().strftime('%Y-%m-%d'),
                            "open":df.iloc[0]['open'],
                            "high":df.iloc[0]['high'],
                            "low":df.iloc[0]['low'],
                            "pdc":df.iloc[0]['close']
                            }
                    sql = f"""
                        INSERT INTO nifty.range (range)
                        VALUES ('{json.dumps(value)}')
                        """
                    await self.db.execute_query(sql)

                ### Below Range
                if df.iloc[0]['close'] < (range['high'] + range['high']*.001) and \
                    df.iloc[0]['close'] < (range['low'] + range['low']*.001):
                    self.logger.info(f"update_range(): Today's candle is below the range")
                    value = {
                            "datetime":datetime.now().strftime('%Y-%m-%d'),
                            "open":df.iloc[0]['open'],
                            "high":df.iloc[0]['high'],
                            "low":df.iloc[0]['low'],
                            "pdc":df.iloc[0]['close']
                            }
                    sql = f"""
                        INSERT INTO nifty.range (range)
                        VALUES ('{json.dumps(value)}')
                        """
                    await self.db.execute_query(sql)
                self.logger.info(f"update_range(): Range updated successfully in DB with Value: {value}")
                return True
            else:
                self.logger.warning(f"update_range(): Error fetching today candle data: {today_candle_data}")
                return False                    

        except Exception as e:
            self.logger.error(f"update_range(): Error updating range in DB: {e}", exc_info=True)
            return None