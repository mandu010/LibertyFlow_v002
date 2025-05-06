import asyncio
import functools
import os
from dotenv import set_key, find_dotenv
from datetime import datetime
import pandas as pd

from app.config import settings
from app.utils.logging import get_logger
from app.db.dbclass import db

from Upstox_apiv3 import UpstoxModel
from app.config import settings

logger = get_logger("UpstoxClient")

class UpstoxClient:
    def __init__(self):
        self.client_id = settings.upstox.UPSTOX_APP_ID
        self.secret_key = settings.upstox.UPSTOX_APP_SECRET
        self.access_token = settings.upstox.UPSTOX_ACCESS_TOKEN

    async def connect(self):
        logger.info("connect():Initializing Upstox client...")
        try:
            # Initialize the Upstox client with the provided credentials
            logger.info("connect():Upstox client initialized successfully")
            
        except Exception as e:
            logger.error(f"connect():Error initializing Upstox client: {e}", exc_info=True)