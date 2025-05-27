from datetime import datetime, time
import pandas as pd
import asyncio
import math

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData
from app.nifty_tf.trigger import LibertyTrigger
from app.slack import slack

class LibertySwing():
    """
        New Approach to get Swings
        1st of all, store the initial trigger time in:
        1. trigger_time
        2. swhTime
        3. swlTime
        Now just initalize SWH/SWL
        It should fetch swhTime from DB itself, let it pull on every iteration.
        Now, you have individual times for SWH and SWL.
        Await 5 mins until len(df) >= 7. 7th is the candle which is being formed.
        Now, once >=7 slice the df.iloc[:-1]['high'].max() and compare with swhTime candle
        if swhTime[High] > df.iloc[:-1]['high'].max(): UPDATE swhPrice in DB & return
        else: get the candle which was highest and update in DB
        var = filtered_df_data.iloc[:-1][filtered_df_data.iloc[:-1]['high'] == filtered_df_data.iloc[:-1]['high'].max()]
        update var.iloc[-1][datetime] wala jo bhi
    """
    def __init__(self, db, fyers):
        self.logger = get_logger("LibertySwing")
        self.db = db
        self.fyers = fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
    
    async def SWH(self) -> bool:
        try:
            self.logger.info("SWH(): Starting to check SWH Formation")
                            
            # Continue checking every 5 minutes until 12:25 PM
            while True:
                # Hard stop at 12:25 PM
                if datetime.now().time() >= time(12, 25): ### Remove this later
                    self.logger.info("SWH(): Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks")
                    await slack.send_message("SWH(): Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks")
                    return False

                trigger_time = await self.db.fetch_swing_trigger_time(swing="swhTime")
                if trigger_time is None:
                    return False
                self.logger.info(f"SWH():trigger_time fetched from DB: {trigger_time}")

                # If time is 9: 15, await till 9.20
                if trigger_time == "09:15:00":
                    if datetime.now().time() <= time(9, 20):
                        next_check = await self.trigger.get_next_5min_interval()
                        await self.trigger.wait_until_time(next_check)


                df_data = await self.LibertyMarketData.fetch_5min_data()
                df_data['timestamp'] = pd.to_datetime(df_data['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(trigger_time).time()]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(trigger_time).time()]

                if len(filtered_df_data) >= 7: 
                    if referenceCandle.iloc[-1]['high'] >= filtered_df_data.iloc[:-1]['high'].max():
                        self.logger.info("SWH(): Swing High Found")
                        swhPrice = math.ceil(referenceCandle.iloc[-1]['high'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        
                        ### Updating DB w/ SWH Price and Time
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET "swhPrice" = {swhPrice}, "swhTime" = '{str(referenceCandle.iloc[-1]['timestamp'].time())}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)
                        return True
                    else:
                        df_cut = filtered_df_data.iloc[:-1]
                        max_high = df_cut['high'].max()
                        trigger_row = df_cut[df_cut['high'] == max_high]
                        trigger_time = str(trigger_row['timestamp'].iloc[0].time())
                        sqlUpdate = f'''UPDATE nifty.trigger_status 
                        SET "swhTime" = '{trigger_time}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlUpdate)

                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                await self.trigger.wait_until_time(next_check)

        except Exception as e:
            self.logger.error(f"SWH(): Error: {e}", exc_info=True)
            print(f"SWH(): Error: {e}")
            return False
        
    async def SWL(self) -> bool:
        try:
            self.logger.info("SWL(): Starting to check SWL Formation")
                            
            # Continue checking every 5 minutes until 12:25 PM
            while True:
                # Hard stop at 12:25 PM
                if datetime.now().time() >= time(12, 25): ### Remove this later
                    self.logger.info("SWL(): Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks")
                    await slack.send_message("SWL(): Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks")
                    return False
                
                trigger_time = await self.db.fetch_swing_trigger_time(swing="swlTime")
                print("SWL()",trigger_time,type(trigger_time))
                if trigger_time is None:
                    return False
                self.logger.info(f"SWL():trigger_time fetched from DB: {trigger_time}")
                # If time is 9: 15, await till 9.20
                if trigger_time == "09:15:00":
                    if datetime.now().time() <= time(9, 20):
                        next_check = await self.trigger.get_next_5min_interval()
                        await self.trigger.wait_until_time(next_check)

                df_data = await self.LibertyMarketData.fetch_5min_data()
                df_data['timestamp'] = pd.to_datetime(df_data['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(trigger_time).time()]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(trigger_time).time()]

                if len(filtered_df_data) >= 7: 
                    if referenceCandle.iloc[-1]['low'] <= filtered_df_data.iloc[:-1]['low'].min():
                        self.logger.info("SWL(): Swing Low Found")
                        swlPrice = math.floor(referenceCandle.iloc[-1]['low'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        ### Updating DB w/ SWL Price and Time
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET "swlPrice" = {swlPrice}, "swlTime" = '{str(referenceCandle.iloc[-1]['timestamp'].time())}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)
                        return True
                    else:
                        df_cut = filtered_df_data.iloc[:-1]
                        min_low = df_cut['low'].min()
                        trigger_row = df_cut[df_cut['low'] == min_low]
                        self.logger.info(f"Trigger_row:{trigger_row},df_cut:{df_cut},min_low:{min_low}")
                        print("SWL(),",trigger_row,trigger_row['timestamp'].iloc[0].time())
                        trigger_time = str(trigger_row['timestamp'].iloc[0].time()) ### This caused an issue, 27th May-> 9:55 and 10:00
                        sqlUpdate = f'''UPDATE nifty.trigger_status 
                            SET "swlTime" = '{trigger_time}'
                            WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlUpdate)

                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                await self.trigger.wait_until_time(next_check)

        except Exception as e:
            self.logger.error(f"SWL(): Error: {e}", exc_info=True)
            print(f"SWL(): Error: {e}")
            return False

    