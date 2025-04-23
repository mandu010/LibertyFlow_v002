from datetime import datetime, time
import pandas as pd
import asyncio
import math

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData
from app.nifty_tf.trigger import LibertyTrigger

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
    def __init__(self, db, fyers, trigger_time):
        self.logger = get_logger("LibertySwing")
        self.db = db
        self.fyers = fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.trigger_time = trigger_time
    
    async def SWH(self) -> bool:
        try:
            self.logger.info("SWH(): Starting to check SWH Formation")
            candleList = []
                            
            # Continue checking every 5 minutes until 12:25 PM
            while True:
                #Hard stop at 12:25 PM
                if datetime.now().time() >= time(12, 25):
                    print("Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks.")
                    self.logger.info("SWH(): Breaced 12.25 PM.")
                    return False

                # Check if trigger condition is met
                df_data = await self.LibertyMarketData.fetch_5min_data()
                #df_data = await self.LibertyMarketData.fetch_1min_data() ### Remove this later
                df_data['timestamp'] = pd.to_datetime(df_data['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')

                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(self.trigger_time).time()]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(self.trigger_time).time()]
                #if referenceCandle.iloc[0]['high'] >= combined_df['high'].max():
                if referenceCandle.iloc[0]['high'] >= max(candleList):
                    if len(candleList) >= 6: 
                    #if len(candleList) >= 3: ### Remove this later
                        self.logger.info("SWH(): Swing High Found")       
                        swhPrice = math.ceil(referenceCandle.iloc[0]['high'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        ### Check needs to be done here
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET "swhPrice" = {swhPrice}, "swhTime" = '{str(referenceCandle.iloc[0]['timestamp'].time())}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)
                        return True
                else:
                    # Making the 2nd last candle as reference candle, because -1 is always in making
                    referenceCandle = filtered_df_data.iloc[-2]
                    self.trigger_time = str(filtered_df_data.iloc[-2]['timestamp'].time())
                    candleList = []   

                print(f"CandleList: \n{candleList}\n Reference Candle:\n{referenceCandle}\n Filtered Data:\n {filtered_df_data}")
                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                #next_check = await self.trigger.get_next_1min_interval() ### Remove this later
                await self.trigger.wait_until_time(next_check)
        except Exception as e:
            self.logger.error(f"SWH(): Error: {e}", exc_info=True)
            print(f"SWH(): Error: {e}")
            return False

    