import requests
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf
import random

class ApiClient:
    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v8/finance/chart/"
        
    def get_market_data(self, symbol, interval='1d', range_period='1mo'):
        """Get market data from Yahoo Finance"""
        try:
            ticker = yf.Ticker(symbol)
            
            # Map intervals
            interval_map = {
                '1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m',
                '1h': '1h', '4h': '4h', '1d': '1d', '1w': '1wk'
            }
            
            # Map periods
            period_map = {
                '1d': '1d', '5d': '5d', '1mo': '1mo', 
                '3mo': '3mo', '6mo': '6mo', '1y': '1y'
            }
            
            yf_interval = interval_map.get(interval, '1d')
            yf_period = period_map.get(range_period, '1mo')
            
            # Get historical data
            hist = ticker.history(period=yf_period, interval=yf_interval)
            
            if hist.empty:
                return []
            
            # Convert to our format
            data = []
            for index, row in hist.iterrows():
                data.append({
                    'datetime': index.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(row['Open']),
                    'high': float(row['High']),
                    'low': float(row['Low']),
                    'close': float(row['Close']),
                    'volume': int(row['Volume']) if not pd.isna(row['Volume']) else 0
                })
            
            return data
            
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return self._generate_mock_data(symbol)
    
    def get_quote(self, symbol):
        """Get current quote for symbol"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            hist = ticker.history(period='2d')
            
            if hist.empty:
                return self._generate_mock_quote(symbol)
            
            current_price = float(hist['Close'].iloc[-1])
            previous_close = float(hist['Close'].iloc[-2]) if len(hist) > 1 else current_price
            
            change = current_price - previous_close
            change_percent = (change / previous_close) * 100 if previous_close != 0 else 0
            
            return {
                'symbol': symbol,
                'price': current_price,
                'change': change,
                'changePercent': change_percent,
                'dayHigh': float(hist['High'].iloc[-1]),
                'dayLow': float(hist['Low'].iloc[-1]),
                'volume': int(hist['Volume'].iloc[-1]) if not pd.isna(hist['Volume'].iloc[-1]) else 0,
                'previousClose': previous_close,
                'marketCap': info.get('marketCap', 0),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
            return self._generate_mock_quote(symbol)
    
    def _generate_mock_data(self, symbol):
        """Generate mock market data for testing"""
        data = []
        base_price = 100.0
        
        for i in range(30):  # 30 days of data
            date = datetime.now() - timedelta(days=29-i)
            
            # Generate realistic OHLC data
            open_price = base_price + random.uniform(-2, 2)
            high_price = open_price + random.uniform(0, 3)
            low_price = open_price - random.uniform(0, 3)
            close_price = open_price + random.uniform(-2, 2)
            volume = random.randint(1000000, 10000000)
            
            data.append({
                'datetime': date.strftime('%Y-%m-%d %H:%M:%S'),
                'open': round(open_price, 4),
                'high': round(high_price, 4),
                'low': round(low_price, 4),
                'close': round(close_price, 4),
                'volume': volume
            })
            
            base_price = close_price  # Use close as next base
        
        return data
    
    def _generate_mock_quote(self, symbol):
        """Generate mock quote data for testing"""
        base_price = 100.0 + random.uniform(-50, 50)
        change = random.uniform(-5, 5)
        
        return {
            'symbol': symbol,
            'price': round(base_price, 4),
            'change': round(change, 4),
            'changePercent': round((change / base_price) * 100, 2),
            'dayHigh': round(base_price + random.uniform(0, 3), 4),
            'dayLow': round(base_price - random.uniform(0, 3), 4),
            'volume': random.randint(1000000, 10000000),
            'previousClose': round(base_price - change, 4),
            'marketCap': random.randint(1000000000, 100000000000),
            'timestamp': datetime.now().isoformat()
        }

