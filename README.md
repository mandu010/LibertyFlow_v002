# LibertyFlow_v002

# LibertyFlow v2 - Automated Trading System by Saurabh Mandlik
# Yes the README is fully written using AI, because WHY NOT?!
# Yes, I have fully designed and developed this.
## 📋 Table of Contents

- [Overview](#overview)
- [Key Highlights](#key-highlights)
- [Features](#features)
- [System Architecture](#system-architecture)
- [Installation](#installation)
- [Trading Strategy](#trading-strategy)
- [Project Structure](#project-structure)
- [Scripts](#scripts)

## 🎯 Overview

**LibertyFlow** is an advanced, fully automated algorithmic trading system designed for Indian equity markets (NSE). It implements sophisticated trading strategies for **NIFTY** and **Bank NIFTY** futures using real-time market data, technical analysis, and automated order execution through the Fyers API.

The system is built with Python using asynchronous programming (asyncio) for high performance, PostgreSQL for data persistence, and Slack for real-time notifications.

### Key Highlights

- **Automated Trading**: Complete end-to-end automation from signal generation to order execution
- **Multi-Strategy Support**: Implements Liberty Momentum and Liberty Flow strategies
- **Real-time Monitoring**: WebSocket-based live market data streaming
- **Risk Management**: Built-in stop-loss, trailing stop-loss, and position management
- **Slack Integration**: Real-time trade notifications and status updates
- **Database Persistence**: PostgreSQL for storing trade history, ranges, and strategy parameters
- **Holiday Handling**: Automatic market holiday detection and skip logic

## ✨ Features

### Trading Features
- ✅ **Multiple Trigger Mechanisms**: PCT trigger, ATR trigger, and Range trigger
- ✅ **Swing Formation Detection**: Automated swing high/low identification
- ✅ **Breakout Detection**: Real-time breakout monitoring with WebSocket
- ✅ **Dynamic Stop Loss**: Percentage-based SL with trailing functionality
- ✅ **Position Management**: Automatic entry and exit with order validation
- ✅ **Range Expansion**: Daily range update based on market behavior

### Technical Features
- ✅ **Async/Await Architecture**: High-performance asynchronous operations
- ✅ **WebSocket Streaming**: Real-time market data via Fyers WebSocket
- ✅ **Connection Pooling**: PostgreSQL connection pooling for efficiency
- ✅ **Token Management**: Automatic Fyers token generation and validation
- ✅ **Error Handling**: Comprehensive error handling and logging
- ✅ **Graceful Shutdown**: Signal handling for clean application termination

### Monitoring Features
- ✅ **Slack Notifications**: Real-time updates on trades and system status
- ✅ **Comprehensive Logging**: Detailed logging at multiple levels
- ✅ **Database Status Tracking**: Trade status and trigger status in DB
- ✅ **Shell Scripts**: Automation scripts for deployment and management

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     LibertyFlow System                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐    ┌─────────────┐  │
│  │   main.py    │─────▶│  Strategy    │───▶│    OMS      │  │
│  │  (Orchestr.) │      │   Engine     │    │  (Orders)   │  │
│  └──────────────┘      └──────────────┘    └─────────────┘  │
│         │                     │                     │        │
│         ▼                     ▼                     ▼        │
│  ┌──────────────┐      ┌──────────────┐    ┌─────────────┐ │
│  │   Database   │      │  Market Data │    │ Fyers API   │ │
│  │  PostgreSQL  │      │  WebSocket   │    │  Client     │ │
│  └──────────────┘      └──────────────┘    └─────────────┘ │
│         │                     │                     │        │
│         └─────────────────────┴─────────────────────┘        │
│                           │                                   │
│                           ▼                                   │
│                  ┌──────────────┐                            │
│                  │    Slack     │                            │
│                  │ Notifications│                            │
│                  └──────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

1. **Main Controller** (`app/main.py`): Orchestrates the entire trading workflow
2. **Strategy Engine** (`app/nifty_tf/`): Implements trading logic and signals
3. **Database Layer** (`app/db/`): Handles all PostgreSQL operations
4. **Fyers Client** (`app/fyers/`): Manages broker API interactions
5. **Order Management** (`app/fyers/oms/`): Executes and tracks orders
6. **Slack Notifier** (`app/slack/`): Sends real-time notifications
7. **Utilities** (`app/utils/`): Logging and helper functions


### API Accounts
- **Fyers Trading Account**: 
- **Slack Workspace**: For notifications (optional but recommended)


### Fyers Token Generation

Before running the system, generate an access token:

```bash
# 1. Generate authorization URL (visit in browser)
python generate_token.py

# 2. After authentication, use the redirect URL with fyers_auth.py
python fyers_auth.py "https://localhost?auth_code=YOUR_AUTH_CODE&state=sample"
```

## 🎮 Usage

### Basic Usage

```bash
# Activate virtual environment
source venv/bin/activate

# Run the main application
python -m app.main
```

### Using Shell Scripts

```bash
# Launch Liberty Flow for NIFTY
./Shell_scripts/launch_liberty_flow.sh

# Launch Liberty Momentum for Bank NIFTY
./Shell_scripts/launch_liberty_momentum_bnf.sh

# Update NIFTY range
./Shell_scripts/update_range.sh

# Update Bank NIFTY range
./Shell_scripts/update_bnf_range.sh

# Exit all positions
./Shell_scripts/exit_positions.sh

# Kill running processes
./Shell_scripts/kill_main_app.sh
```

### Running Specific Components

```bash
# Test Fyers connection
python -m app.test_fyers_connection

# Update range manually
python -m app.range_update

# Exit positions manually
python -m app.exit_positions

# Generate new token
python -m app.generate_token
```

## 📊 Trading Strategy

### Liberty Flow Strategy

The Liberty Flow strategy follows a systematic approach:

#### 1. **Trigger Phase** (9:15 AM - 12:25 AM)
   - **PCT Trigger**: Checks if price moves beyond a percentage threshold
   - **ATR Trigger**: Uses Average True Range for volatility-based trigger
   - **Range Trigger**: Monitors if price breaks out of defined range

#### 2. **Swing Formation Phase**
   - Identifies Swing High (SWH) and Swing Low (SWL)
   - Uses 5-minute candle patterns
   - Validates swing formation criteria

#### 3. **Breakout Detection Phase**
   - Monitors for breakout above SWH (bullish) or below SWL (bearish)
   - Uses WebSocket for real-time price updates
   - Confirms breakout with volume and momentum

#### 4. **Order Execution**
   - Places limit order in breakout direction
   - Sets stop-loss based on configured percentage
   - Implements trailing stop-loss

#### 5. **Position Management**
   - Monitors position until exit conditions
   - Trails stop-loss as price moves favorably
   - Auto-exits at 3:13 PM if position still open

### Risk Management

- **Stop Loss**: Dynamic SL based on entry price (default 0.3%)
- **Trailing SL**: Adjusts SL as price moves in favorable direction
- **Position Sizing**: Controlled by lot size configuration
- **Time-based Exit**: Automatic square-off before market close
- **Holiday Detection**: Skips trading on market holidays

## 📁 Project Structure

### Complete App Directory Tree

```
app/
├── __init__.py                      # Package initialization
├── config.py                        # Configuration management (Pydantic settings)
├── main.py                          # Main application entry point
├── main_bkp.py                      # Backup of main file
├── generate_token.py                # Fyers token generation utility
├── test_fyers_connection.py         # Connection testing utility
├── exit_positions.py                # Position exit utility
├── range_update.py                  # NIFTY range update script
├── range_update_bnf.py              # Bank NIFTY range update script
├── LibertyMomentum_BNF.py          # Bank NIFTY momentum strategy
│
├── db/                              # Database layer
│   ├── __init__.py
│   └── dbclass.py                   # PostgreSQL connection pool & queries
│
├── fyers/                           # Fyers broker integration
│   ├── __init__.py
│   ├── client.py                    # Fyers API client wrapper
│   ├── handlers.py                  # API response handlers
│   └── oms/                         # Order Management System
│       ├── __init__.py
│       └── nifty_tf_oms.py         # NIFTY order execution logic
│
├── nifty_tf/                        # Trading strategy modules
│   ├── __init__.py
│   ├── strategy_main.py             # Main strategy orchestrator (NIFTY)
│   ├── strategy_main_original.py   # Original strategy backup
│   ├── strategy_main_test.py       # Testing version
│   ├── range.py                     # Range calculation & update (NIFTY)
│   ├── range_bnf.py                 # Range calculation (Bank NIFTY)
│   ├── trigger.py                   # Trigger detection logic (NIFTY)
│   ├── trigger2.py                  # Alternative trigger logic
│   ├── trigger_bkp.py               # Trigger backup
│   ├── trigger_bkp2.py              # Trigger backup 2
│   ├── trigger2_bnf.py              # Bank NIFTY trigger
│   ├── swingFormation.py            # Swing high/low detection (NIFTY)
│   ├── swingFormation2.py           # Alternative swing logic
│   ├── swingFormation_bnf.py        # Bank NIFTY swing formation
│   ├── breakout.py                  # Breakout detection (NIFTY)
│   ├── breakout_bnf.py              # Bank NIFTY breakout
│   ├── market_data.py               # Market data fetching (NIFTY)
│   ├── market_data_bnf.py           # Bank NIFTY market data
│   ├── trail.py                     # Trailing stop-loss logic
│   └── libertymomentum_bnf_strategy_main.py  # Bank NIFTY momentum main
│
├── slack/                           # Slack integration
│   ├── __init__.py
│   ├── client.py                    # Async Slack client
│   ├── handlers.py                  # Message handlers
│   └── helpers.py                   # Helper functions
│
├── upstox/                          # Upstox broker integration (alternative) #To be used for getting Greeks from Upstox later on
│   ├── __init__.py
│   └── client.py                    # Upstox API client
│
├── utils/                           # Utility modules
│   ├── __init__.py
│   ├── logging.py                   # Logging configuration
│   └── logging_bkp.py               # Logging backup
│
├── functions/                       # Internal helper functions
│   ├── __init__.py
│   └── internal.py                  # Common internal functions
│
└── sql/                             # SQL scripts
    ├── insert.sql                   # Data insertion scripts
    └── insert_date_trigger_status.sql  # Trigger status initialization
```

### Root Directory Structure

```
LibertyFlow_v002-main/
├── README.md                        # This file
├── requirements.txt                 # Python dependencies
├── Tree                             # Tree structure file
├── fyers_auth.py                    # Fyers authentication script
├── upstox_auth.py                   # Upstox authentication script
├── .env                             # Environment variables (create this)
├── .env.example                     # Environment template
├── app/                             # Main application package (see above)
└── Shell_scripts/                   # Automation scripts
    ├── chrome_install.sh            # Chrome installation for auth
    ├── kill_chrome.sh               # Kill Chrome processes
    ├── kill_jupyter.sh              # Kill Jupyter processes
    ├── kill_main_app.sh             # Kill main app processes
    ├── kill_unattended_python.sh    # Kill orphan Python processes
    ├── kill_vs_servers.sh           # Kill VS Code servers
    ├── launch_liberty_flow.sh       # Launch NIFTY strategy
    ├── launch_liberty_flow_2.sh     # Alternative launcher
    ├── launch_liberty_momentum_bnf.sh  # Launch Bank NIFTY strategy
    ├── update_range.sh              # Update NIFTY range
    ├── update_bnf_range.sh          # Update Bank NIFTY range
    └── exit_positions.sh            # Exit all positions
```

## 🔔 Monitoring & Notifications

### Slack Integration

The system sends real-time notifications for:
- ✅ System startup/shutdown
- ✅ Trigger activation (PCT/ATR/Range)
- ✅ Swing formation detection
- ✅ Breakout events
- ✅ Order placement/execution
- ✅ Stop-loss hits
- ✅ Position exits
- ✅ Errors and warnings

## 🛠️ Scripts

### Shell Scripts Documentation

| Script | Purpose |
|--------|---------|
| `launch_liberty_flow.sh` | Start NIFTY Liberty Flow strategy | # Scheduled via Cron for 8.45 AM
| `launch_liberty_momentum_bnf.sh` | Start Bank NIFTY momentum strategy | # Scheduled via Cron for 8.50 AM
| `update_range.sh` | Update NIFTY trading range | # Scheduled via Cron for 4.00 PM
| `update_bnf_range.sh` | Update Bank NIFTY trading range | # Scheduled via Cron for 4.00 PM
| `exit_positions.sh` | Emergency exit all open positions | # Scheduled via Cron for 3.13 PM
| `kill_main_app.sh` | Stop running strategy processes | # As-n-when required
| `kill_unattended_python.sh` | Clean up zombie Python processes | # Runs EOD daily
| `chrome_install.sh` | Install Chrome for auth automation | # No longer used
