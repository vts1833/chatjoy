import yfinance as yf
from .indicators import calculate_indicators

def get_stock_info(ticker, exchange_rate):
    stock = yf.Ticker(ticker)
    info = stock.info
    history = stock.history(period="1y")
    close = history['Close']
    current = close.iloc[-1]
    prev = close.iloc[-2] if len(close) > 1 else current
    change_pct = (current - prev) / prev * 100
    ma5, ma20, ma60, ma120, rsi = calculate_indicators(history)

    return {
        "symbol": ticker,
        "name": info.get("shortName", ticker),
        "price": current * exchange_rate,
        "change_pct": change_pct,
        "market_cap": info.get("marketCap", 0) * exchange_rate / 1e12,
        "market_cap_unit": "조 원",
        "high_52w": info.get("fiftyTwoWeekHigh", 0) * exchange_rate,
        "low_52w": info.get("fiftyTwoWeekLow", 0) * exchange_rate,
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "ma_5": ma5 * exchange_rate,
        "ma_20": ma20 * exchange_rate,
        "ma_60": ma60 * exchange_rate,
        "ma_120": ma120 * exchange_rate,
        "rsi": rsi,
        "history": history,
        "currency": "₩"
    }
