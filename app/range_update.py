import asyncio
import sys
import signal
import os
from dotenv import load_dotenv, set_key, find_dotenv
from datetime import date

from app.utils.logging import get_logger
from app.utils.logging import setup_logging
from app.db.dbclass import db
from app.fyers.client import fyersClient
from app.nifty_tf.strategy_main import LibertyFlow
from app.nifty_tf.range import LibertyRange
from app.slack import slack

logger = get_logger("RANGE_UPDATE")

def today_holiday():
    """
    Check if today's date is a holiday.
    Returns 0 if today matches any of the specified holiday dates.
    """
    # List of holiday dates
    holiday_dates = [
        date(2026, 1, 15),   # 15-Jan-2026 Municipal Corporation Holiday
        date(2026, 1, 26),   # 26-Jan-2026
        date(2026, 3, 3),    # 03-Mar-2026
        date(2026, 3, 26),   # 26-Mar-2026
        date(2026, 3, 31),   # 31-Mar-2026
        date(2026, 4, 3),    # 03-Apr-2026
        date(2026, 4, 14),   # 14-Apr-2026
        date(2026, 5, 1),    # 01-May-2026
        date(2026, 5, 28),   # 28-May-2026
        date(2026, 6, 26),   # 26-Jun-2026
        date(2026, 9, 14),   # 14-Sep-2026
        date(2026, 10, 2),   # 02-Oct-2026
        date(2026, 10, 20),  # 20-Oct-2026
        date(2026, 11, 10),  # 10-Nov-2026
        date(2026, 11, 24),  # 24-Nov-2026
        date(2026, 12, 25),  # 25-Dec-2026
    ]
    today = date.today()
    return today in holiday_dates

async def main():
    # Setup logging first
    setup_logging()
    logger.info("Updating Range for the Day")
    asyncio.create_task(slack.send_message("Updating Range for the Day"))
    
    try:
        if today_holiday():
            logger.info("Today is a holiday. Skipping trading session.")
            await slack.send_message("Today is a holiday.")
            return 0        
        # Initialize database connection
        logger.info("Connecting to database...")
        await db.connect()
        logger.info("Database connection established")
        
        # Initialize Fyers client
        logger.info("Initializing Fyers client...")
        fyers = await fyersClient.connect()
        if fyers is not None:
            print("Fyers client connected successfully")
            logger.info("Fyers client initialized")
        else:
            logger.error("Fyers client initialization failed")
            return 1
        
        # Initializing & Running Strategy
        range = LibertyRange(db, fyers)
        range_val = await range.read_range()
        print(range_val)
        if range_val is not None:
            await range.update_range(range_val)       
                 
        # dotenv_path = find_dotenv(filename="/mnt/LibertyFlow/LibertyFlow_v002/.env")
        dotenv_path = "/mnt/LibertyFlow/LibertyFlow_v002/.env"
        load_dotenv(dotenv_path, override=True)       
        set_key(dotenv_path, 'NIFTY_BUY_SYMBOL', "")
        set_key(dotenv_path, 'NIFTY_SELL_SYMBOL', "")
        logger.info("Cleared Nifty Buy and Sell Symbols")
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        return 1

    return 0 

if __name__ == "__main__":
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: asyncio.create_task(shutdown(s.name)))
    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}", exc_info=True)
        sys.exit(1)