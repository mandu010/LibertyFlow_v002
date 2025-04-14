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
        self.swing = LibertySwing(db, fyers, trigger_index=0,trigger_time='19:19:00')
        self.logger.info("LibertyFlow initialized")
    
    async def run(self) -> None:
        try:
            self.logger.info("LibertyFlow run started")
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
            swingHigh = await self.swing.SWH() ### Need to call 


            await self.db.close()            

        except Exception as e:
            self.logger.error(f"Error in LibertyFlow run: {e}", exc_info=True)
            return 1

