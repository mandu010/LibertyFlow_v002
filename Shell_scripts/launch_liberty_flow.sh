#!/bin/bash

# Script to authenticate with Fyers API and run Liberty Flow application
# Designed to run from ~/root while accessing files in /mnt/LibertyFlow

# Define paths
LIBERTY_ENV="/mnt/LibertyFlow/LibertyFlowEnv"
LIBERTY_APP="/mnt/LibertyFlow/LibertyFlow_v002"
FYERS_AUTH_SCRIPT="${LIBERTY_APP}/fyers_auth.py"

# 1. Activate the Python virtual environment
source "${LIBERTY_ENV}/bin/activate"

# 2. Change directory to the Liberty Flow application folder
cd "${LIBERTY_APP}"

# 3. Run Fyers authentication script
if [ $# -eq 1 ]; then
    # If URL is provided as argument
    python3 "${FYERS_AUTH_SCRIPT}" "$1"
else
    # If no URL is provided, script will prompt for it
    python3 "${FYERS_AUTH_SCRIPT}"
fi

# Check if authentication was successful
if [ $? -ne 0 ]; then
    echo "Authentication failed. Exiting."
    exit 1
fi

echo "Authentication successful. Starting Liberty Flow application..."

# 4. Run the main application module
python3 -m app.main

# Add exit status message
if [ $? -eq 0 ]; then
    echo "Liberty Flow application executed successfully"
else
    echo "Liberty Flow application exited with an error code: $?"
fi

# Return to the original directory
cd /mnt/LibertyFlow/LibertyFlow_v002/logs
