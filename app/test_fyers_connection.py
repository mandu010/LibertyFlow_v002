import os
import asyncio
import sys
import signal
import traceback
import requests
import pyotp
from urllib.parse import parse_qs, urlparse
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv, set_key, find_dotenv

from app.config import settings
from app.utils.logging import get_logger, setup_logging
from app.fyers.client import fyersClient
from app.slack import slack

# Global logger
logger = get_logger("FYERS_CLIENT_CONNECTION")

# Global flags for clean shutdown
shutdown_requested = False

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
    
    # Wait briefly for any pending async operations to complete
    await asyncio.sleep(1)
    
    logger.info("Shutdown complete")

async def main():
    """Main function"""
    setup_logging()
    
    try:
        await asyncio.sleep(2)  
        # Test Fyers client connection with new token
        logger.info("Testing Fyers client connection...")
        fyers = await fyersClient.connect()
        if fyers is not None:
            logger.info("Fyers client connection test successful")
            await slack.send_message("Fyers client connection verified")
        else:
            logger.warning("Fyers client connection test failed")
            await slack.send_message("WARNING: Fyers client connection test failed")
            return 1
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in main function: {e}\n{error_traceback}")
        await slack.send_message(f"CRITICAL ERROR: Fyers connection failed: {str(e)[:200]}")
        return 1

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
        error_traceback = traceback.format_exc()
        logger.error(f"Unhandled exception: {str(e)}\n{error_traceback}")
        try:
            asyncio.run(slack.send_message(f"FATAL ERROR: Fyers Connection Test crashed: {str(e)[:200]}"))
        except:
            pass
        sys.exit(1)
