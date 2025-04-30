import asyncio

from app.nifty_tf.range import LibertyRange
from app.nifty_tf.trigger import LibertyTrigger
from app.utils.logging import get_logger
from app.config import settings
from app.slack import slack

class LibertyOrder:
    def __init__(self, db, fyers):
        self.logger= get_logger("OMS")
        self.db= db
        self.fyers= fyers
        self.range = LibertyRange(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.logger.info("LibertyFlow initialized")
        self.qty = settings.trade.NIFTY_LOT * settings.trade.NIFTY_LOT_SIZE

    async def nifty_tf_long(self):
        self.logger.info("nifty_tf_long(): Starting")
        