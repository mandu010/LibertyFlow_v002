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
    
    async def SWH(self):
        try:
            self.logger.info("SWH(): Triggered")
            candleList = []
                            
            # Continue checking every 5 minutes until 01:00 PM
            while True:
                # Hard stop at 13:00 PM
                if datetime.now().time() >= time(13, 00):
                    print("Reached cutoff time 13:00 PM. Stopping Swing Formation Check checks.")
                    self.logger.info("SWH(): Breaced 1 PM.")
                    return False
                

                # Check if trigger condition is met
                df_data = await self.LibertyMarketData.fetch_5min_data()
                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(self.trigger_time).time()]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(self.trigger_time).time()]
                candleList.append(filtered_df_data.iloc[-2])
                combined_df = pd.concat(candleList, ignore_index=True)

                if referenceCandle.iloc[0]['high'] >= combined_df['high'].max():
                    if len(candleList) >= 6:
                        self.logger.info("SWH(): Swing High Found")       
                        swhPrice = math.ceil(referenceCandle.iloc[0]['high'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        ### Check needs to be done here
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET swhPrice = {swhPrice}, swhTime = '{referenceCandle['timestamp'].iloc[0]}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)
                        
                        ### Sabse pehele to Breakout Method ko Call kar.
                        ### Breakout method ne websocket se connect karna chahea.
                        ### Update DB with SWH
                else:
                    referenceCandle = filtered_df_data.iloc[-2]
                    self.trigger_time = filtered_df_data.iloc[-2]['timestamp'].time()
                    candleList = []                    


                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                await self.trigger.wait_until_time(next_check)
                await self.trigger.wait_until_time(await self.get_next_5min_interval())
            
        except Exception as e:
            self.logger.error(f"SWH(): Error: {e}", exc_info=True)
            print(f"SWH(): Error: {e}")

    async def SWL(self):
        try:
            self.logger.info("SWL(): Triggered")
            candleList = []
                            
            # Continue checking every 5 minutes until 01:00 PM
            while True:
                # Hard stop at 13:00 PM
                if datetime.now().time() >= time(13, 00):
                    print("Reached cutoff time 13:00 PM. Stopping Swing Formation Check checks.")
                    self.logger.info("SWL(): Breaced 1 PM.")
                    return False

                # Check if trigger condition is met
                df_data = await self.LibertyMarketData.fetch_5min_data()
                filtered_df_data = df_data[df_data['timestamp'].dt.time > pd.to_datetime(self.trigger_time).time()]
                referenceCandle = df_data[df_data['timestamp'].dt.time == pd.to_datetime(self.trigger_time).time()]
                candleList.append(filtered_df_data.iloc[-2])
                combined_df = pd.concat(candleList, ignore_index=True)

                if referenceCandle.iloc[0]['low'] <= combined_df['low'].min():
                    if len(candleList) >= 6:
                        self.logger.info("SWL(): Swing High Found")                     
                        swlPrice = math.floor(referenceCandle.iloc[0]['low'])              
                        referenceCandle['timestamp'] = pd.to_datetime(referenceCandle['timestamp'], unit='s', utc=True).dt.tz_convert('Asia/Kolkata')
                        ### Check needs to be done here
                        sqlTrue = f'''UPDATE nifty.trigger_status 
                        SET swlPrice = {swlPrice}, swlTime = '{referenceCandle['timestamp'].iloc[0]}'
                        WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlTrue)                        
                        ### Sabse pehele to Breakout Method ko Call kar.
                        ### Breakout method ne websocket se connect karna chahea.
                        ### Update DB with SWL
                else:
                    referenceCandle = filtered_df_data.iloc[-2]
                    self.trigger_time = filtered_df_data.iloc[-2]['timestamp'].time()
                    candleList = []                    


                # Wait for next 5-minute interval
                next_check = await self.trigger.get_next_5min_interval()
                await self.trigger.wait_until_time(next_check)
                await self.trigger.wait_until_time(await self.get_next_5min_interval())
                await asyncio.sleep(5) ### Adding this additional 5 second wait to make sure next candle gets started is taken up by Broker
            
        except Exception as e:
            self.logger.error(f"SWL(): Error: {e}", exc_info=True)
            print(f"SWL(): Error: {e}")

