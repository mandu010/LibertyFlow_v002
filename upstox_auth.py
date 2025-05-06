#!/usr/bin/env python3
"""
Fyers Authentication Script

This script takes an authentication URL as input, extracts the auth code,
and generates an access token which is then saved to the .env file.
"""

import os
import sys
import requests
import json
import asyncio
from dotenv import load_dotenv, set_key, find_dotenv

from app.slack import slack

async def main():
    # Load environment variables
    dotenv_path = find_dotenv(filename="/mnt/LibertyFlow/LibertyFlow_v002/.env")
    if not dotenv_path:
        print("Error: .env file not found at /mnt/LibertyFlow/LibertyFlow_v002/.env")
        sys.exit(1)
    
    load_dotenv(dotenv_path)
    
    # Get required credentials from environment variables
    client_id = os.getenv("UPSTOX_APP_ID")
    secret_key = os.getenv("UPSTOX_APP_SECRET")
    redirect_uri = os.getenv("UPSTOX_REDIRECT_URI")
    response_type = os.getenv("FYERS_RESPONSE_TYPE", "authorization_code")
    
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
        auth_code = authUrl.split("code=")[1].split("&state")[0]
        
        # Get Access token
        url = "https://api.upstox.com/v2/login/authorization/token"
        payload=f'client_id={client_id}&client_secret={secret_key}&redirect_uri=https%3A%2F%2F127.0.0.1%2F&grant_type=authorization_code&code={auth_code}'
        headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)
        access_token = response.json().get("access_token")

        access_token1 = f'Bearer {access_token}'
        url = 'https://api.upstox.com/v2/user/profile'
        headers = {
            'Accept': 'application/json',
            'Authorization': access_token1
        }
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            profile="get Profile from upstox"
            print("Authentication successful!")
            print(f"Profile data: {profile}")
        
        # Save access token to .env file
        set_key(dotenv_path, 'UPSTOX_ACCESS_TOKEN', access_token)
        print(f"Access token saved to {dotenv_path}")
        await slack.send_message("upstox_auth: Successfully Generated Access Token")

        return 0
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
