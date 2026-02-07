import yfinance as yf


def get_market_data(ticker_symbol):
   """
   Fetches the current price and 24h change for a stock or crypto.
   """
   try:
       ticker = yf.Ticker(ticker_symbol)
      
       # .fast_info is quicker for 'real-time' stats than .info
       info = ticker.fast_info
      
       current_price = info['lastPrice']
       previous_close = info['previousClose']
      
       # Calculate percent change
       change = ((current_price - previous_close) / previous_close) * 100
      
       return {
           "symbol": ticker_symbol.upper(),
           "price": round(current_price, 2),
           "change_percent": round(change, 2),
           "currency": info['currency']
       }
   except Exception as e:
       return {"error": f"Could not find data for {ticker_symbol}. {str(e)}"}

