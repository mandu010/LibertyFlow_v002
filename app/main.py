import asyncio
import sys

from app.utils.logging import get_logger
import signal
from app.utils.logging import setup_logging
from app.db.dbclass import db
from app.fyers.client import fyersClient
#from app.nifty_tf.strategy_main import LibertyFlow
from app.nifty_tf.strategy_main_test import LibertyFlow

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
        #await fyersClient.connect()
        #if (await fyersClient.connect()) is not None:
        if fyers is not None:
            print("Fyers client connected successfully")
            logger.info("Fyers client initialized")
        else:
            logger.error("Fyers client initialization failed")
            return 1
        
        # Initialize Strategy
        strategy = LibertyFlow(db, fyers)

        # Keep application running until interrupted
        logger.info("Application is now running. Press CTRL+C to exit.")
        
        # This is a simple way to keep the application running
        # Replace this with your actual application logic later
        await strategy.run()   
            
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}", exc_info=True)
        return 1

    print("About to exit")
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