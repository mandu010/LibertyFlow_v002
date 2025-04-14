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
            pctTrigger, atrTrigger, rangeTrigger = False, False, False ### Replace these with pulling status from DB Later
            #
            # Happy Path-> Get the status of strategy 1st. If Awaiting Trigger then insert trigger_status with today's date first
            #
            sql='''INSERT INTO nifty.trigger_status (date, pct_trigger, atr, range)
                SELECT CURRENT_DATE, NULL, NULL, NULL
                WHERE NOT EXISTS (
                    SELECT 1 FROM nifty.trigger_status WHERE date = CURRENT_DATE
                );'''
            await self.db.execute_query(sql)

            triggerStatusSql = '''
                    SELECT pct_trigger, atr, range FROM nifty.trigger_status
                    where date = CURRENT_DATE
                    order by ctid DESC
                    limit 1
                  '''
            triggerStatus = await self.db.fetch_query(triggerStatusSql)
            if  len(triggerStatus) != 0:
                pctTrigger = triggerStatusSql[0]['pct_trigger']
                atrTrigger = triggerStatusSql[0]['atr']
                rangeTrigger = triggerStatusSql[0]['range']

            if pctTrigger == False:
                pctTrigger = await self.trigger.pct_trigger(range_val)
            
            if pctTrigger == False and atrTrigger == False:
                atrTrigger = await self.trigger.ATR()

            if pctTrigger == False and atrTrigger == False and rangeTrigger == False:
                rangeTrigger = await self.trigger.check_triggers_until_cutoff(range_val)
                if not rangeTrigger:
                    self.logger.info("Not Triggered -> Exit") ### Exit out of day and close the server. Script should not go forward.
                    return False
            if pctTrigger or atrTrigger or rangeTrigger:
                swingHigh = await self.swing.SWH() ### Need to call 
                swingLow = await self.swing.SWL() ### Need to call 


            await self.db.close()            

        except Exception as e:
            self.logger.error(f"Error in LibertyFlow run: {e}", exc_info=True)
            return 1

