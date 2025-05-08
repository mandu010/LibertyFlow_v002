import asyncio
import sys

from app.utils.logging import get_logger
import signal
from app.utils.logging import setup_logging
from app.db.dbclass import db
from app.fyers.client import fyersClient
from app.nifty_tf.strategy_main import LibertyFlow
from app.nifty_tf.range import LibertyRange
from app.slack import slack
from app.fyers.oms.nifty_tf_oms import Nifty_OMS


logger = get_logger("EXIT POSITION MAIN")

async def main():
    # Setup logging first
    setup_logging()
    logger.info("Exiting Positions for the Day")
    asyncio.create_task(slack.send_message("Exiting Positions for the Day"))
    
    try:
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
        place_order = Nifty_OMS(db, fyers)
        await place_order.exit_position()
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