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

# 미국 주요 지수 종목 티커 가져오기 (S&P 500 또는 NASDAQ 100)
def get_us_index_tickers():
    """
    S&P 500과 NASDAQ 100의 구성 종목 티커와 회사명을 Wikipedia에서 가져옵니다.
    Returns: dict, {회사명: 티커} 형식
    """
    us_ticker_map = {}
    
    # S&P 500
    try:
        url_sp500 = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables_sp500 = pd.read_html(url_sp500, header=0, flavor='lxml')
        df_sp500 = tables_sp500[0]
        for _, row in df_sp500.iterrows():
            ticker = row['Symbol']
            company = row['Security']
            if isinstance(ticker, str) and isinstance(company, str) and not ticker.startswith('^'):
                us_ticker_map[company.lower()] = ticker
    except Exception as e:
        try:
            # Fallback to html5lib parser
            tables_sp500 = pd.read_html(url_sp500, header=0, flavor='html5lib')
            df_sp500 = tables_sp500[0]
            for _, row in df_sp500.iterrows():
                ticker = row['Symbol']
                company = row['Security']
                if isinstance(ticker, str) and isinstance(company, str) and not ticker.startswith('^'):
                    us_ticker_map[company.lower()] = ticker
        except Exception as e2:
            st.warning(f"S&P 500 티커 목록을 가져오지 못했습니다: {str(e2)}")

    # NASDAQ 100
    try:
        url_nasdaq = 'https://en.wikipedia.org/wiki/NASDAQ-100'
        tables_nasdaq = pd.read_html(url_nasdaq, header=0, flavor='lxml')
        df_nasdaq = tables_nasdaq[4]  # NASDAQ 100 테이블은 4번째
        for _, row in df_nasdaq.iterrows():
            ticker = row['Ticker']
            company = row['Company']
            if isinstance(ticker, str) and isinstance(company, str) and not ticker.startswith('^'):
                us_ticker_map[company.lower()] = ticker
    except Exception as e:
        try:
            # Fallback to html5lib parser
            tables_nasdaq = pd.read_html(url_nasdaq, header=0, flavor='html5lib')
            df_nasdaq = tables_nasdaq[4]
            for _, row in df_nasdaq.iterrows():
                ticker = row['Ticker']
                company = row['Company']
                if isinstance(ticker, str) and isinstance(company, str) and not ticker.startswith('^'):
                    us_ticker_map[company.lower()] = ticker
        except Exception as e2:
            st.warning(f"NASDAQ 100 티커 목록을 가져오지 못했습니다: {str(e2)}")

    return us_ticker_map

# KRX 종목명-티커 매핑
try:
    with open('krx_ticker_map.json', 'r', encoding='utf-8') as f:
        kr_tickers = json.load(f)
except FileNotFoundError:
    st.warning("krx_ticker_map.json 파일을 찾을 수 없습니다.")
    kr_tickers = {}

# 미국 티커 매핑 (Wikipedia에서 동적으로 가져옴)
us_ticker_map = get_us_index_tickers()

# OpenAI 설정
openai.api_key = "3p1vX5a5zu1nTmEdd0lxhT1E0lpkNKq2vmUif4GrGv0eRa1jV7rHJQQJ99BCACHYHv6XJ3w3AAAAACOGR64o"
openai.api_base = "https://ai-jhs51470758ai014414829313.openai.azure.com/"
openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"

def get_ticker_from_name(stock_name):
    """
    한국 또는 미국 주식 이름을 티커로 매핑합니다.
    한국: krx_ticker_map.json
    미국: Wikipedia S&P 500/NASDAQ 100 및 하드코딩된 티커
    """
    stock_name_lower = stock_name.lower().strip()

    # 한국 티커 확인
    if stock_name in kr_tickers:
        return kr_tickers[stock_name]

    # 하드코딩된 미국 티커
    hardcoded_us_tickers = {
        '애플': 'AAPL', '테슬라': 'TSLA', '마이크로소프트': 'MSFT',
        '알파벳': 'GOOGL', '아마존': 'AMZN', '메타': 'META',
        '엔비디아': 'NVDA', '페이팔': 'PYPL', '넷플릭스': 'NFLX', '팔란티어': 'PLTR',
        'amd': 'AMD', '인텔': 'INTC', 'ibm': 'IBM', '퀄컴': 'QCOM',
    }
    if stock_name_lower in hardcoded_us_tickers:
        return hardcoded_us_tickers[stock_name_lower]

    # Wikipedia에서 가져온 미국 티커 확인
    for company, ticker in us_ticker_map.items():
        # 정확한 매칭 또는 부분 매칭 (예: "Apple"이 "Apple Inc."와 매칭)
        if stock_name_lower == company or stock_name_lower in company:
            return ticker

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

    return {
        'symbol': stock_symbol,
        'name': info.get('shortName', stock_symbol),
        'price': current_price,
        'change_pct': change_pct,
        'market_cap': info.get('marketCap', 0) / 1e12,
        'high_52w': info.get('fiftyTwoWeekHigh'),
        'low_52w': info.get('fiftyTwoWeekLow'),
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'ma_5': float(ma_5),
        'ma_20': float(ma_20),
        'ma_60': float(ma_60),
        'ma_120': float(ma_120),
        'rsi': float(rsi),
        'history': data
    }

def get_ai_analysis(stock_data):
    prompt = f"""
    {stock_data['name']} ({stock_data['symbol']}) 분석 요청:
    - 현재가: {stock_data['price']:,.0f}원 ({stock_data['change_pct']:+.1f}%)
    - 시가총액: {stock_data['market_cap']:,.1f}조원
    - 52주 범위: {stock_data['low_52w']:,.0f}~{stock_data['high_52w']:,.0f}원
    - 업종: {stock_data['sector']} > {stock_data['industry']}
    - 이동평균: 5일 {stock_data['ma_5']:,.0f}, 20일 {stock_data['ma_20']:,.0f}, 60일 {stock_data['ma_60']:,.0f}, 120일 {stock_data['ma_120']:,.0f}
    - RSI: {stock_data['rsi']:.1f}
    AI 분석 요청:
    - 현재 주가 평가
    - 업종 내 경쟁력
    - 다중 이동평균 분석
    - 종합 투자 의견 (300자 내외)
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
        {"role": "assistant", "content": "분석할 종목명을 말씀해 주세요 (예: 삼성전자, Apple)!"}
    ]

# 채팅 메시지 표시
for i, msg in enumerate(st.session_state.messages):
    is_user = msg['role'] == 'user'
    message(msg['content'], is_user=is_user, key=f"msg_{i}")
    if msg.get('chart_data'):
        fig = plot_stock_chart(msg['chart_data'], msg['stock_name'])
        st.pyplot(fig)
        plt.close(fig)  # Close figure to prevent memory leaks

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
            
            # 기본 정보
            basic_info = f"""
**📊 기본 정보**  
{data['name']} ({ticker})  
현재가: {data['price']:,.0f}원 ({data['change_pct']:+.1f}%)  
시가총액: {data['market_cap']:,.1f}조원  
52주 고가: {data['high_52w']:,.0f}원  
52주 저가: {data['low_52w']:,.0f}원  
RSI: {data['rsi']:.1f}
            """
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
    "종목명을 입력하세요 (예: 삼성전자, Apple)",
    key="stock_input",
    on_change=handle_input,
    placeholder="여기에 입력 후 엔터!"
)
