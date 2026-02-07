"""
Stock Monitor Agent Integration
Combines proactive monitoring with email reporting
"""

from proactive_monitor import StockMonitor, get_stock_snapshot
from email_reporter import EmailReporter, create_gmail_reporter


class StockMonitorAgent:
    """Main agent that integrates monitoring and reporting"""
    
    def __init__(self, email_config: dict, check_interval_minutes: int = 10):
        """
        Args:
            email_config: Dict with 'gmail_address' and 'app_password'
            check_interval_minutes: How often to check and report (default: 10)
        """
        # Setup email reporter
        self.reporter = create_gmail_reporter(
            email_config['gmail_address'],
            email_config['app_password']
        )
        self.recipient_email = email_config['gmail_address']  # Send to self
        
        # Setup stock monitor with callback
        self.monitor = StockMonitor(
            callback=self._on_stock_update,
            interval_minutes=check_interval_minutes
        )
    
    def _on_stock_update(self, stock_data: dict):
        """Called automatically when monitor collects data"""
        print(f"\n📊 Proactive update at {stock_data['timestamp']}")
        
        # Print to console
        for stock in stock_data['stocks']:
            symbol = stock['symbol']
            price = stock['price']
            change = stock['change_percent']
            print(f"  {symbol}: ${price} ({change:+.2f}%)")
        
        # Send email report
        self.reporter.send_report(stock_data, self.recipient_email)
    
    def add_stock(self, symbol: str):
        """Add stock to watchlist"""
        self.monitor.add_stock(symbol)
    
    def remove_stock(self, symbol: str):
        """Remove stock from watchlist"""
        self.monitor.remove_stock(symbol)
    
    def start(self):
        """Start proactive monitoring"""
        self.monitor.start()
    
    def stop(self):
        """Stop proactive monitoring"""
        self.monitor.stop()
    
    def get_immediate_report(self, symbol: str) -> dict:
        """Get immediate snapshot of a stock (on-demand)"""
        return get_stock_snapshot(symbol)