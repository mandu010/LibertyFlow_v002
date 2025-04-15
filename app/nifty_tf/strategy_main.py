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
        #self.swing = LibertySwing(db, fyers, trigger_index=0,trigger_time='19:19:00')
        self.logger.info("LibertyFlow initialized")
    
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
            # range_val = {'low': 299.5,
            #                 'pdc': 304.2,
            #                 'high': 304,
            #                 'datetime': '09-04-2025'}
            #swingHigh = await self.swing.SWH() ### Need to call 
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
            while True:
                if datetime.now().time() < time(9, 15):
                    next_check = await self.trigger.get_next_5min_interval()
                    await self.trigger.wait_until_time(next_check)
                    break
                else:
                    break
            #await asyncio.sleep(5)

            if pctTrigger == False:
                pctTrigger = await self.trigger.pct_trigger(range_val)            
                print(pctTrigger)

            if pctTrigger == False and atrTrigger == False:
                atrTrigger = await self.trigger.ATR()
                print(atrTrigger)
            self.swing = LibertySwing(self.db, self.fyers, trigger_index=0,trigger_time='09:30:00')
            swingHigh = await self.swing.SWH()                
            print(swingHigh)
            await self.db.close()            

        except Exception as e:
            self.logger.error(f"Error in LibertyFlow run: {e}", exc_info=True)
            return 1

