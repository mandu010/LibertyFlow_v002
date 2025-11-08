import asyncio
import functools
import os
from dotenv import set_key, find_dotenv
from datetime import datetime
import pandas as pd

from app.config import settings
from app.utils.logging import get_logger
from app.db.dbclass import db

from fyers_apiv3 import fyersModel

logger = get_logger("FyersClient")

class FyersClient:
    def __init__(self):
        self.client_id = settings.fyers.CLIENT_ID
        self.secret_key = settings.fyers.SECRET_KEY
        self.access_token = settings.fyers.FYERS_ACCESS_TOKEN

    async def connect(self):
        logger.info("connect():Initializing Fyers client...")
        try:
            # Initialize the Fyers client with the provided credentials
            self.fyers = fyersModel.FyersModel(
                client_id=self.client_id,
                token=self.access_token)
            logger.info("connect():Fyers client initialized successfully")
            if await self._validate_token() and await self._update_nifty_symbol() and await self._update_banknifty_symbol():
                return self.fyers
            else:
                return None
        except Exception as e:
            logger.error(f"connect():Error initializing Fyers client: {e}", exc_info=True)

    async def _validate_token(self) -> bool:
        try:
            # Use get_profile API to validate token
            response = await self._run_sync(self.fyers.get_profile)
            
            # Check if response is valid
            if isinstance(response, dict) and response.get("code") == 200:
                logger.info("_validate_token():Token Validated successfully")
                return True
            else:
                logger.warning(f"_validate_token():Token Validated failed: {response}")
                return False
            
        except Exception as e:
            logger.error(f"_validate_token():Error validating token: {str(e)}")
            return False
        
    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous function in a thread pool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, 
            functools.partial(func, *args, **kwargs)
        )        
    
    async def _update_nifty_symbol(self) -> bool:
        try:
            url = 'https://public.fyers.in/sym_details/NSE_FO.csv'
            df = pd.read_csv(url, header=None)
            df_filtered = df[df[9].str.startswith(f"NSE:NIFTY") & df[9].str.contains(f"FUT") & ~df[9].str.contains(f"NXT")]
            expiry_date = datetime.strptime(f"{df_filtered.iloc[0][1].split(" ")[3]} {df_filtered.iloc[0][1].split(" ")[2]} {datetime.now().year}", "%d %b %Y").date()
            if expiry_date != datetime.today().date():
                symbol = str(df_filtered.iloc[0][9])
            else:
                symbol = str(df_filtered.iloc[1][9])
            dotenv_path = find_dotenv() 
            set_key(dotenv_path, 'NIFTY_SYMBOL', symbol)
            logger.info(f"_update_nifty_symbol(): Setting Nifty Symbol: {symbol}")
            return True
        except Exception as e:
            logger.error(f"_update_nifty_symbol():Error validating token: {str(e)}")
            return False 
        
    async def _update_banknifty_symbol(self) -> bool:
        try:
            url = 'https://public.fyers.in/sym_details/NSE_FO.csv'
            df = pd.read_csv(url, header=None)
            df_filtered = df[df[9].str.startswith(f"NSE:BANKNIFTY") & df[9].str.contains(f"FUT") & ~df[9].str.contains(f"NXT")]
            expiry_date = datetime.strptime(f"{df_filtered.iloc[0][1].split(" ")[3]} {df_filtered.iloc[0][1].split(" ")[2]} {datetime.now().year}", "%d %b %Y").date()
            if expiry_date != datetime.today().date():
                symbol = str(df_filtered.iloc[0][9])
            else:
                symbol = str(df_filtered.iloc[1][9])
            dotenv_path = find_dotenv() 
            set_key(dotenv_path, 'BANKNIFTY_SYMBOL', symbol)
            logger.info(f"_update_banknifty_symbol(): Setting Nifty Symbol: {symbol}")
            return True
        except Exception as e:
            logger.error(f"_update_banknifty_symbol():Error validating token: {str(e)}")
            return False 
        
fyersClient = FyersClient()