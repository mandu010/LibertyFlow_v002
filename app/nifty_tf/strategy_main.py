import asyncio
from datetime import datetime,time

from app.nifty_tf.range import LibertyRange
from app.nifty_tf.trigger import LibertyTrigger
from app.nifty_tf.swingFormation import LibertySwing
from app.utils.logging import get_logger


class LibertyFlow:
    def __init__(self, db, fyers):
        self.logger= get_logger("LibertyFlow")
        self.db= db
        self.fyers= fyers
        self.range = LibertyRange(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.swing = LibertySwing(db, fyers, trigger_index=0,trigger_time='11:35:00')
        self.logger.info("LibertyFlow initialized")
    
    async def run(self) -> None:
        try:
            self.logger.info("LibertyFlow run started")
            range_val = await self.range.read_range()
            pctTrigger, atrTrigger, triggered = False, False, False ### Replace these with pulling status from DB Later
            #
            # Happy Path-> Get the status of strategy 1st. If Awaiting Trigger then insert trigger_status with today's date first
            #
            sql='''INSERT INTO nifty.trigger_status (date, pct_trigger, atr, range)
                SELECT CURRENT_DATE, NULL, NULL, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM nifty.trigger_status WHERE date = CURRENT_DATE
                );'''
            await self.db.execute_query(sql)

            pctTrigger = await self.trigger.pct_trigger(range_val)
            
            if pctTrigger == False:
                atrTrigger = await self.trigger.ATR()

            if pctTrigger == False and atrTrigger == False:
                triggered = await self.trigger.check_triggers_until_cutoff(range_val)
                if not triggered:
                    self.logger.info("Not Triggered -> Exit")
                    return False
            swingHigh = await self.swing.SWH()


            await self.db.close()            

        except Exception as e:
            self.logger.error(f"Error in LibertyFlow run: {e}", exc_info=True)
            return 1

