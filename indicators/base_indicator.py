import pandas as pd
from pybit.unified_trading import HTTP
import os

# --- Helper function for fetching candlestick data ---
def get_kline_data_helper(client, symbol, category, interval, limit):
    """General function to fetch candlestick data, used by all indicators."""
    try:
        response = client.get_kline(
            category=category,
            symbol=symbol,
            interval=interval,
            limit=limit
        )
        if response['retCode'] == 0:
            df = pd.DataFrame(response['result']['list'], columns=['open_time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
            
            # 💡 FIX: Convert time and set index
            df['open_time'] = df['open_time'].astype(int) 
            df['open_time'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
            df.set_index('open_time', inplace=True)
            
            # Convert data to numeric format
            df[['open', 'high', 'low', 'close']] = df[['open', 'high', 'low', 'close']].apply(pd.to_numeric) 
            # Sort by index (time)
            df = df.sort_index(ascending=True) 
            
            return df
        # print(f"API Error (retCode {response['retCode']}): {response.get('retMsg', 'Unknown error')}")
    except Exception as e:
        # print(f"Exception during kline data fetch for {symbol}: {e}")
        pass
    return None

# --- Base Class ---
class BaseIndicator:
    def __init__(self, params, test_net=False):
        # API Client initialization
        BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
        BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')
        self.client = HTTP(api_key=BYBIT_API_KEY, api_secret=BYBIT_API_SECRET, testnet=test_net) 
        
        self.params = params
        self.category = params['CATEGORY']
        self.kline_limit = params.get('KLINE_LIMIT', 100) 
        
        # Get global liquidity filters from parameters
        self.min_volume_24h = params.get('MIN_VOLUME_24H', 150000000)
        self.max_volume_24h = params.get('MAX_VOLUME_24H', 1000000000000)

    def get_kline_data(self, symbol, interval='1', limit=None):
        """Wrapper method for fetching candlestick data, available to all descendants."""
        return get_kline_data_helper(self.client, symbol, self.category, interval, limit or self.kline_limit)
        
    def get_all_tickers(self):
        """General logic for filtering tickers for futures (linear)."""
        if self.category == 'spot':
            # Logic for Spot will be overridden in SpotIndicator
            raise NotImplementedError("For SpotIndicator, use the overridden method SpotIndicator.get_all_tickers.")

        try:
            response = self.client.get_tickers(category=self.category)
            if response['retCode'] == 0:
                tickers_list = response['result']['list']
                usdt_tickers = []
                for t in tickers_list:
                    symbol = t['symbol']
                    volume = float(t.get('turnover24h', 0)) 
                    if (symbol.endswith('USDT') and 
                        not any(ext in symbol for ext in ['UP', 'DOWN', 'BULL', 'BEAR', 'HALF']) and 
                        not symbol[0].isdigit() and
                        volume >= self.min_volume_24h and volume <= self.max_volume_24h):
                        usdt_tickers.append(symbol)
                return usdt_tickers
            # print(f"API Error fetching tickers (retCode {response['retCode']}): {response.get('retMsg', 'Unknown error')}")
            return []
        except Exception:
            # print(f"Exception during ticker data fetch: {e}")
            return []

    def get_first_coin_to_buy(self):
        """Method that searches for a signal. Must be implemented in each indicator."""
        raise NotImplementedError("Subclasses must implement get_first_coin_to_buy")