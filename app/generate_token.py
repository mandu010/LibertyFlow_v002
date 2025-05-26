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
logger = get_logger("GENERATE_TOKEN")

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
    
    await slack.send_message("Token generation shutting down...")
    
    # Wait briefly for any pending async operations to complete
    await asyncio.sleep(1)
    
    logger.info("Shutdown complete")

def send_login_otp(fy_id, app_id):
    """Send login OTP to Fyers"""
    base_url = "https://api-t2.fyers.in/vagator/v2"
    url = f"{base_url}/send_login_otp"
    resp = requests.post(url, json={"fy_id": fy_id, "app_id": app_id})
    resp.raise_for_status()
    return resp.json()["request_key"]

def generate_totp(secret):
    """Generate TOTP using secret"""
    return pyotp.TOTP(secret).now()

def verify_totp(request_key, otp):
    """Verify TOTP with Fyers"""
    base_url = "https://api-t2.fyers.in/vagator/v2"
    url = f"{base_url}/verify_otp"
    resp = requests.post(url, json={"request_key": request_key, "otp": otp})
    resp.raise_for_status()
    return resp.json()["request_key"]

def verify_pin(request_key, pin):
    """Verify PIN with Fyers"""
    base_url = "https://api-t2.fyers.in/vagator/v2"
    url = f"{base_url}/verify_pin"
    payload = {"request_key": request_key, "identity_type": "pin", "identifier": pin}
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    print(resp.json()["data"]["access_token"])
    return resp.json()["data"]["access_token"]

def fetch_auth_code(fy_id, app_id, app_type, redirect_uri, trade_token):
    """Fetch authorization code from Fyers"""
    url = "https://api-t1.fyers.in/api/v3/token"
    payload = {
        "fyers_id": fy_id,
        "app_id": app_id,
        "redirect_uri": redirect_uri,
        "appType": app_type,
        "code_challenge": "",
        "state": "state123",
        "scope": "",
        "nonce": "",
        "response_type": "code",
        "create_cookie": True
    }
    headers = {"Authorization": f"Bearer {trade_token}"}
    resp = requests.post(url, json=payload, headers=headers, allow_redirects=False)
    
    if resp.status_code not in (200, 308):
        logger.error(f"Token exchange error: {resp.status_code} {resp.text}")
        resp.raise_for_status()
    
    redirect_url = resp.json().get("Url") or resp.json().get("url")
    return parse_qs(urlparse(redirect_url).query)["auth_code"][0]

async def generate_access_token():
    """Generate Fyers access token"""
    try:
        # Load environment variables
        dotenv_path = find_dotenv(filename="/mnt/LibertyFlow/LibertyFlow_v002/.env")
        load_dotenv(dotenv_path)
        
        # Get configuration
        APP_ID_FULL = settings.fyers.CLIENT_ID
        SECRET_KEY = settings.fyers.SECRET_KEY
        REDIRECT_URI = settings.fyers.REDIRECT_URI
        FYERS_ID = settings.fyers.FYERS_USERNAME
        TOTP_SECRET = settings.fyers.FYERS_2FA
        PIN = settings.fyers.FYERS_PIN
        client_id = os.getenv("FYERS_APP_ID")
        secret_key = os.getenv("FYERS_APP_SECRET")
        redirect_uri = os.getenv("FYERS_REDIRECT_URI")
        response_type = os.getenv("FYERS_RESPONSE_TYPE", "code")        
        grant_type = "authorization_code"
        
        # Validate required environment variables
        if not all([APP_ID_FULL, SECRET_KEY, REDIRECT_URI, FYERS_ID, TOTP_SECRET, PIN]):
            logger.error("Error: All FYERS environment variables must be set")
            return False
        
        APP_ID, APP_TYPE = APP_ID_FULL.split("-")
        WEB_APP_ID_TYPE = "2"
        
        logger.info("Starting token generation process...")
        
        # Step 1: Send login OTP  
        logger.info("Sending login OTP...")
        request_key_1 = send_login_otp(FYERS_ID, WEB_APP_ID_TYPE)
        logger.info("OTP sent successfully")
        
        # Step 2: Generate and verify TOTP
        logger.info("Generating and verifying TOTP...")
        totp = generate_totp(TOTP_SECRET)
        request_key_2 = verify_totp(request_key_1, totp)
        logger.info("TOTP verified successfully")
        
        # Step 3: Verify PIN to get trade access token
        logger.info("Verifying PIN...")
        trade_token = verify_pin(request_key_2, PIN)
        logger.info("PIN verified successfully")
        
        # Step 4: Fetch OAuth authorization code
        logger.info("Fetching authorization code...")
        auth_code = fetch_auth_code(FYERS_ID, APP_ID, APP_TYPE, REDIRECT_URI, trade_token)
        logger.info("Authorization code obtained successfully")
        
        # Step 5: Exchange auth code for API access token using Fyers SDK
        logger.info("Generating API access token...")
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key, 
            redirect_uri=redirect_uri, 
            response_type=response_type, 
            grant_type=grant_type
        )
        session.set_token(auth_code)
        token_response = session.generate_token()
        if token_response.get("s") == "ERROR":
            logger.error(f"Token generation failed: {token_response}")
            return False
        
        # Step 6: Save access token to environment file
        access_token = token_response.get("access_token")
        set_key(dotenv_path, 'FYERS_ACCESS_TOKEN', access_token)
        
        logger.info("Access token generated and saved successfully")
        return True
        
    except requests.HTTPError as e:
        logger.error(f"HTTP error during token generation: {e}")
        return False
    except Exception as e:
        logger.error(f"Error generating access token: {e}", exc_info=True)
        return False

async def main():
    """Main function"""
    setup_logging()
    logger.info("Starting Access Token Generation...")
    await slack.send_message("Starting Access Token Generation...")
    
    try:
        # Generate access token
        success = await generate_access_token()
        
        if success:
            await asyncio.sleep(2)  
            logger.info("Access token generation completed successfully")
            await slack.send_message("Access token generated successfully")
            logger.info("Importing Settings Module again to reload Env")
            return 0
        else:
            logger.error("Access token generation failed")
            await slack.send_message("ERROR: Access token generation failed")
            return 1
            
    except Exception as e:
        error_traceback = traceback.format_exc()
        logger.error(f"Error in main function: {e}\n{error_traceback}")
        await slack.send_message(f"CRITICAL ERROR: Token generation failed: {str(e)[:200]}")
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
            asyncio.run(slack.send_message(f"FATAL ERROR: Token generation crashed: {str(e)[:200]}"))
        except:
            pass
        sys.exit(1)
