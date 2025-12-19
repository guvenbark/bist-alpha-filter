import pandas as pd
import yfinance as yf
from data_manager import DataManager
from strategy_engine import StrategyEngine
import time

class Scanner:
    def __init__(self):
        self.data_manager = DataManager()
        self.strategy_engine = StrategyEngine()
        # BIST 30 Tickers (Snapshot)
        self.bist30_tickers = [
            "AKBNK", "ALARK", "ARCLK", "ASELS", "ASTOR", "BIMAS", "BRSAN", "DOAS", "EKGYO", "ENKAI",
            "EREGL", "FROTO", "GARAN", "GUBRF", "HEKTS", "ISCTR", "KCHOL", "KONTR", "KOZAL", "KRDMD",
            "ODAS", "OYAKC", "PETKM", "PGSUS", "SAHOL", "SASA", "SISE", "TCELL", "THYAO", "TOASO",
            "TUPRS", "YKBNK"
        ]
        # BIST 100 Tickers (Snapshot - Expanded)
        self.bist100_tickers = list(set(self.bist30_tickers + [
            "AEFES", "AGHOL", "AHGAZ", "AKCNS", "AKFGY", "AKMSA", "AKSEN", "ALBRK", "ALFAS", "ANSGR",
            "ASGYO", "BERA", "BFREN", "BIOEN", "BOBET", "BRYAT", "BTCIM", "CANTE", "CCOLA", "CIMSA",
            "CWENE", "DOHOL", "ECILC", "ECZYT", "EGEEN", "ENERY", "ENJSA", "EUPWR", "EUREN",
            "GENIL", "GESAN", "GLYHO", "GOZDE", "GWIND", "HALKB", "ISDMR", "ISGYO", "ISMEN", "IZMDC",
            "KARSN", "KAYSE", "KCAER", "KMPUR", "KORDS", "KOZAA", "KZBGY", "MAVI", "MGROS", "MIATK",
            "OTKAR", "PENTA", "PSGYO", "QUAGR", "REEDR", "SANTM", "SDTTR", "SKBNK", "SMRTG", "SOKM",
            "TABGD", "TAVHL", "TKFEN", "TMSN", "TSKB", "TTKOM", "TTRAK", "TURSG", "ULKER", "VAKBN",
            "VESBE", "YEOTK", "YYLGD", "ZOREN"
        ]))

    def get_bist_tickers(self, index_name="BIST 30"):
        if index_name == "BIST 100":
            return self.bist100_tickers
        return self.bist30_tickers

    def scan_market(self, tickers: list = None, interval: str = "1d"):
        """
        Scans the list of tickers and returns a DataFrame of results.
        """
        if tickers is None:
            tickers = self.get_bist_tickers()

        results = []
        
        # 1. Fetch Index Data First (Global Filter)
        print(f"Fetching Index Data ({interval})...")
        # Re-using fetch_index_data from DataManager which calls fetch_ohlcv("XU100.IS")
        # Note: fetch_index_data in DataManager might default to 1d. Let's fix that usage if needed or override.
        # Ideally DataManager should also accept interval. 
        # For now, let's call data_manager.fetch_ohlcv directly for the index to ensure interval matches.
        index_df = self.data_manager.fetch_ohlcv("XU100.IS", period="2y" if interval=="1wk" else "6mo", interval=interval)
        
        if index_df.empty:
            print("Error: Could not fetch Index data.")
            return pd.DataFrame()

        # 2. Fetch Stock Data (Bulk or Loop)
        print(f"Scanning {len(tickers)} tickers ({interval})...")
        
        # Prepare tickers with .IS extension
        yf_tickers = [t if t.endswith(".IS") else f"{t}.IS" for t in tickers]
        
        # Bulk Download
        # period='1y' is safer for weekly wma 30 (need 30 weeks ~ 7 months)
        period = "2y" if interval == "1wk" else "6mo" 
        try:
            # Using threads=False sometimes helps with rate limits or errors, but True is faster
            bulk_data = yf.download(yf_tickers, period=period, interval=interval, group_by='ticker', progress=True, threads=True)
        except Exception as e:
            print(f"Bulk download failed: {e}")
            return pd.DataFrame()

        # Iterate
        for ticker, yf_ticker in zip(tickers, yf_tickers):
            try:
                # Extract dataframe for single ticker
                if len(tickers) > 1:
                    if yf_ticker in bulk_data:
                        df = bulk_data[yf_ticker].copy()
                    elif ticker in bulk_data: # Backup check
                        df = bulk_data[ticker].copy()
                    else:
                        # Sometimes yfinance returns multi-index columns differently
                        # If columns have levels (Ticker, Price), we might need to access differently if not grouped by ticker correctly
                        # With group_by='ticker', it should be Dict-like or MultiIndex
                        # Let's try to slice if it's a huge DF
                        try:
                           df = bulk_data.xs(yf_ticker, level=0, axis=1)
                        except:
                           continue
                else:
                    df = bulk_data.copy() # If single ticker requested
                
                if df.empty:
                    continue
                
                # Standardize columns
                # yfinance recent versions might use "Price" and "Ticker" levels.
                # If column names are "Open", "High" etc. directly:
                df = df.rename(columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
                
                # Drop NaN
                df = df.dropna()

                if len(df) < 50:
                    continue

                # Calculate Strategy
                df_signals = self.strategy_engine.calculate_indicators(df, index_df)
                latest = self.strategy_engine.get_latest_signal(df_signals)

                if latest:
                    result_row = {
                        "Ticker": ticker,
                        "Price": latest['close'],
                        "Trend Up": latest['trend_up'],
                        "Market Pos": latest['market_positive'],
                        "Buy Signal": latest['buy_signal'],
                        "Exit Signal": latest['exit_signal'],
                        "EMA9": latest['ema_9'],
                        "WMA30": latest['wma_30'],
                        "RSI": latest['rsi']
                    }
                    results.append(result_row)
                    
            except Exception as e:
                # print(f"Error processing {ticker}: {e}") # Reduce spam
                continue

        results_df = pd.DataFrame(results)
        return results_df

    def enrich_with_fundamentals(self, df_results):
        """
        Enriches a results DataFrame with fundamental data.
        Should be called only on filtered results to save time.
        """
        if df_results.empty:
            return df_results

        fundamentals = []
        for ticker in df_results['Ticker']:
            funda = self.data_manager.fetch_fundamentals(ticker)
            fundamentals.append(funda)
        
        funda_df = pd.DataFrame(fundamentals)
        if not funda_df.empty and 'symbol' in funda_df.columns:
            # Merge on Ticker
            funda_df.rename(columns={'symbol': 'Ticker'}, inplace=True)
            return df_results.merge(funda_df, on='Ticker', how='left')
        
        return df_results
