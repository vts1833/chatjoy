import streamlit as st
from streamlit_chat import message
import openai
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import json
import warnings
import os

warnings.filterwarnings('ignore')

# 한글 폰트 설정
def setup_font():
    try:
        font_name = "NanumGothic"
        font_list = fm.findSystemFonts()
        font_path = None
        for font in font_list:
            if font_name.lower() in font.lower():
                font_path = font
                break
        
        if font_path:
            fm.fontManager.addfont(font_path)
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
            return font_prop, True
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['axes.unicode_minus'] = False
            st.warning("NanumGothic 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
            return None, False
    except Exception as e:
        st.error(f"폰트 설정 중 오류 발생: {str(e)}")
        plt.rcParams['font.family'] = 'sans-serif'
        return None, False

font_prop, font_available = setup_font()

# KRX 종목명-티커 매핑
try:
    with open('krx_ticker_map.json', 'r', encoding='utf-8') as f:
        kr_tickers = json.load(f)
except FileNotFoundError:
    st.warning("krx_ticker_map.json 파일을 찾을 수 없습니다.")
    kr_tickers = {}

# OpenAI 설정
openai.api_key = "3p1vX5a5zu1nTmEdd0lxhT1E0lpkNKq2vmUif4GrGv0eRa1jV7rHJQQJ99BCACHYHv6XJ3w3AAAAACOGR64o"
openai.api_base = "https://ai-jhs51470758ai014414829313.openai.azure.com/"
openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"

def get_ticker_from_name(stock_name):
    """
    한국 주식은 krx_ticker_map.json에서, 미국 주식은 yfinance로 티커를 확인합니다.
    """
    stock_name_lower = stock_name.lower().strip()

    # 한국 티커 확인
    if stock_name in kr_tickers:
        return kr_tickers[stock_name]

    # 미국 주식 확인 (yfinance로 티커 검증)
    try:
        ticker = stock_name_upper = stock_name.upper()
        stock = yf.Ticker(ticker)
        if stock.info and 'symbol' in stock.info:
            return stock.info['symbol']
        return None
    except Exception as e:
        return None

def calculate_technical_indicators(stock_symbol):
    data = yf.download(stock_symbol, period="1y", progress=False)
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

    return ma_5.iloc[-1], ma_20.iloc[-1], ma_60.iloc[-1], ma_120.iloc[-1], rsi.iloc[-1], data

def get_stock_info(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    info = stock.info
    history = stock.history(period="1y")
    current_price = history['Close'].iloc[-1]
    prev_close = history['Close'].iloc[-2] if len(history) > 1 else current_price
    change_pct = (current_price - prev_close) / prev_close * 100 if prev_close else 0
    ma_5, ma_20, ma_60, ma_120, rsi, data = calculate_technical_indicators(stock_symbol)

    # 미국 주식(.KS 없음)은 달러, 한국 주식은 원
    is_us_stock = '.KS' not in stock_symbol
    currency = '$' if is_us_stock else '₩'
    market_cap = info.get('marketCap', 0)
    market_cap_unit = '억 달러' if is_us_stock else '조 원'
    market_cap_value = market_cap / 1e9 if is_us_stock else market_cap / 1e12

    return {
        'symbol': stock_symbol,
        'name': info.get('shortName', stock_symbol),
        'price': current_price,
        'change_pct': change_pct,
        'market_cap': market_cap_value,
        'market_cap_unit': market_cap_unit,
        'high_52w': info.get('fiftyTwoWeekHigh'),
        'low_52w': info.get('fiftyTwoWeekLow'),
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'ma_5': float(ma_5),
        'ma_20': float(ma_20),
        'ma_60': float(ma_60),
        'ma_120': float(ma_120),
        'rsi': float(rsi),
        'history': data,
        'currency': currency
    }

def get_ai_analysis(stock_data):
    currency = stock_data['currency']
    price_format = f"{currency}{stock_data['price']:,.2f}" if currency == '$' else f"{stock_data['price']:,.0f}{currency}"
    high_52w_format = f"{currency}{stock_data['high_52w']:,.2f}" if currency == '$' else f"{stock_data['high_52w']:,.0f}{currency}"
    low_52w_format = f"{currency}{stock_data['low_52w']:,.2f}" if currency == '$' else f"{stock_data['low_52w']:,.0f}{currency}"
    ma_5_format = f"{currency}{stock_data['ma_5']:,.2f}" if currency == '$' else f"{stock_data['ma_5']:,.0f}{currency}"
    ma_20_format = f"{currency}{stock_data['ma_20']:,.2f}" if currency == '$' else f"{stock_data['ma_20']:,.0f}{currency}"
    ma_60_format = f"{currency}{stock_data['ma_60']:,.2f}" if currency == '$' else f"{stock_data['ma_60']:,.0f}{currency}"
    ma_120_format = f"{currency}{stock_data['ma_120']:,.2f}" if currency == '$' else f"{stock_data['ma_120']:,.0f}{currency}"
    market_cap_format = f"{stock_data['market_cap']:,.1f} {stock_data['market_cap_unit']}"

    prompt = f"""
    다음 데이터를 바탕으로 {stock_data['name']} ({stock_data['symbol']})를 분석해 주세요. 분석은 자연스러운 한국어로, 문장을 완결하게 작성하며, 제공된 데이터를 정확히 반영하세요.

    - 현재가: {price_format} ({stock_data['change_pct']:+.1f}%)
    - 시가총액: {market_cap_format}
    - 52주 범위: {low_52w_format} ~ {high_52w_format}
    - 업종: {stock_data['sector']} > {stock_data['industry']}
    - 이동평균: 5일 {ma_5_format}, 20일 {ma_20_format}, 60일 {ma_60_format}, 120일 {ma_120_format}
    - RSI: {stock_data['rsi']:.1f}

    분석 내용:
    1. 현재 주가 평가: 주가가 52주 범위와 이동평균 대비 어떤 위치인지.
    2. 업종 내 경쟁력: 회사의 시장 지위와 강점.
    3. 다중 이동평균 분석: 단기(5일, 20일) 및 장기(60일, 120일) 추세.
    4. 종합 투자 의견: 300자 내외로, 투자 판단 근거 포함.

    출력 형식:
    {stock_data['name']} ({stock_data['symbol']}) 분석:
    - 현재 주가는 {price_format}이며, 전일 대비 {stock_data['change_pct']:+.1f}% 변동했습니다.
    - [주가 평가 문장]
    - [경쟁력 문장]
    - [이동평균 분석 문장]
    - 종합 의견: [투자 의견]
    """

    try:
        response = openai.ChatCompletion.create(
            engine="gpt-35-turbo",
            messages=[
                {"role": "system", "content": "주식 분석 전문가"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 분석 실패: {str(e)}"

def plot_stock_chart(stock_data, stock_name):
    history = stock_data['history']
    close = history['Close']
    ma_5 = close.rolling(5).mean()
    ma_20 = close.rolling(20).mean()
    ma_60 = close.rolling(60).mean()
    ma_120 = close.rolling(120).mean()

    fig, ax = plt.subplots()
    ax.plot(close.index, close, label="종가", color="blue", linewidth=2)
    ax.plot(ma_5.index, ma_5, label="5일", color="red")
    ax.plot(ma_20.index, ma_20, label="20일", color="green")
    ax.plot(ma_60.index, ma_60, label="60일", color="orange")
    ax.plot(ma_120.index, ma_120, label="120일", color="purple")
    ax.set_title(f"{stock_name} 주가 차트", fontproperties=font_prop if font_prop else None)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    return fig

# ✅ Streamlit 앱 시작
st.title("📈 ChatJOY AI 주식 분석")

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "분석할 종목명을 말씀해 주세요 (예: 삼성전자, AAPL)!"}
    ]

# 채팅 메시지 표시
for i, msg in enumerate(st.session_state.messages):
    is_user = msg['role'] == 'user'
    if msg.get('chart_data'):
        fig = plot_stock_chart(msg['chart_data'], msg['stock_name'])
        st.pyplot(fig)
        plt.close(fig)  # Close figure to prevent memory leaks
    else:
        st.markdown(msg['content'], unsafe_allow_html=True)

# 종목명 입력 및 엔터 키 처리
def handle_input():
    stock_name = st.session_state.stock_input
    if stock_name:
        # 사용자 입력 추가
        st.session_state.messages.append({"role": "user", "content": stock_name})
        
        ticker = get_ticker_from_name(stock_name)
        if not ticker:
            st.session_state.messages.append({"role": "assistant", "content": "❌ 종목명을 찾을 수 없습니다."})
        else:
            with st.spinner("데이터 조회 중..."):
                data = get_stock_info(ticker)
            
            # 기본 정보 - 각 항목을 개별적으로 포맷팅
            currency = data['currency']
            price_str = f"{currency}{data['price']:,.2f}" if currency == '$' else f"{data['price']:,.0f}{currency}"
            change_str = f"{data['change_pct']:+.1f}%"
            market_cap_str = f"{data['market_cap']:,.1f} {data['market_cap_unit']}"
            high_52w_str = f"{currency}{data['high_52w']:,.2f}" if currency == '$' else f"{data['high_52w']:,.0f}{currency}"
            low_52w_str = f"{currency}{data['low_52w']:,.2f}" if currency == '$' else f"{data['low_52w']:,.0f}{currency}"
            rsi_str = f"{data['rsi']:.1f}"

            basic_info = (
                "**📊 기본 정보**\n"
                f"{data['name']} ({ticker})\n"
                f"현재가: {price_str} ({change_str})\n"
                f"시가총액: {market_cap_str}\n"
                f"52주 고가: {high_52w_str}\n"
                f"52주 저가: {low_52w_str}\n"
                f"RSI: {rsi_str}\n"
            )
            st.session_state.messages.append({"role": "assistant", "content": basic_info})
            
            # AI 분석
            analysis = get_ai_analysis(data)
            st.session_state.messages.append({"role": "assistant", "content": f"**🤖 AI 분석**\n{analysis}"})
            
            # 주가 차트 데이터 저장
            st.session_state.messages.append({
                "role": "assistant",
                "content": "📈 주가 차트",
                "chart_data": data,
                "stock_name": stock_name
            })
        
        # 입력창 초기화
        st.session_state.stock_input = ""

# 입력창 (엔터로 실행)
st.text_input(
    "종목명을 입력하세요 (예: 삼성전자, AAPL)",
    key="stock_input",
    on_change=handle_input,
    placeholder="여기에 입력 후 엔터!"
)
