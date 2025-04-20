import math

from app.utils.logging import get_logger
from app.nifty_tf.market_data import LibertyMarketData

class Nifty_OMS:
    def __init__(self, db, fyers):
        self.logger= get_logger("Nifty OMS")
        self.db= db
        self.fyers= fyers
        self.LibertyMarketData = LibertyMarketData(db, fyers)

    async def calculateATM(self, strike_interval=50):
        ltp = self.LibertyMarketData.fetch_quick_LTP
        if ltp is not None:
            return round(ltp/strike_interval)*strike_interval
        else:
            raise Exception
        
    async def place_nifty_order(self,side,ATM,symbol,qty):
        try:
            data={
                'productType':'INTRADAY',
                'side': 1,
                'symbol': symbol,
                'qty': qty,
                'type': 2
            }
            self.fyers.place_order(data)
        except Exception as e:
            print(f"Error: {e}")

        