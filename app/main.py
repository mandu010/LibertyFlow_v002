import asyncio
import sys
import traceback
from datetime import date

from app.utils.logging import setup_logging, get_logger
import signal
from app.db.dbclass import db
from app.fyers.client import fyersClient
from app.nifty_tf.strategy_main import LibertyFlow
#from app.nifty_tf.strategy_main_test import LibertyFlow
from app.slack import slack

# global logger
logger = get_logger("MAIN")

# Global flags for clean shutdown
shutdown_requested = False
strategy = None  # Global reference to allow proper cleanup

async def shutdown(signal_name=None):
    """Gracefully shut down the application"""
    global shutdown_requested
    
    if shutdown_requested:
        logger.warning("Shutdown already in progress, ignoring repeated signal")
        return
        
    shutdown_requested = True
    
    if signal_name:
        logger.info(f"Received {signal_name}, initiating shutdown")
    else:
        logger.info("Initiating shutdown")
    
    await slack.send_message("Liberty Flow shutting down...")
    
    # Cleanup strategy if it exists
    if strategy is not None:
        logger.info("Stopping strategy...")
        # Strategy already handles DB closing, so we don't need to close it again here
    
    # Wait briefly for any pending async operations to complete
    await asyncio.sleep(1)
    
    logger.info("Shutdown complete")

def today_holiday():
    """
    Check if today's date is a holiday.
    Returns 0 if today matches any of the specified holiday dates.
    """
    # List of holiday dates
    holiday_dates = [
        date(2025, 2, 26),   # 26-Feb-2025
        date(2025, 3, 14),   # 14-Mar-2025
        date(2025, 3, 31),   # 31-Mar-2025
        date(2025, 4, 10),   # 10-Apr-2025
        date(2025, 4, 14),   # 14-Apr-2025
        date(2025, 4, 18),   # 18-Apr-2025
        date(2025, 5, 1),    # 01-May-2025
        date(2025, 8, 15),   # 15-Aug-2025
        date(2025, 8, 27),   # 27-Aug-2025
        date(2025, 10, 2),   # 02-Oct-2025
        date(2025, 10, 21),  # 21-Oct-2025
        date(2025, 10, 22),  # 22-Oct-2025
        date(2025, 11, 5),   # 05-Nov-2025
        date(2025, 12, 25),  # 25-Dec-2025
    ]
    today = date.today()
    return today in holiday_dates    

async def main():
    # Setup logging first
    global strategy
    setup_logging()
    logger.info("Starting Liberty Flow...")
    asyncio.create_task(slack.send_message("Starting Liberty Flow..."))
    
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
        if fyers is None:
            logger.error("Fyers client initialization failed")
            await slack.send_message("ERROR: Fyers client initialization failed. Exiting.")
            await db.close()
            return 1
        
        logger.info("Fyers client initialized")

        # Initializing & Running Strategy
        strategy = LibertyFlow(db, fyers)        
        result = await strategy.run()   

        # Check result and log appropriately
        if result == 1:
            logger.warning("Strategy execution completed with warnings")
        else:
            logger.info("Strategy execution completed successfully")
            
        await slack.send_message("Liberty Flow execution completed")        

        # Returning exit code based on strategy result
        return 0 if result != 1 else 1
            
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in main function: {e}\n{error_traceback}")
        await slack.send_message(f"CRITICAL ERROR: Application failed: {str(e)[:200]}")
        return 1


if __name__ == "__main__":
    # FIXED: Proper signal handler that works with asyncio
    def signal_handler(signum, frame):
        """Handle shutdown signals properly"""
        try:
            sig_name = signal.Signals(signum).name
        except (ValueError, AttributeError):
            sig_name = f"Signal-{signum}"
        
        # Get the current event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(shutdown(sig_name))
            else:
                logger.info(f"Received {sig_name} but loop not running")
                sys.exit(0)
        except Exception as e:
            logger.error(f"Error in signal handler: {e}")
            sys.exit(1)
    
    # Set up signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal_handler)    
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Unhandled exception: {str(e)}\n{error_traceback}")
        try:
            asyncio.run(slack.send_message(f"FATAL ERROR: Application crashed: {str(e)[:200]}"))
        except:
            pass        
        sys.exit(1)