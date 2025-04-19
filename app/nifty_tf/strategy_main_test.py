import asyncio
from datetime import datetime,time

from app.nifty_tf.range import LibertyRange
from app.nifty_tf.trigger import LibertyTrigger
from app.nifty_tf.swingFormation import LibertySwing
from app.nifty_tf.breakout_test import LibertyBreakout
from app.utils.logging import get_logger


class LibertyFlow:
    def __init__(self, db, fyers):
        self.logger= get_logger("LibertyFlow")
        self.db= db
        self.fyers= fyers
        self.range = LibertyRange(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.breakout = LibertyBreakout(db, fyers)
        self.logger.info("LibertyFlow initialized")

        # Create event tracking dictionary
        self.events = {
            "swh_formed": asyncio.Event(),
            "swl_formed": asyncio.Event(),
            "breakout_detected": asyncio.Event(),
            "trading_complete": asyncio.Event()
        }        
        # Store swing values
        self.swh_value = 23850
        self.swl_value = 23852        
    
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

            await self.breakout.monitor_breakouts(swh_price=self.swh_value)
            #await self.breakout.monitor_breakouts(swh_price=self.swl_value)
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
                self.swh_value = result["swhPrice"] if result and "swhPrice" in result else None
                
                if self.swh_value:
                    self.logger.info(f"SWH formed with value: {self.swh_value}, notifying breakout system")
                    
                    # Start or update breakout monitor with SWH value
                    await self.breakout.monitor_breakouts(swh_price=self.swh_value)
                    
                    # Set event to notify other components
                    self.events["swh_formed"].set()
            else:
                self.logger.info("SWH formation failed or timed out")
                
        except Exception as e:
            self.logger.error(f"Error in SWH formation: {e}", exc_info=True)

    async def run_swl_formation(self, swing_instance):
        """Run SWL formation and immediately notify breakout when it forms"""
        try:
            self.logger.info("Starting Swing Low formation monitoring")
            
            result = await swing_instance.SWL()
            
            if result:
                # Get the SWL value from DB
                sql = 'SELECT "swlPrice" FROM nifty.trigger_status WHERE date = CURRENT_DATE'
                result = await self.db.fetch_query(sql)
                self.swl_value = result["swlPrice"] if result and "swlPrice" in result else None
                
                if self.swl_value:
                    self.logger.info(f"SWL formed with value: {self.swl_value}, notifying breakout system")
                    
                    # Start or update breakout monitor with SWL value
                    await self.breakout.monitor_breakouts(swl_price=self.swl_value)
                    
                    # Set event to notify other components
                    self.events["swl_formed"].set()
            else:
                self.logger.info("SWL formation failed or timed out")
                
        except Exception as e:
            self.logger.error(f"Error in SWL formation: {e}", exc_info=True)

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