import pandas as pd
from strategy_engine import StrategyEngine
from data_manager import DataManager
import time

class Backtester:
    def __init__(self):
        self.strategy_engine = StrategyEngine()
        self.data_manager = DataManager()
        
    def run_backtest(self, df: pd.DataFrame) -> dict:
        """
        Runs backtest on a single dataframe with signals already calculated.
        Assumes df has 'buy_signal' and 'exit_signal'.
        """
        trades = []
        position = None # {'entry_price': float, 'entry_date': date}
        
        for index, row in df.iterrows():
            # Check Exit First
            if position:
                # If exit signal OR we want a stop loss (not defined yet, sticking to strategy exit)
                if row['exit_signal']:
                    exit_price = row['close']
                    pnl = (exit_price - position['entry_price']) / position['entry_price']
                    trades.append({
                        "entry_date": position['entry_date'],
                        "exit_date": index,
                        "entry_price": position['entry_price'],
                        "exit_price": exit_price,
                        "return": pnl
                    })
                    position = None
            
            # Check Entry
            if not position and row['buy_signal']:
                position = {
                    'entry_price': row['close'],
                    'entry_date': index
                }
                
        # Close open position at end (mark as unrealized/final close)
        if position:
            exit_price = df.iloc[-1]['close']
            pnl = (exit_price - position['entry_price']) / position['entry_price']
            trades.append({
                "entry_date": position['entry_date'],
                "exit_date": df.index[-1],
                "entry_price": position['entry_price'],
                "exit_price": exit_price,
                "return": pnl,
                "status": "open"
            })
            
        return trades

    def backtest_tickers(self, tickers: list, period="1y", interval="1d"):
        """
        Runs backtest for a list of tickers.
        """
        results = []
        
        # Fetch Index Data
        idx_period = "2y" if interval == "1wk" else "1y" # Match period roughly
        print(f"Fetching Index for Backtest ({idx_period})...")
        index_df = self.data_manager.fetch_ohlcv("XU100.IS", period=idx_period, interval=interval)
        
        # Reusing Scanner logic for bulk fetch could be better but let's stick to safe iteration for backtest validity or use small bulk chunks.
        # Let's use loop for precision now.
        
        for ticker in tickers:
            try:
                df = self.data_manager.fetch_ohlcv(ticker, period=period, interval=interval)
                if df.empty or len(df) < 50:
                    continue
                
                # Calculate Signals
                df = self.strategy_engine.calculate_indicators(df, index_df)
                
                # Run Simulation
                trades = self.run_backtest(df)
                
                if trades:
                    # Calc metrics
                    total_trades = len(trades)
                    winning_trades = len([t for t in trades if t['return'] > 0])
                    win_rate = winning_trades / total_trades if total_trades > 0 else 0
                    total_return = sum([t['return'] for t in trades])
                    
                    results.append({
                        "Ticker": ticker,
                        "Total Trades": total_trades,
                        "Win Rate": win_rate,
                        "Total Return": total_return,
                        "Trades": trades
                    })
            except Exception as e:
                print(f"Backtest error {ticker}: {e}")
                
        return pd.DataFrame(results)
