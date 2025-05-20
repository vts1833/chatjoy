import yfinance as yf

def get_ticker_from_name(name, kr_tickers):
    name = name.strip().lower()
    if name in kr_tickers:
        return kr_tickers[name]
    try:
        ticker = name.upper()
        if yf.Ticker(ticker).info.get('symbol'):
            return ticker
    except:
        return None
