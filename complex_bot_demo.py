import pandas as pd
import pandas_ta as ta
import time as tm
import numpy as np
import os
from dotenv import load_dotenv
from pybit.unified_trading import HTTP
# import requests удален

# =========================================================================
# === INDICATOR IMPORTS BLOCK ===
# -------------------------------------------------------------------------
# =========================================================================
from indicators.ema_indicator import EmaIndicator


# =========================================================================
# === MAIN SETTINGS (CONFIGURATION) ===
# -------------------------------------------------------------------------
# =========================================================================

# --- ⚙️ ACTIVE STRATEGY SELECTION ---
# Только EMA Indicator (ID 1)
# -------------------------------------------------------------------------
# 1 = EMA Indicator (Trend Following)
STRATEGY_TYPE = 1 # ( EMA: 1)

# Ensure you have openpyxl installed to work with Excel: pip install openpyxl
load_dotenv() # Load environment variables from .env

# --- 💰 RISK AND BALANCE MANAGEMENT ---
DEFAULT_BALANCE = 10000 
RISK_PER_TRADE_USDT = 1.0 # <--- Maximum risk in USDT per trade
TRADING_MODE = 2 # <--- 0=LONG ONLY, 1=SHORT ONLY, 2=BOTH (LONG & SHORT)

# --- BYBIT FEES ---
TAKER_FEE_PERCENT = 0.055
MAKER_FEE_PERCENT = -0.025
ENTRY_FEE_TYPE = 'TAKER' 

# --- LIQUIDITY FILTERS (FUTURES / LINEAR) ---
MIN_VOLUME_24H = 150000000  
MAX_VOLUME_24H = 1000000000000 

# --- RETRY MECHANISM ---
MAX_RETRIES = 3 
RETRY_DELAY = 1 

# =========================================================================
# === 🛠️ UNIFIED PARAMETERS MAP FOR ALL INDICATORS (PARAMS_MAP) ===
# =========================================================================

# BASE LIQUIDITY PARAMETERS
BASE_PARAMS = {'MIN_VOLUME_24H': MIN_VOLUME_24H, 'MAX_VOLUME_24H': MAX_VOLUME_24H}

# 1: EMA Indicator
EMA_PARAMS = {**BASE_PARAMS, 'SL_PERCENT': 0.8, 'TP_PERCENT': 1.0, 'EMA_FAST_LENGTH': 10, 'EMA_SLOW_LENGTH': 20, 'KLINE_LIMIT': 200, 'CATEGORY': 'linear', 'KLINE_INTERVAL': '60'}

# =========================================================================
# === FUNCTION: CALCULATE VOLUME BASED ON RISK ===
# =========================================================================

def calculate_volume_from_risk(risk_usdt, entry_price, sl_percent):
    """
    Calculates the asset volume (in coins) based on the specified risk, 
    entry price, and stop-loss percentage.
    """
    if entry_price == 0 or sl_percent == 0:
        return 0
    
    # 1. Calculate the acceptable price loss (as a percentage of the price)
    risk_percent_factor = sl_percent / 100.0
    
    # 2. Calculate the acceptable price loss per coin
    price_risk_amount = entry_price * risk_percent_factor
    
    # 3. Volume = Total risk in USDT / Price loss per coin
    volume = risk_usdt / price_risk_amount
    
    # Add a small buffer to avoid exceeding the limit
    return volume * 0.999 

# =========================================================================
# === CLASS: TradingSimulator (Execution and Accounting Simulator) ===
# =========================================================================

class TradingSimulator:
    
    def __init__(self, test_net=False):
        self.balance_file = 'balance.txt'
        self.history_file = 'trade_history.xlsx'
        self.balance = self.load_balance()
        self.active_trade = {}
        # Loading API keys from .env file
        BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
        BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
        # Initializing the Bybit client
        self.client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, testnet=test_net)

    # --- Balance and Log Management Methods ---
    
    def load_balance(self):
        # Loads the balance from balance.txt or uses DEFAULT_BALANCE
        if os.path.exists(self.balance_file):
            with open(self.balance_file, 'r') as f:
                try:
                    balance = float(f.read())
                    print(f"Balance loaded from file: {balance:.2f} USDT")
                    return balance
                except (ValueError, FileNotFoundError):
                    print("Error reading balance file. Using default initial balance.")
                    self.save_balance(DEFAULT_BALANCE)
                    return DEFAULT_BALANCE
        else:
            print(f"Balance file not found. Creating file and using initial balance: {DEFAULT_BALANCE:.2f} USDT")
            self.save_balance(DEFAULT_BALANCE)
            return DEFAULT_BALANCE

    def save_balance(self, new_balance):
        # Saves the current balance to the file
        with open(self.balance_file, 'w') as f:
            f.write(str(new_balance))

    # --- Price Fetching Method ---
    
    def get_current_price(self, symbol, category):
        # Gets the latest price for the given symbol and category (linear/spot)
        for attempt in range(MAX_RETRIES):
            try:
                # ... (API price fetching code) ...
                response = self.client.get_tickers(category=category, symbol=symbol)
                
                if response['retCode'] == 0:
                    data_list = response['result']['list']
                    
                    if data_list:
                        return float(data_list[0]['lastPrice'])
                    else:
                        print(f"⚠️ Attempt {attempt + 1}: API returned an empty ticker list for {symbol}.")
                else:
                    print(f"❌ Attempt {attempt + 1}: Bybit API error ({response['retCode']}): {response.get('retMsg', 'No message')}")
                
            except Exception as e:
                print(f"🛑 Attempt {attempt + 1}: Critical error fetching price for {symbol}: {e}")

            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY * (2 ** attempt) 
                print(f"--> Waiting {delay}s before retry...")
                tm.sleep(delay)
        return None

    # --- Position Opening and Closing Methods ---
    
    def open_position(self, symbol, side, entry_price, volume, category):
        # Records the open position data in active_trade
        self.active_trade = {
            'symbol': symbol,
            'side': side,
            'entry_price': entry_price,
            'volume': volume,
            'status': 'OPEN',
            'timestamp_open': pd.Timestamp.now(),
            'category': category
        }
        
        # Accounting for entry fee
        fee_rate = TAKER_FEE_PERCENT if ENTRY_FEE_TYPE == 'TAKER' else MAKER_FEE_PERCENT
        trade_cost_usdt = entry_price * volume 
        fee_amount = trade_cost_usdt * (fee_rate / 100)
        self.balance -= fee_amount
        self.save_balance(self.balance)
        
        fee_action = "debited (Taker)" if fee_amount > 0 else "added (Maker Rebate)"
        
        print(f"Position opened: {side} {volume:.4f} {symbol} at price {entry_price:.4f}")
        print(f"Fee: {abs(fee_amount):.4f} USDT ({fee_action})")
        
    def close_position(self, close_price):
        # Closes the position, calculates PnL, updates balance, and logs the trade
        if not self.active_trade:
            return
        
        side = self.active_trade['side']
        entry_price = self.active_trade['entry_price']
        volume = self.active_trade['volume']
        
        pnl = 0
        if side == 'Buy':
            pnl = (close_price - entry_price) * volume
        elif side == 'Sell':
            pnl = (entry_price - close_price) * volume
        
        self.balance += pnl
        
        # Accounting for exit fee
        close_value_usdt = close_price * volume 
        fee_amount_close = close_value_usdt * (TAKER_FEE_PERCENT / 100)
        
        self.balance -= fee_amount_close
        timestamp_close = pd.Timestamp.now()

        # Logging to Excel
        self.log_trade(
            symbol=self.active_trade['symbol'],
            side=side,
            entry_price=entry_price,
            close_price=close_price,
            pnl=pnl, 
            new_balance=self.balance,
            volume=volume,
            timestamp_open=self.active_trade['timestamp_open'],
            timestamp_close=timestamp_close
        )
        
        self.save_balance(self.balance)
        
        # Formatting message for console (instead of Telegram)
        pnl_percent = (pnl / (self.active_trade['volume'] * self.active_trade['entry_price'])) * 100 if self.active_trade['entry_price'] > 0 else 0
        pnl_emoji = "✅" if pnl >= 0 else "❌"
        total_pnl_net = pnl - fee_amount_close 
        timestamp_close_str = timestamp_close.strftime('%Y-%m-%d %H:%M:%S')

        print(f"\n--- TRADE CLOSED ---")
        print(f"{pnl_emoji} Instrument: {self.active_trade['symbol']}")
        print(f"Type: {side}")
        print(f"PnL (NET): {total_pnl_net:.2f} USDT ({pnl_percent:.2f}%)")
        print(f"Exit Fee: {fee_amount_close:.4f} USDT")
        print(f"Entry Price: {entry_price:.8f}")
        print(f"Exit Price: {close_price:.8f}")
        print(f"New Balance: {self.balance:.2f} USDT")
        print(f"Time: {timestamp_close_str}")
        print("--------------------\n")
        
        self.active_trade = {}

    def log_trade(self, symbol, side, entry_price, close_price, pnl, new_balance, volume, timestamp_open, timestamp_close):
        # Adds the trade record to the Excel file
        # ... (Excel logging code) ...
        new_trade = pd.DataFrame([{
            'Symbol': symbol,
            'Side': side,
            'Entry Price': entry_price,
            'Close Price': close_price,
            'Volume': volume,
            'PnL': pnl, 
            'New Balance': new_balance,
            'Open Time': timestamp_open,
            'Close Time': timestamp_close
        }])

        if not os.path.exists(self.history_file):
            new_trade.to_excel(self.history_file, index=False, sheet_name='Trade History')
        else:
            existing_df = pd.read_excel(self.history_file, sheet_name='Trade History')
            updated_df = pd.concat([existing_df, new_trade], ignore_index=True)
            updated_df.to_excel(self.history_file, index=False, sheet_name='Trade History')


# =========================================================================
# === CLASS: TradingBot (Main Trading Logic) ===
# =========================================================================

class TradingBot:
    """
    The main trading bot class that manages cycles and calls the selected indicator.
    """
    def __init__(self, simulator, strategy_type, params_map):
        self.simulator = simulator
        self.strategy_type = strategy_type
        
        # INDICATOR CLASS MAP 
        indicator_map = {
            1: EmaIndicator 
        }
        
        self.current_params = params_map[strategy_type] 
        IndicatorClass = indicator_map.get(self.strategy_type)
        
        if IndicatorClass and self.strategy_type == 1:
            # Create an instance of the required indicator
            self.indicator = IndicatorClass(self.current_params, test_net=simulator.client.testnet)
        else:
            raise ValueError(f"Strategy type {self.strategy_type} is not implemented. Only EMA (ID 1) is supported in this file.")
            
        self.stop_loss_percent = self.current_params['SL_PERCENT']
        self.take_profit_percent = self.current_params['TP_PERCENT']


    def manage_open_trade(self, symbol, entry_price, side, trade_info):
        """Manages an open position: checks SL and TP."""
        # Use the indicator's inherited method to get the current price
        current_price = self.simulator.get_current_price(symbol, self.indicator.category)
        
        if current_price is None:
            return

        # SL/TP levels are taken from parameters specific to the current strategy
        stop_loss_percent = self.current_params['SL_PERCENT']
        take_profit_percent = self.current_params['TP_PERCENT']

        if side == 'Buy': # Long
            stop_loss_price = entry_price * (1 - stop_loss_percent / 100)
            take_profit_price = entry_price * (1 + take_profit_percent / 100)
            
            # ... (SL/TP condition check) ...
            if current_price >= take_profit_price:
                self.simulator.close_position(current_price)
            elif current_price <= stop_loss_price:
                self.simulator.close_position(current_price)
            else:
                print(f"Position {symbol} (Long): Current price {current_price:.4f} (entry: {entry_price:.4f}). Waiting...")
                                
        elif side == 'Sell': # Short
            stop_loss_price = entry_price * (1 + stop_loss_percent / 100)
            take_profit_price = entry_price * (1 - take_profit_percent / 100)

            # ... (SL/TP condition check) ...
            if current_price <= take_profit_price:
                self.simulator.close_position(current_price)
            elif current_price >= stop_loss_price:
                self.simulator.close_position(current_price)
            else:
                print(f"Position {symbol} (Short): Current price {current_price:.4f} (entry: {entry_price:.4f}). Waiting...")

    def run_strategy(self):
        """The main bot loop: searches for signals and manages trades."""
        while True:
            try:
                # If a position is open, manage it
                if self.simulator.active_trade:
                    # ... (Position management logic) ...
                    symbol = self.simulator.active_trade['symbol']
                    entry_price = self.simulator.active_trade['entry_price']
                    side = self.simulator.active_trade['side']
                    self.manage_open_trade(symbol, entry_price, side, self.simulator.active_trade)
                    tm.sleep(13) # Pause when a trade is open
                else:
                    # No position, search for a new signal
                    print(f"[{tm.strftime('%H:%M:%S')}] Searching for signal on Strategy #1 (EMA)...")
                    
                    # INDICATOR CALL
                    signal = self.indicator.get_first_coin_to_buy()
                    
                    if signal:
                        symbol, signal_type, category = signal
                        
                        # Check category
                        if category != self.indicator.category:
                            print(f"Error: Signal category ({category}) does not match strategy category ({self.indicator.category}). Skipping.")
                            tm.sleep(5)
                            continue
                            
                        # Get entry price (current price)
                        current_price = self.simulator.get_current_price(symbol, category)
                        
                        if current_price is not None:
                            side = 'Buy' if 'BUY' in signal_type else 'Sell'
                            
                            # Calculate volume based on global risk and strategy SL
                            volume_to_buy = calculate_volume_from_risk(
                                RISK_PER_TRADE_USDT, 
                                current_price, 
                                self.current_params['SL_PERCENT']
                            )

                            if volume_to_buy > 0:
                                # Open position
                                self.simulator.open_position(symbol, side, current_price, volume_to_buy, category)
                                print(f"✅ Trade entry: {side} {symbol} at price {current_price:.4f}, volume: {volume_to_buy:.4f}")
                                
                    tm.sleep(10) # Pause when no trade is open

            except Exception as e:
                print(f"An unexpected error occurred in the strategy: {e}")
                tm.sleep(18)

# =========================================================================
# === ENTRY POINT: BOT STARTUP ===
# =========================================================================

if __name__ == "__main__":
    
    # --- ⚠️ Defining the final PARAMS_MAP ---
    PARAMS_MAP = {
        1: EMA_PARAMS
    }
    # --------------------------------------------------------------------
    
    try:
        # Create simulator instance
        simulator = TradingSimulator(test_net=False)
        # Create trading logic instance
        trader = TradingBot(simulator, STRATEGY_TYPE, PARAMS_MAP)
        
        print(f"*** Starting Trading Bot, Strategy 1 (EMA Indicator) ***")
        print(f"*** Trading Mode: {TRADING_MODE} (0=LONG, 1=SHORT, 2=BOTH) ***")
        print(f"*** Risk per trade: {RISK_PER_TRADE_USDT} USDT ***\n")
        
        # Start the main loop
        trader.run_strategy()

    except Exception as e:
        print(f"Critical error during initialization or in the main thread: {e}")