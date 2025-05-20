def calculate_indicators(data):
    close = data['Close']
    ma_5 = close.rolling(5).mean()
    ma_20 = close.rolling(20).mean()
    ma_60 = close.rolling(60).mean()
    ma_120 = close.rolling(120).mean()
    delta = close.diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return ma_5.iloc[-1], ma_20.iloc[-1], ma_60.iloc[-1], ma_120.iloc[-1], rsi.iloc[-1]
