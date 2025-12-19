import pandas as pd
# import pandas_ta as ta - REMOVED
import ta 
import numpy as np

class StrategyEngine:
    def __init__(self, ema_len=9, wma_len=30, index_sma_len=50):
        self.ema_len = ema_len
        self.wma_len = wma_len
        self.index_sma_len = index_sma_len

    def calculate_wma(self, series: pd.Series, length: int) -> pd.Series:
        """Calculates Weighted Moving Average."""
        weights = np.arange(1, length + 1)
        wma = series.rolling(length).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
        return wma

    def calculate_indicators(self, df: pd.DataFrame, index_df: pd.DataFrame = None) -> pd.DataFrame:
        """
        Calculates indicators and strategy signals.
        Returns the dataframe with signal columns.
        """
        if df.empty:
            return df

        # --- Indicators ---
        # EMA 9
        df['ema_9'] = df['close'].ewm(span=self.ema_len, adjust=False).mean()
        
        # WMA 30
        df['wma_30'] = self.calculate_wma(df['close'], self.wma_len)
        
        # RSI 14
        df['rsi'] = ta.momentum.RSIIndicator(df['close'], window=14).rsi()
        
        # Index Logic
        market_positive = True # Default true if no index provided fallback
        if index_df is not None and not index_df.empty:
            # Calculate SMA 50 for Index
            index_df['sma_50'] = index_df['close'].rolling(window=self.index_sma_len).mean()
            
            # Align Index data to Stock data
            df = df.join(index_df[['close', 'sma_50']].rename(columns={'close': 'index_close', 'sma_50': 'index_sma_50'}), rsuffix='_index')
            
            df['market_positive'] = df['index_close'] > df['index_sma_50']
            market_positive = df['market_positive'] # Series
        else:
            df['market_positive'] = True

        # --- Logic ---
        # 1. Trend Direction (9 EMA > 30 WMA)
        df['trend_up'] = df['ema_9'] > df['wma_30']

        # 2. Trigger Candle (Close < EMA 9 and Close > WMA 30) - For info
        df['pullback'] = (df['close'] < df['ema_9']) & (df['close'] > df['wma_30'])

        # 3R. RSI Filter (RSI > 50)
        df['rsi_positive'] = df['rsi'] > 50

        # 3. Buy Signal: Market Positive AND Trend Up AND Crossover(Close, EMA 9) AND RSI > 50
        # Crossover: Previous Close < Previous EMA 9 AND Current Close > Current EMA 9
        df['crossover_ema9'] = (df['close'].shift(1) < df['ema_9'].shift(1)) & (df['close'] > df['ema_9'])
        
        df['buy_signal'] = df['market_positive'] & df['trend_up'] & df['crossover_ema9'] & df['rsi_positive']

        # Exit Signal: Crossunder(Close, WMA 30)
        df['exit_signal'] = (df['close'].shift(1) > df['wma_30'].shift(1)) & (df['close'] < df['wma_30'])

        return df

    def get_latest_signal(self, df: pd.DataFrame) -> dict:
        """
        Returns the latest signal status.
        """
        if df.empty or len(df) < 50: # Need enough data
            return None
        
        last_row = df.iloc[-1]
        return {
            "date": last_row.name,
            "close": last_row['close'],
            "ema_9": last_row['ema_9'],
            "wma_30": last_row['wma_30'],
            "rsi": last_row['rsi'],
            "trend_up": bool(last_row['trend_up']),
            "market_positive": bool(last_row.get('market_positive', True)),
            "rsi_positive": bool(last_row['rsi_positive']),
            "buy_signal": bool(last_row['buy_signal']),
            "exit_signal": bool(last_row['exit_signal'])
        }
