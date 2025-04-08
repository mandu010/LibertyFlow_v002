import asyncio
import logging
import sys
import os
import signal

from app.config import settings
from app.utils.logging import get_logger
from app.utils.logging import setup_logging
from app.db.dbclass import db
from app.fyers.client import fyersClient
from app.nifty_tf.range import LibertyRange
from app.nifty_tf.trigger import LibertyTrigger



logger = get_logger("MAIN")


async def main():
    #global db, fyers_client
    
    # Setup logging first
    setup_logging()
    logger.info("Starting Liberty Flow...")
    
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
        range = LibertyRange(db, fyers)
        range_val = await range.read_range()
        if range_val is not None:
            await range.update_range(range_val)
        
        # Keep application running until interrupted
        logger.info("Application is now running. Press CTRL+C to exit.")
        
        # This is a simple way to keep the application running
        # Replace this with your actual application logic later
        while True:
            #await asyncio.sleep(60)
            #range = LibertyRange(db, fyers)
            await range.read_range()
            trigger = LibertyTrigger(db, fyers)
            await trigger.pct_trigger(range_val)
            await trigger.ATR(range_val)

            break
            
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