from .base_indicator import BaseIndicator
import pandas_ta as ta
import time as tm
import numpy as np # <-- ADDED for NaN check

class EmaIndicator(BaseIndicator):
    def __init__(self, params, test_net=False):
        super().__init__(params, test_net)
        self.ema_fast = params['EMA_FAST_LENGTH']
        self.ema_slow = params['EMA_SLOW_LENGTH']

    def get_first_coin_to_buy(self):
        tickers_to_check = self.get_all_tickers()
        kline_limit = max(self.ema_fast, self.ema_slow) + 1 # +1 for .iloc[-2]
        
        for coin in tickers_to_check:
            interval = self.params.get('KLINE_INTERVAL', '60') 
            kline_limit_param = self.params.get('KLINE_LIMIT', 200) 
            df = self.get_kline_data(coin, interval=interval, limit=kline_limit_param)
                        
            if df is not None and not df.empty and len(df) >= kline_limit:
                try: # <-- ADDED ERROR HANDLING
                    ema_f = ta.ema(df['close'], length=self.ema_fast)
                    ema_s = ta.ema(df['close'], length=self.ema_slow)
                except Exception as e:
                    print(f"⚠️ {coin}: Error calculating EMA: {e}")
                    tm.sleep(0.5)
                    continue

                # Extract values for the current and previous candle
                ema_f_now = ema_f.iloc[-1]
                ema_s_now = ema_s.iloc[-1]
                ema_f_prev = ema_f.iloc[-2]
                ema_s_prev = ema_s.iloc[-2]

                # NaN Check
                if (np.isnan(ema_f_now) or np.isnan(ema_s_now) or 
                    np.isnan(ema_f_prev) or np.isnan(ema_s_prev)): # <-- ADDED NaN CHECK
                    tm.sleep(0.5)
                    continue
                
                # Buy: Fast EMA crosses slow EMA from below to above
                if ema_f_now > ema_s_now and ema_f_prev <= ema_s_prev:
                    print(f"LONG Signal by EMA for {coin}: Crossover up.")
                    return [coin, 'STRONG_BUY', self.category]
                
                # Sell: Fast EMA crosses slow EMA from above to below
                if ema_f_now < ema_s_now and ema_f_prev >= ema_s_prev:
                    print(f"SHORT Signal by EMA for {coin}: Crossover down.")
                    return [coin, 'STRONG_SELL', self.category]
                
                tm.sleep(0.5)
        return None