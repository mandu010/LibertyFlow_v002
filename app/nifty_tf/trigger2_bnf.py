import json
from datetime import datetime, timedelta, time
import pandas as pd
import numpy as np
import builtins
import asyncio
import pytz

from app.utils.logging import get_logger
from app.nifty_tf.market_data_bnf import LibertyMarketData
from app.slack import slack

class LibertyTrigger():
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertyTrigger_Bnf")
        self.db = db
        self.fyers = fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)

    async def pct_trigger(self, range) -> bool:
        try:
            while True:
                if datetime.now().time() < time(9, 16, 15):
                    next_check = await self.get_next_1min_interval()
                    await self.wait_until_time(next_check)
                    break
                else:
                    break            
            min1_df = await self.LibertyMarketData.fetch_1min_data()
            min1_df['timestamp'] = pd.to_datetime(min1_df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
            
            change = round((min1_df.iloc[0]['open'] - range['pdc']) / range['pdc'] * 100, 2)
            asyncio.create_task(slack.send_message(f"Percent Change is {change}",webhook_name="banknifty"))
            if change >= 0.3 and change <= 1.0:
                self.logger.info(f"pct_trigger(): Triggered. Percent Change is {change}")
                return [True, change]
            elif change <= -0.3 and change >= -1.0:
                    return [True, change]
            else:
                self.logger.info(f"pct_trigger(): Not Triggered. Exiting. Percent Change is {change}")
                return [False, change]
      
        except Exception as e:
            self.logger.error(f"pct_trigger(): Error fetching min1 data: {e}", exc_info=True)
            return False
        
    async def ATR(self,opening_percent):
        try:
            while True:
                if datetime.now().time() < time(9, 20):
                    next_check = await self.get_next_5min_interval()
                    await self.wait_until_time(next_check)
                    break
                else:
                    break
            await asyncio.sleep(3) ### Even after 9.20 waiting a few seconds
            df_today = await self.LibertyMarketData.fetch_5min_data()
            df_today['timestamp'] = pd.to_datetime(df_today['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')         

            df_prevDay = await self.LibertyMarketData.fetch_prevDay_5min_data()
            df_prevDay['timestamp'] = pd.to_datetime(df_prevDay['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')                      

            average_prev_body = (df_prevDay['close'] - df_prevDay['open']).abs().tail(10).mean()
            if average_prev_body != 0:
                atrVal = round(((abs(df_today.iloc[0]['close'] - df_today.iloc[0]['open']) - average_prev_body) / average_prev_body) * 100,2)
            else:
                atrVal = 0
            self.logger.info(f"ATR(): ATR Value: {atrVal}")
            asyncio.create_task(slack.send_message(f"ATR(): ATR Value: {atrVal}",webhook_name="banknifty"))
            if df_today.iloc[0]['close'] > df_today.iloc[0]['open']:
                direction = "Buy"
                poi = round(df_today.iloc[0]['high'])
            if df_today.iloc[0]['close'] < df_today.iloc[0]['open']:
                direction = "Sell"
                poi = round(df_today.iloc[0]['low'])

            """Checking Criteria 1"""
            if atrVal >= 1000 and atrVal <= 1500:
                return [True,direction.poi]

            """Checking Criteria 2: Dynamic Calculation"""
            dynamic_cbab_calculator_result = self.dynamic_cbab_calculator(opening_percent=opening_percent, CBAB_value=atrVal)
            if dynamic_cbab_calculator_result:
                return [True,direction,poi]
            else:
                self.logger.info(f"ATR(): ATR Value not met. Exiting")
                return [False,direction,poi]
            
        except Exception as e:
            self.logger.error(f"ATR(): Error fetching today 5min candle data: {e}", exc_info=True)
            return [False,"N/A",0.0]
        
    async def range_break(self, range) -> bool:
        try: 
            now = datetime.now().time()
            
            # Check if we're in the valid time window
            if now < time(9, 25):
                # Too early - wait until 9:25 to start
                self.logger.info("range_break(): Waiting till 9.25, if triggered before it.")
                await self.wait_until_start_time(time(9, 25))
                await asyncio.sleep(3)           
            df = await self.LibertyMarketData.fetch_5min_data()
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')                        
            self.logger.info(f"range_break(): Checking")

            for i,r in df.iterrows():
                if df.iloc[i]['high'] > range['high'] or df.iloc[i]['low'] < range['low']:
                    self.logger.info(f"range_break(): Triggered")
                    trigger_time = str(df['timestamp'].iloc[i].time())
                    sql = f'''UPDATE nifty.trigger_status 
                    SET "range" = TRUE, "trigger_index" = 0, "trigger_time" = '{trigger_time}', "swhTime" = '{trigger_time}', "swlTime" = '{trigger_time}'
                    WHERE "date" = CURRENT_DATE '''
                    sql = f"""
                            UPDATE nifty.trigger_status
                            SET "range" = TRUE,
                                "trigger_index" = '{i}',
                                "trigger_time" = '{trigger_time}',
                                "swhTime" = '{trigger_time}',
                                "swlTime" = '{trigger_time}'
                            WHERE "date" = CURRENT_DATE;
                            """.strip()
                    await self.db.execute_query(sql)
                    asyncio.create_task(self.db.update_status(status='Awaiting Swing Formation'))
                    await slack.send_message(f"range_break(): Triggered.")
                    self.logger.info(f"range_break(): Triggered.")                    
                    return True
                
                ### If not returned from loop, then returning False
                self.logger.info(f"range_break(): Not Triggered.")                    
                sql = '''UPDATE nifty.trigger_status 
                SET range = FALSE
                WHERE date = CURRENT_DATE '''                    
                await self.db.execute_query(sql)
            return False
                    
        except Exception as e:
            self.logger.error(f"range_break(): Error fetching min1 data: {e}", exc_info=True)
            return False

    async def check_triggers_until_cutoff(self, range_val):
        """Check triggers every 5 minutes until 12:25 PM"""
        now = datetime.now().time()
        
        # Check if we're in the valid time window
        if now < time(9, 25):
            # Too early - wait until 9:25 to start
            self.logger.info("check_triggers_until_cutoff(): Waiting till 9.25, if triggered before it.")
            await self.wait_until_start_time(time(9, 25))
            # Check if trigger condition is met
            is_triggered = await self.range_break(range_val)
            if is_triggered:
                print("Trigger condition met!")
                self.logger.info("check_triggers_until_cutoff(): Trigger condition met!")
                return True            
        elif now >= time(12, 25):
            # Too late - past cutoff time
            print("Already past cutoff time of 12:25 PM. Strategy will not start.")
            return False
        else:
            # Between 9:25 and 12:25 - start immediately
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
                self.logger.info("check_triggers_until_cutoff(): Reached cutoff time 12:25 PM. Stopping trigger checks.")
                return False
                
            # Wait for next 5-minute interval
            next_check = await self.get_next_5min_interval()
            await self.wait_until_time(next_check)
            
            # Check if trigger condition is met
            is_triggered = await self.range_break(range_val)
            if is_triggered:
                print("Trigger condition met!")
                self.logger.info("check_triggers_until_cutoff(): Trigger condition met!")
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
    
    async def get_next_5min_interval(self):
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
    
    async def get_next_1min_interval(self):
        """Get the next 1-minute interval time"""
        now = datetime.now()
        current_minute = now.minute
        # Calculate the next 5-minute mark
        next_5min = ((current_minute // 1) + 1) * 1 
        
        # Handle hour rollover
        new_hour = now.hour
        if next_5min >= 60:
            new_hour += 1
            next_5min -= 60
            
        return time(new_hour, next_5min)
    
    def dynamic_cbab_calculator(opening_percent, CBAB_value,
                                gap_low=0.30, gap_high=1.00,
                                CBAB_MIN_AT_LOW=300, CBAB_MIN_AT_HIGH=800,
                                CBAB_MAX_AT_LOW=800, CBAB_MAX_AT_HIGH=1500):
        """
        CBAB × Opening % dynamic range calculator (supports +ve / -ve openings)

        Parameters:
        -----------
        opening_percent : float
            Opening gap %, can be +ve or -ve
        CBAB_value : float
            The CBAB value to check
        gap_low : float, default=0.30
            Lower gap threshold
        gap_high : float, default=1.00
            Upper gap threshold
        CBAB_MIN_AT_LOW : float, default=300
            CBAB minimum when opening = gap_low
        CBAB_MIN_AT_HIGH : float, default=800
            CBAB minimum when opening = gap_high
        CBAB_MAX_AT_LOW : float, default=900
            CBAB maximum when opening = gap_low
        CBAB_MAX_AT_HIGH : float, default=1500
            CBAB maximum when opening = gap_high

        Returns:
        --------
        bool : True if CBAB value is within the dynamic range, False otherwise
        """

        def clamp(x, lo, hi):
            return max(lo, min(hi, x))

        def interpolate(x, x0, x1, y0, y1):
            x = clamp(x, x0, x1)
            t = (x - x0) / (x1 - x0)
            return y0 + t * (y1 - y0)

        # Absolute gap (handles -ve openings too)
        g = abs(opening_percent)

        # Linear interpolation for thresholds
        cbab_min = interpolate(g, gap_low, gap_high, CBAB_MIN_AT_LOW, CBAB_MIN_AT_HIGH)
        cbab_max = interpolate(g, gap_low, gap_high, CBAB_MAX_AT_LOW, CBAB_MAX_AT_HIGH)
        # print(f"cbab_min:{cbab_min} cbab_max:{cbab_max}")

        # Return True/False based on whether CBAB is within range
        return cbab_min <= CBAB_value <= cbab_max    