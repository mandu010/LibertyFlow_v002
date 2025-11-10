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

# 3. Run the main application module
python3 -m app.range_update_bnf