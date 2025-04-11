
from app.nifty_tf.range import LibertyRange
from app.nifty_tf.trigger import LibertyTrigger
from app.utils.logging import get_logger


class LibertyOrder:
    def __init__(self, db, fyers):
        self.logger= get_logger("LibertyFlow")
        self.db= db
        self.fyers= fyers
        self.range = LibertyRange(db, fyers)
        self.trigger = LibertyTrigger(db, fyers)
        self.logger.info("LibertyFlow initialized")