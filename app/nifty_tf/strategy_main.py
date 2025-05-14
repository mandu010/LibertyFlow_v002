import asyncio
from datetime import datetime,time

from app.nifty_tf.range import LibertyRange
from app.nifty_tf.breakout import LibertyBreakout
from app.utils.logging import get_logger
from app.fyers.oms.nifty_tf_oms import Nifty_OMS
from app.nifty_tf.swingFormation2 import LibertySwing
from app.nifty_tf.trigger2 import LibertyTrigger
from app.slack import slack

class LibertyFlow:
    def __init__(self, db, fyers):
        self.logger= get_logger("LibertyFlow")
        self.db= db
        self.fyers= fyers
        self.range = LibertyRange(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.breakout = LibertyBreakout(db, fyers)
        self.place_order = Nifty_OMS(db, fyers)
        self.logger.info("LibertyFlow initialized")

        # Create event tracking dictionary
        self.events = {
            "swh_formed": asyncio.Event(),
            "swl_formed": asyncio.Event(),
            "breakout_detected": asyncio.Event(),
            "trading_complete": asyncio.Event()
        }        
        # Store swing values
        self.swh_value = None
        self.swl_value = None        
    
    async def run(self) -> None:
        try:
            self.logger.info("LibertyFlow run started")
            pctTrigger, atrTrigger, rangeTrigger = False, False, False ### Initializing triggers as False
            sql='''INSERT INTO nifty.trigger_status (date, pct_trigger, atr, range)
                SELECT CURRENT_DATE, NULL, NULL, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM nifty.trigger_status WHERE date = CURRENT_DATE
                );'''
            await self.db.execute_query(sql)            
            range_val = await self.range.read_range()
            sqlStatus = '''INSERT INTO nifty.status (date, status)
                SELECT CURRENT_DATE,'Awaiting Trigger'
                WHERE NOT EXISTS (
                    SELECT 1 FROM nifty.status WHERE date = CURRENT_DATE
                );'''
            await self.db.execute_query(sqlStatus)

            triggerStatusSql = '''
                    SELECT pct_trigger, atr, range FROM nifty.trigger_status
                    where date = CURRENT_DATE
                    order by ctid DESC
                    limit 1
                  '''
            triggerStatus = await self.db.fetch_query(triggerStatusSql)
            if  triggerStatus is not None and  len(triggerStatus) != 0:
                if triggerStatus[0]['pct_trigger'] is not None: pctTrigger = bool(triggerStatus[0]['pct_trigger'])
                if triggerStatus[0]['atr'] is not None: atrTrigger = bool(triggerStatus[0]['atr'])
                if triggerStatus[0]['range'] is not None: rangeTrigger = bool(triggerStatus[0]['range'])

            ### Wait until Market start if before 9.15
            while True:
                if datetime.now().time() < time(9, 15):
                    next_check = await self.trigger.get_next_5min_interval()
                    await self.trigger.wait_until_time(next_check)
                else:
                    break

            if not any([pctTrigger]):
                await asyncio.sleep(15)
                pctTrigger = await self.trigger.pct_trigger(range_val)            

            if not any([pctTrigger, atrTrigger]):
                atrTrigger = await self.trigger.ATR()

            if not any([pctTrigger, atrTrigger, rangeTrigger]): 
                rangeTrigger = await self.trigger.check_triggers_until_cutoff(range_val)

            ### Exiting if not Triggered
            if not any([pctTrigger, atrTrigger, rangeTrigger]):
                self.logger.info("Not Triggered -> Exit") ### Exit out of day and close the server. Script should not go forward.
                asyncio.create_task(self.db.update_status(status='Not Triggered'))
                return 1   
            if pctTrigger or atrTrigger or rangeTrigger:
                asyncio.create_task(self.db.update_status(status='Awaiting Swing Formation'))

                trigger_time = await self.db.fetch_trigger_time() 
                if trigger_time is not None and len(trigger_time) != 0:
                    trigger_time = trigger_time[0]['trigger_time']
                    self.logger.info(f"Using trigger time: {trigger_time}")
                print(f"Trigger Time: {trigger_time}")

                # Initializing Swing Class
                swh_swing = LibertySwing(self.db, self.fyers)    
                swl_swing = LibertySwing(self.db, self.fyers)                

                self.logger.info("Starting parallel swing formation and monitoring tasks")
                asyncio.create_task(slack.send_message("Starting parallel swing formation and monitoring tasks"))
                await asyncio.gather(
                    self.run_swh_formation(swh_swing),
                    self.run_swl_formation(swl_swing)
                    #self.monitor_trading_session()
                )
            self.logger.info("Awaiting Breakout")
            asyncio.create_task(slack.send_message("Awaiting Breakout"))
            state = await self.breakout.wait_for_breakout()
            direction, price = state["direction"], state["price"]

            if direction == "Buy":
                self.logger.info("direction: Buy")
                asyncio.create_task(slack.send_message("Order Placed: Long"))
                # await self.place_order.place_nifty_order(side="Buy")
                symbol = await self.place_order.place_nifty_order_new(side="Buy")
            else:
                self.logger.info("direction: Sell")
                asyncio.create_task(slack.send_message("Order Placed: Short"))
                # await self.place_order.place_nifty_order(side="Sell")
                symbol = await self.place_order.place_nifty_order_new(side="Sell")

            await self.db.close()   
            return True                   

        except Exception as e:
            self.logger.error(f"Error in LibertyFlow run: {e}", exc_info=True)
            return 1

    async def run_swh_formation(self, swing_instance):
        """Run SWH formation and immediately notify breakout when it forms"""
        try:
            self.logger.info("Starting Swing High formation monitoring")
            result = await swing_instance.SWH()
            if result:
                # Get the SWH value from DB
                sql = 'SELECT "swhPrice" FROM nifty.trigger_status WHERE date = CURRENT_DATE'
                result = await self.db.fetch_query(sql)
                if result is not None:
                    self.logger.info(f"run_swh_formation(): {result}")
                    self.swh_value = result[0]["swhPrice"]
                
                if self.swh_value:
                    self.logger.info(f"SWH formed with value: {self.swh_value}, notifying breakout system")
                    
                    asyncio.create_task(slack.send_message("Starting Breakout Monitor for SWH"))
                    # Set event to notify other components
                    self.events["swh_formed"].set()                  

                    # Start or update breakout monitor with SWH value
                    await self.breakout.monitor_breakouts(swh_price=self.swh_value)   
            else:
                self.logger.info("SWH formation failed or timed out")
                await slack.send_message("run_swh_formation(): SWH formation failed or timed out")
                
        except Exception as e:
            self.logger.error(f"Error in SWH formation: {e}", exc_info=True)
            await slack.send_message(f"run_swh_formation(): Error in SWH formation: {e}")

    async def run_swl_formation(self, swing_instance):
        """Run SWL formation and immediately notify breakout when it forms"""
        try:
            self.logger.info("Starting Swing Low formation monitoring")
            
            result = await swing_instance.SWL()
            
            if result:
                # Get the SWL value from DB
                sql = 'SELECT "swlPrice" FROM nifty.trigger_status WHERE date = CURRENT_DATE'
                result = await self.db.fetch_query(sql)
                if result is not None:
                    self.logger.info(f"SWL(): {result}")
                    self.swl_value = result[0]["swlPrice"]

                if self.swl_value:
                    self.logger.info(f"SWL formed with value: {self.swl_value}, notifying breakout system")
                    
                    # Set event to notify other components
                    self.events["swl_formed"].set()
                    asyncio.create_task(slack.send_message("Starting Breakout Monitor for SWL"))
                    # Start or update breakout monitor with SWL value
                    await self.breakout.monitor_breakouts(swl_price=self.swl_value)
            else:
                self.logger.info("SWL formation failed or timed out")
                await slack.send_message("run_swl_formation(): SWL formation failed or timed out")
                
        except Exception as e:
            self.logger.error(f"Error in SWL formation: {e}", exc_info=True)
            await slack.send_message(f"run_swl_formation(): Error in SWL formation: {e}")

    async def monitor_trading_session(self):
            """Monitor the trading session for completion conditions"""
            try:
                while True:
                    # Check if it's past market close time
                    # if datetime.now().time() >= time(15, 30):  # 3:30 PM
                    #     self.logger.info("Market closed, stopping all processes")
                    #     await self.breakout.stop()
                        
                    #     # Update status in DB
                    #     sqlStatus = '''UPDATE nifty.status 
                    #         SET status = 'Exited - Market Close'
                    #         WHERE date = CURRENT_DATE '''
                    #     await self.db.execute_query(sqlStatus)
                        
                    #     self.events["trading_complete"].set()
                    #     break
                    
                    # Check if both swing formations have completed
                    both_swings_formed = self.events["swh_formed"].is_set() and self.events["swl_formed"].is_set()
                    
                    # Check if breakout has been detected (by checking the breakout state)
                    breakout_detected = self.breakout.state["triggered"] if hasattr(self.breakout, "state") else False
                    
                    # Check if we should end the session
                    if breakout_detected:
                        self.logger.info("Breakout detected, trading session complete")
                        
                        # Get breakout direction
                        direction = self.breakout.state.get("breakout_direction", "Unknown")
                        
                        # Update status in DB
                        sqlStatus = f'''UPDATE nifty.status 
                            SET status = 'Exited - {direction} Breakout'
                            WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlStatus)
                        
                        self.events["trading_complete"].set()
                        break
                    
                    # If both swings formed but no breakout by 13:00, exit
                    if both_swings_formed and datetime.now().time() >= time(13, 00) and not breakout_detected:
                        self.logger.info("Both swings formed but no breakout by 12:30, ending session")
                        
                        # Update status in DB
                        sqlStatus = '''UPDATE nifty.status 
                            SET status = 'Exited - No Breakout'
                            WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlStatus)
                        
                        self.events["trading_complete"].set()
                        break
                    
                    # If neither swing could form by cutoff time (12:25)
                    if datetime.now().time() >= time(12, 25) and not (self.events["swh_formed"].is_set() or self.events["swl_formed"].is_set()):
                        self.logger.info("No swings formed by cutoff time, ending session")
                        
                        # Update status in DB
                        sqlStatus = '''UPDATE nifty.status 
                            SET status = 'Exited - No Swings Formed'
                            WHERE date = CURRENT_DATE '''
                        await self.db.execute_query(sqlStatus)
                        
                        self.events["trading_complete"].set()
                        break
                    
                    await asyncio.sleep(10)  # Check every 10 seconds
                    
            except Exception as e:
                self.logger.error(f"Error monitoring trading session: {e}", exc_info=True)
                self.events["trading_complete"].set()  # Set the event to prevent hanging

    async def monitor_trading_session_temp(self):
        try:
            while True:
                if datetime.now().time() >= time(13, 00): 
                    asyncio.create_task(slack.send_message("Stop Algo."))
        except Exception as e:
            asyncio.create_task(slack.send_message("Stop Algo."))