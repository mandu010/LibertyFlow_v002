import math
from datetime import datetime
import pandas as pd

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
            return float(round(ltp/strike_interval)*strike_interval)
        else:
            raise Exception
        
    async def place_nifty_order(self,side,qty):
        try:
            symbol = await self.get_symbol(side)
            print(symbol)
            data={
                'productType':'INTRADAY',
                'side': 1,
                'symbol': symbol,
                'qty': qty,
                'type': 2,
                'validity':'DAY'
            }
            response = self.fyers.place_order(data)
            self.logger.info(f"Order Placed. Response:{response}\n")
        except Exception as e:
            print(f"Error: {e}")
    
    async def get_symbol(self,side,strike_interval=50):
        try:
            ltp = float(self.LibertyMarketData.fetch_quick_LTP)
            #ltp=23850
            print(f"ltp:{ltp}")
            if ltp is not None:
                ATM =  round(ltp/strike_interval)*strike_interval
            else:
                raise Exception
            url = 'https://public.fyers.in/sym_details/NSE_FO.csv'
            df = pd.read_csv(url, header=None)
            if side == "Buy":
                optionType="CE"
            else:
                optionType="PE"
            df_filtered = df[df[9].str.startswith(f"NSE:NIFTY") & df[9].str.contains(f"{ATM}{optionType}")]
            expiry_date = datetime.strptime(f"{df_filtered.iloc[0][1].split(" ")[3]} {df_filtered.iloc[0][1].split(" ")[2]} {datetime.now().year}", "%d %b %Y").date()
            if expiry_date != datetime.today().date():
                return str(df_filtered.iloc[0][9])
            else:
                return str(df_filtered.iloc[1][9])
        except Exception as e:
            self.logger.error(f"get_symbol(): Error Getting Symbol for {side} {ATM}. Error: {e}")
            return None
