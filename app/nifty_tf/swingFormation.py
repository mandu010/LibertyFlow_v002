from datetime import datetime, time
import pandas as pd
import asyncio
import math

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData
from app.nifty_tf.trigger import LibertyTrigger

class LibertySwing():
    def __init__(self, db, fyers, trigger_index, trigger_time):
        self.logger = get_logger("LibertySwing")
        self.db = db
        self.fyers = fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.trigger_index = trigger_index
        self.trigger_time = trigger_time
    
    async def SWH(self) -> bool:
        try:
            self.logger.info("SWH(): Starting to check SWH Formation")
            candleList = []
                            
            # Continue checking every 5 minutes until 12:25 PM
            while True:
                #Hard stop at 12:25 PM
                # if datetime.now().time() >= time(12, 25): ### Change to 12:25
                #     print("Reached cutoff time 12:25 PM. Stopping Swing Formation Check checks.")
                #     self.logger.info("SWH(): Breaced 1 PM.")
                #     return False

                # Check if trigger condition is met
                #df_data = await self.LibertyMarketData.fetch_5min_data()
                df_data = await self.LibertyMarketData.fetch_1min_data()
                df_data['timestamp'] = pd.to_datetime(df_data['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')

                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(self.trigger_time).time()]
                filtered_df_data = filtered_df_data[:-1]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(self.trigger_time).time()]
                #candleList.append(filtered_df_data.iloc[-2].to_frame().T)
                #combined_df = pd.concat(candleList, ignore_index=True)
                candleList.append(filtered_df_data.iloc[-2]['high'])
                #if referenceCandle.iloc[0]['high'] >= combined_df['high'].max():
                if referenceCandle.iloc[0]['high'] >= max(candleList):
                    if len(candleList) >= 6: 
                        self.logger.info("SWH(): Swing High Found")       
                        swhPrice = math.ceil(referenceCandle.iloc[0]['high'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        ### Check needs to be done here
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET "swhPrice" = {swhPrice}, "swhTime" = '{str(referenceCandle.iloc[0]['timestamp'].time())}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)
                        return True
                        ### Sabse pehele to Breakout Method ko Call kar.
                        ### Breakout method ne websocket se connect karna chahea.
                        ### Update DB with SWH
                else:
                    # Making the Last candle as the reference candle
                    referenceCandle = filtered_df_data.iloc[-1]
                    self.trigger_time = str(filtered_df_data.iloc[-1]['timestamp'].time())
                    candleList = []   
                    print("In side else")             
                    print(f"CandleList: \n{candleList}\n Reference Candle:\n{referenceCandle}\n Filtered Data:\n {filtered_df_data}")    

                print(f"CandleList: \n{candleList}\n Reference Candle:\n{referenceCandle}\n Filtered Data:\n {filtered_df_data}")
                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                await self.trigger.wait_until_time(next_check)
            
        except Exception as e:
            self.logger.error(f"SWH(): Error: {e}", exc_info=True)
            print(f"SWH(): Error: {e}")

