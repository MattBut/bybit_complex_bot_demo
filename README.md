# bybit_complex_bot_demo
Trading bot with  EMA strategy could be used as framework to  different strategies analysing 

🤖 CRYPTO TRADING SIMULATOR BOT: INSTALLATION & USAGE GUIDE

SECTION 1: PREREQUISITES AND SETUP

1.1. SYSTEM REQUIREMENTS

Python 3.9+ (Installed).

Bybit API Key/Secret (Required for data fetching).

Reliable internet connection.

1.2. INSTALLATION STEPS

1. Clone the Repository:

Bash

git clone https://github.com/YourUsername/your-repo-name.git
cd your-repo-name

2. Create & Activate Virtual Environment:

Bash

python3 -m venv venv
source venv/bin/activate

3. Install All Dependencies:

Bash

pip install pandas pandas-ta numpy python-dotenv pybit openpyxl

4. Place Indicator Files: Crucially, ensure indicator files (e.g., ema_indicator.py) are located in the /indicators/ subdirectory.

1.3. API CONFIGURATION (.env file)

Create a file named .env in the ROOT DIRECTORY for secure key management:

Ini, TOML

# .env file content
BYBIT_API_KEY="YOUR_BYBIT_API_KEY"
BYBIT_API_SECRET="YOUR_BYBIT_API_SECRET"
SECTION 2: BOT CONFIGURATION (main.py)
All trading logic and risk parameters are set in main.py.

2.1. GLOBAL TRADING SETTINGS

Active Strategy: STRATEGY_TYPE is set to 1 (EMA Indicator).

RISK PER TRADE: RISK_PER_TRADE_USDT is set to 1.0 USDT (CRITICAL: Maximum loss allowed per trade).

Trading Mode: TRADING_MODE is set to 2 (Both LONG and SHORT).

Liquidity Filter: MIN_VOLUME_24H is set to 150,000,000 (Minimum 24h volume for trading pairs).

2.2. STRATEGY PARAMETERS (EMA Example)

These settings define the exit levels and technical analysis periods (EMA_PARAMS):

Stop Loss %: SL_PERCENT is 0.8.

Take Profit %: TP_PERCENT is 1.0.

Fast/Slow EMA: Lengths are 10 / 20.

Interval: KLINE_INTERVAL is '60' (60 minutes).

SECTION 3: EXECUTION AND ACCOUNTING

3.1. RUNNING THE BOT

Start the main trading loop from your activated virtual environment:

Bash

source venv/bin/activate
python main.py

3.2. ACCOUNTING LOGS

The bot manages persistent data in the root directory:

balance.txt: Stores the current floating simulation balance.

trade_history.xlsx: Detailed log of all closed trades (PnL, entry/exit data). Requires openpyxl.

⚠️ TROUBLESHOOTING

"Strategy is not implemented" Error: Verify STRATEGY_TYPE in main.py is set to 1.

API Errors: Check your keys in .env for correctness and valid permissions.

Missing Logs: Ensure openpyxl is installed (pip install openpyxl).
