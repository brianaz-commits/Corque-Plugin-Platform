"""
Proactive Stock Monitor Tool
Monitors stock prices at scheduled intervals and triggers callbacks
"""

import threading
import time
from datetime import datetime
from typing import Callable, List, Dict
import yfinance as yf


class StockMonitor:
    """Background monitor that checks stocks at regular intervals"""
    
    def __init__(self, callback: Callable[[Dict], None], interval_minutes: int = 10):
        """
        Args:
            callback: Function to call when reporting stock data
            interval_minutes: How often to check stocks (default: 10 minutes)
        """
        self.callback = callback
        self.interval_seconds = interval_minutes * 60
        self.watchlist: List[str] = []
        self.is_running = False
        self.monitor_thread = None
    
    def add_stock(self, symbol: str):
        """Add a stock to the watchlist"""
        if symbol not in self.watchlist:
            self.watchlist.append(symbol.upper())
            print(f"Added {symbol} to watchlist")
    
    def remove_stock(self, symbol: str):
        """Remove a stock from the watchlist"""
        if symbol.upper() in self.watchlist:
            self.watchlist.remove(symbol.upper())
            print(f"Removed {symbol} from watchlist")
    
    def start(self):
        """Start the background monitoring"""
        if self.is_running:
            print("Monitor already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"✓ Monitor started - checking every {self.interval_seconds // 60} minutes")
    
    def stop(self):
        """Stop the background monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        print("Monitor stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop running in background thread"""
        while self.is_running:
            try:
                if self.watchlist:
                    stock_data = self._fetch_stock_data()
                    self.callback(stock_data)
            except Exception as e:
                print(f"Monitor error: {e}")
            
            # Wait for next interval
            time.sleep(self.interval_seconds)
    
    def _fetch_stock_data(self) -> Dict:
        """Fetch current data for all stocks in watchlist"""
        results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'stocks': []
        }
        
        for symbol in self.watchlist:
            try:
                stock = yf.Ticker(symbol)
                info = stock.info
                hist = stock.history(period='1d')
                
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
                    open_price = hist['Open'].iloc[0]
                    change = current_price - open_price
                    change_percent = (change / open_price) * 100
                    
                    stock_info = {
                        'symbol': symbol,
                        'name': info.get('longName', symbol),
                        'price': round(current_price, 2),
                        'change': round(change, 2),
                        'change_percent': round(change_percent, 2),
                        'volume': hist['Volume'].iloc[-1],
                        'high': round(hist['High'].max(), 2),
                        'low': round(hist['Low'].min(), 2)
                    }
                    results['stocks'].append(stock_info)
                    
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
        
        return results


def get_stock_snapshot(symbol: str) -> Dict:
    """
    Get immediate snapshot of a single stock
    Useful for on-demand queries
    """
    try:
        stock = yf.Ticker(symbol.upper())
        info = stock.info
        hist = stock.history(period='1d')
        
        if hist.empty:
            return {'error': f'No data available for {symbol}'}
        
        current_price = hist['Close'].iloc[-1]
        open_price = hist['Open'].iloc[0]
        change = current_price - open_price
        change_percent = (change / open_price) * 100
        
        return {
            'symbol': symbol.upper(),
            'name': info.get('longName', symbol),
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_percent': round(change_percent, 2),
            'volume': hist['Volume'].iloc[-1],
            'high': round(hist['High'].max(), 2),
            'low': round(hist['Low'].min(), 2),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {'error': str(e)}