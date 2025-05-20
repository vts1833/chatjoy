import matplotlib.pyplot as plt

def plot_stock_chart(data, name, font_prop=None):
    history = data['history']
    close = history['Close']
    ma5 = close.rolling(5).mean()
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma120 = close.rolling(120).mean()

    fig, ax = plt.subplots()
    ax.plot(close.index, close, label="종가", linewidth=2)
    ax.plot(ma5.index, ma5, label="5일")
    ax.plot(ma20.index, ma20, label="20일")
    ax.plot(ma60.index, ma60, label="60일")
    ax.plot(ma120.index, ma120, label="120일")
    ax.set_title(f"{name} 주가 차트", fontproperties=font_prop)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig
