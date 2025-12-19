import yfinance as yf
import pandas as pd

class DataManager:
    def __init__(self):
        pass

    def fetch_ohlcv(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """
        Fetches OHLCV data for a given ticker.
        """
        try:
            # yfinance tickers for BIST usually end with .IS, ensure it's there if not provided
            full_ticker = ticker if ticker.endswith(".IS") else f"{ticker}.IS"
            df = yf.download(full_ticker, period=period, interval=interval, progress=False)
            
            if df.empty:
                return pd.DataFrame()
                
            # Flatten MultiIndex columns if present (common in recent yfinance versions)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Ensure standard column names
            df = df.rename(columns={
                "Open": "open", "High": "high", "Low": "low", 
                "Close": "close", "Volume": "volume"
            })
            
            # Return only necessary columns
            return df[["open", "high", "low", "close", "volume"]]
            
        except Exception as e:
            print(f"Error fetching data for {ticker}: {e}")
            return pd.DataFrame()

    def fetch_index_data(self, index_ticker: str = "XU100.IS", period: str = "1y") -> pd.DataFrame:
        """
        Fetches benchmark index data (BIST 100 default).
        """
        return self.fetch_ohlcv(index_ticker, period=period)

    def fetch_fundamentals(self, ticker: str) -> dict:
        """
        Fetches basic fundamental data (P/E, Market Cap, etc.).
        Returns specific metrics relevant to 'Basic Fundamental Analysis'.
        """
        try:
            full_ticker = ticker if ticker.endswith(".IS") else f"{ticker}.IS"
            info = yf.Ticker(full_ticker).info
            
            return {
                "symbol": ticker,
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
                "sector": info.get("sector"),
                "industry": info.get("industry")
            }
        except Exception as e:
            print(f"Error fetching fundamentals for {ticker}: {e}")
            return {}
