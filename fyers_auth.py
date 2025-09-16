#!/usr/bin/env python3
"""
Fyers Authentication Script

This script takes an authentication URL as input, extracts the auth code,
and generates an access token which is then saved to the .env file.
"""

import os
import sys
from fyers_apiv3 import fyersModel
from dotenv import load_dotenv, set_key, find_dotenv

def main():
    # Load environment variables
    #dotenv_path = find_dotenv(filename="/mnt/LibertyFlow/LibertyFlow_v002/.env")
    dotenv_path = "/mnt/LibertyFlow/LibertyFlow_v002/.env"
    if not dotenv_path:
        print("Error: .env file not found at /mnt/LibertyFlow/LibertyFlow_v002/.env")
        sys.exit(1)
    
    load_dotenv(dotenv_path, override=True)
    
    # Get required credentials from environment variables
    client_id = os.getenv("FYERS_APP_ID")
    secret_key = os.getenv("FYERS_APP_SECRET")
    redirect_uri = os.getenv("FYERS_REDIRECT_URI")
    response_type = os.getenv("FYERS_RESPONSE_TYPE", "code")
    
    if not all([client_id, secret_key, redirect_uri]):
        print("Error: Missing required environment variables (FYERS_CLIENT_ID, FYERS_SECRET_KEY, FYERS_REDIRECT_URI)")
        sys.exit(1)
    
    # Get auth URL from command line or user input
    if len(sys.argv) > 1:
        authUrl = sys.argv[1]
    else:
        authUrl = input("Enter Auth Code URL: ")
    
    try:
        # Extract auth code from the URL
        auth_code = authUrl.split("auth_code=")[1].split("&state")[0]
        
        # Create session model
        session = fyersModel.SessionModel(
            client_id=client_id,
            secret_key=secret_key, 
            redirect_uri=redirect_uri, 
            response_type=response_type, 
            grant_type="authorization_code" 
        )
        session.set_token(auth_code)
        
        # Generate the access token using the authorization code
        response = session.generate_token()
        
        if 'access_token' not in response:
            print("Error generating token:", response)
            sys.exit(1)
            
        access_token = response['access_token']
        
        # Verify token works by getting profile
        fyers = fyersModel.FyersModel(
            client_id=client_id,
            token=access_token
        )
        profile = fyers.get_profile()
        print("Authentication successful!")
        print(f"Profile data: {profile}")
        
        # Save access token to .env file
        set_key(dotenv_path, 'FYERS_ACCESS_TOKEN', access_token)
        print(f"Access token saved to {dotenv_path}")
        
        return 0
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
