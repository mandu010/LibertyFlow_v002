import json
from datetime import datetime, timedelta, time
import pandas as pd
import numpy as np
import builtins
import asyncio
import pytz

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData

class LibertyTrigger():
    def __init__(self, db, fyers):
        self.logger = get_logger("trigger")
        self.db = db
        self.fyers = fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)

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
                min1_df = pd.DataFrame(
                    min1_data["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                min1_df['timestamp'] = pd.to_datetime(min1_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')

                sqlTrue = f'''UPDATE nifty.trigger_status 
                SET pct_trigger = TRUE, trigger_index = 0, trigger_time = '{min1_df['timestamp'].iloc[0]}'
                WHERE date = CURRENT_DATE '''
                sqlFalse = f'''UPDATE nifty.trigger_status 
                SET pct_trigger = FALSE
                WHERE date = CURRENT_DATE '''
               
                change = round((min1_df.iloc[0]['open'] - range['pdc']) / range['pdc'] * 100, 2)
                if change > 0 and change >=0.4:
                    self.logger.info(f"pct_trigger(): Triggered")
                    await self.db.execute_query(sqlTrue)                     
                    return True
                elif change < 0 and change <= -0.4:
                        self.logger.info(f"pct_trigger(): Triggered")
                        await self.db.execute_query(sqlTrue)                        
                        return True
                else:
                    self.logger.info(f"pct_trigger(): Not Triggered. Go to ATR Trigger")
                    await self.db.execute_query(sqlFalse)                  
                    return False
                
            else:
                self.logger.warning(f"pct_trigger(): Error fetching 1min candles: {min1_data}")
                return False         
        except Exception as e:
            self.logger.error(f"pct_trigger(): Error fetching min1 data: {e}", exc_info=True)
            return False
        
    async def ATR(self) -> bool:
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
                df_today['timestamp'] = pd.to_datetime(df_today['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')         

            ### Getting Previous Day's Data
            for i in builtins.range(1, 6):
                    data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                            "resolution":"5",
                            "date_format":"1",
                            "range_from":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                            "range_to":(datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d'),
                            "cont_flag":1
                            }
                    sqlTrue = f'''UPDATE nifty.trigger_status 
                    SET atr = TRUE, trigger_index = 0, trigger_time = '{df_today['timestamp'].iloc[0]}'
                    WHERE date = CURRENT_DATE '''
                    sqlFalse = f'''UPDATE nifty.trigger_status 
                    SET atr = FALSE
                    WHERE date = CURRENT_DATE '''                    
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
                await self.db.execute_query(sqlTrue)
                return True
            else:
                self.logger.info(f"ATR(): ATR Value not met. Go to Range break trigger.")
                await self.db.execute_query(sqlFalse)
                return False
        except Exception as e:
            self.logger.error(f"ATR(): Error fetching today 5min candle data: {e}", exc_info=True)
            await self.db.execute_query(sqlFalse)
            return False    
        
    async def range_break(self, range) -> bool:
        try:
            data={"symbol":f"NSE:NIFTY{datetime.now().strftime('%y%b').upper()}FUT",
                  "resolution":"5",
                  "date_format":"1",
                  "range_from":datetime.now().strftime('%Y-%m-%d'),
                  "range_to":datetime.now().strftime('%Y-%m-%d'),
                  "cont_flag":1
                  }
            min5_data = self.fyers.history(data)
            if min5_data['code'] == 200  and "candles" in min5_data:
                self.logger.info(f"range_break(): Fetched min5 candle data.")
                df = pd.DataFrame(
                    min5_data["candles"], 
                    columns=["timestamp", "open", "high", "low", "close", "volume"]
                    ) 
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')                        
                if df.iloc[-2]['high'] > range['high'] or df.iloc[-2]['low'] < range['low']:
                    self.logger.info(f"range_break(): Triggered")
                    sql = f'''UPDATE nifty.trigger_status 
                    SET range = TRUE, trigger_index = 0, trigger_time = '{df['timestamp'].iloc[0]}'
                    WHERE date = CURRENT_DATE '''
                    await self.db.execute_query(sql)
                    return True
                else:
                    self.logger.info(f"range_break(): Not Triggered.")                    
                    sql = '''UPDATE nifty.trigger_status 
                    SET range = FALSE
                    WHERE date = CURRENT_DATE '''                    
                    await self.db.execute_query(sql)
                    return False
                
            else:
                self.logger.warning(f"range_break(): Error fetching 1min candles: {min5_data}")
                return False         
        except Exception as e:
            self.logger.error(f"range_break(): Error fetching min1 data: {e}", exc_info=True)
            return False

    async def check_triggers_until_cutoff(self, range_val):
        """Check triggers every 5 minutes until 12:25 PM"""
        now = datetime.now().time()
        
        # Check if we're in the valid time window
        if now < time(9, 20):
            # Too early - wait until 9:20 to start
            print("Market not yet open. Waiting until 9:20 AM to start.")
            await self.wait_until_start_time(time(9, 20))
        elif now >= time(12, 25):
            # Too late - past cutoff time
            print("Already past cutoff time of 12:25 PM. Strategy will not start.")
            return False
        else:
            # Between 9:20 and 12:25 - start immediately
            print(f"App restarted at {now}. Beginning immediately.")
            
            # Important: If the app restarted mid-interval, check immediately
            # and then align to the 5-minute schedule
            is_triggered = await self.range_break(range_val)
            if is_triggered:
                print("Trigger condition met on immediate check after restart!")
                return True
        
        # Continue checking every 5 minutes until 12:25 PM
        while True:
            now = datetime.now().time()
            
            # Hard stop at 12:25 PM
            if now >= time(12, 25):
                print("Reached cutoff time 12:25 PM. Stopping trigger checks.")
                return False
                
            # Wait for next 5-minute interval
            next_check = self.get_next_5min_interval()
            await self.wait_until_time(next_check)
            await self.wait_until_time(self.get_next_5min_interval())
            
            # Check if trigger condition is met
            is_triggered = await self.range_break(range_val)
            
            if is_triggered:
                print("Trigger condition met!")
                return True
    
    async def wait_until_start_time(self, target_time):
        """Wait until the specified start time before beginning checks"""
        now = datetime.now()
        target = datetime.now().replace(
            hour=target_time.hour, 
            minute=target_time.minute, 
            second=0, 
            microsecond=0
        )
        
        # If target time is in the future today
        if now < target:
            wait_seconds = (target - now).total_seconds()
            print(f"Waiting {wait_seconds} seconds until {target_time}")
            await asyncio.sleep(wait_seconds)
        else:
            # If we're already past the target time, don't wait
            print(f"Already past start time {target_time}. Beginning immediately.")
    
    async def wait_until_time(self, target_time):
        """Wait until a specific time"""
        now = datetime.now()
        target = datetime.now().replace(
            hour=target_time.hour, 
            minute=target_time.minute, 
            second=0, 
            microsecond=0
        )
        
        # If target is in the past, add 5 minutes until it's in the future
        while now >= target:
            target = target.replace(minute=target.minute + 5)
            # Handle hour rollover
            if target.minute >= 60:
                target = target.replace(hour=target.hour + 1, minute=target.minute - 60)
            
        wait_seconds = (target - now).total_seconds()
        print(f"Next check at {target.time()}, waiting {wait_seconds:.2f} seconds")
        await asyncio.sleep(wait_seconds)
    
    def get_next_5min_interval(self):
        """Get the next 5-minute interval time"""
        now = datetime.now()
        current_minute = now.minute
        # Calculate the next 5-minute mark
        next_5min = ((current_minute // 5) + 1) * 5
        
        # Handle hour rollover
        new_hour = now.hour
        if next_5min >= 60:
            new_hour += 1
            next_5min -= 60
            
        return time(new_hour, next_5min)