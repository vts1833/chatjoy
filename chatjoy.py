import streamlit as st
import yfinance as yf
import json
import os
import warnings
import openai
import requests
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from functools import lru_cache

warnings.filterwarnings('ignore')

# ====== 환경설정 및 유틸 ======
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "krx_ticker_map.json")

# 한글 폰트
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
            return font_prop
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['axes.unicode_minus'] = False
            st.warning("NanumGothic 폰트를 찾을 수 없습니다. 기본 폰트로 출력됩니다.")
            return None
    except Exception as e:
        st.error(f"폰트 설정 중 오류 발생: {str(e)}")
        plt.rcParams['font.family'] = 'sans-serif'
        return None

font_prop = setup_font()

# KRX 종목명-티커 매핑
try:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        krx_map = json.load(f)
except FileNotFoundError:
    st.warning(f"krx_ticker_map.json 파일을 찾을 수 없습니다: {JSON_PATH}")
    krx_map = {}

# 환율 API (USD→KRW)
@lru_cache(maxsize=1)
def get_exchange_rate():
    try:
        url = "https://v6.exchangerate-api.com/v6/a7ce46583c0498045e014086/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['result'] == 'success':
            return data['conversion_rates']['KRW']
        else:
            st.warning(f"환율 API 응답 오류: {data.get('error-type', 'Unknown error')}. 기본 환율(1340) 사용")
            return 1340
    except Exception as e:
        st.warning(f"환율 API 요청 실패: {str(e)}. 기본 환율(1340) 사용")
        return 1340

exchange_rate = get_exchange_rate()

# OpenAI API 세팅 (Azure)
openai.api_key = "3p1vX5a5zu1nTmEdd0lxhT1E0lpkNKq2vmUif4GrGv0eRa1jV7rHJQQJ99BCACHYHv6XJ3w3AAAAACOGR64o"
openai.api_base = "https://ai-jhs51470758ai014414829313.openai.azure.com/"
openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"

def get_ticker_from_name(stock_name):
    name = stock_name.strip()
    if name in krx_map:
        return krx_map[name]
    if name.isupper() and len(name) <= 6:
        return name
    return None

@lru_cache(maxsize=64)
def calculate_technical_indicators(stock_symbol):
    data = yf.download(stock_symbol, period="1y", progress=False)
    if data.empty:
        return None
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

@lru_cache(maxsize=64)
def get_stock_info(stock_symbol):
    try:
        stock = yf.Ticker(stock_symbol)
        try:
            info = stock.info
            history = stock.history(period="1y")
        except Exception as e:
            if "429" in str(e):
                raise RuntimeError("야후 파이낸스 429 Too Many Requests (과도한 요청으로 인한 임시 차단)") from e
            else:
                raise
        if history.empty or not info:
            return None
        current_price = history['Close'].iloc[-1]
        prev_close = history['Close'].iloc[-2] if len(history) > 1 else current_price
        change_pct = (current_price - prev_close) / prev_close * 100 if prev_close else 0
        ind_result = calculate_technical_indicators(stock_symbol)
        if not ind_result:
            return None
        ma_5, ma_20, ma_60, ma_120, rsi, data = ind_result
        currency = '₩'
        market_cap = info.get('marketCap', 0) * exchange_rate / 1e12
        current_price_won = current_price * exchange_rate
        high_52w_won = info.get('fiftyTwoWeekHigh', 0) * exchange_rate
        low_52w_won = info.get('fiftyTwoWeekLow', 0) * exchange_rate
        market_cap_unit = '조 원'
        return {
            'symbol': stock_symbol,
            'name': info.get('shortName', stock_symbol),
            'price': current_price_won,
            'change_pct': change_pct,
            'market_cap': market_cap,
            'market_cap_unit': market_cap_unit,
            'high_52w': high_52w_won,
            'low_52w': low_52w_won,
            'sector': info.get('sector', 'N/A'),
            'industry': info.get('industry', 'N/A'),
            'ma_5': float(ma_5) * exchange_rate,
            'ma_20': float(ma_20) * exchange_rate,
            'ma_60': float(ma_60) * exchange_rate,
            'ma_120': float(ma_120) * exchange_rate,
            'rsi': float(rsi),
            'history': data,
            'currency': currency
        }
    except RuntimeError as e:
        raise  # 상위에서 429 안내 메시지 처리
    except Exception as e:
        print(f"Failed to get ticker '{stock_symbol}' reason: {e}")
        return None

def get_ai_analysis(stock_data):
    currency = stock_data['currency']
    price_format = f"{currency}{int(stock_data['price']):,d}"
    high_52w_format = f"{currency}{int(stock_data['high_52w']):,d}"
    low_52w_format = f"{currency}{int(stock_data['low_52w']):,d}"
    ma_5_format = f"{currency}{int(stock_data['ma_5']):,d}"
    ma_20_format = f"{currency}{int(stock_data['ma_20']):,d}"
    ma_60_format = f"{currency}{int(stock_data['ma_60']):,d}"
    ma_120_format = f"{currency}{int(stock_data['ma_120']):,d}"
    market_cap_format = f"{stock_data['market_cap']:,.1f} {stock_data['market_cap_unit']}"
    prompt = f"""
    다음 데이터를 바탕으로 {stock_data['name']} ({stock_data['symbol']})를 분석해 주세요. 분석은 자연스러운 한국어로, 문장을 완결하게 작성하며, 제공된 데이터를 정확히 반영하세요. 줄바꿈과 띄어쓰기를 명확히 하세요.

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
    {stock_data['name']} ({stock_data['symbol']}) 분석:\n
    - 현재 주가는 {price_format}이며, 전일 대비 {stock_data['change_pct']:+.1f}% 변동했습니다.\n
    - 주가 평가: [평가 문장]\n
    - 경쟁력: [경쟁력 문장]\n
    - 이동평균 분석: [분석 문장]\n
    - 종합 의견: [투자 의견]\n
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

# ====== UI (카카오톡 챗봇 스타일) ======
if "agreed" not in st.session_state:
    st.session_state.agreed = False
if "messages" not in st.session_state:
    st.session_state.messages = []

st.markdown("""
<style>
.chat-container {background-color: #0e0e11; padding: 20px; border-radius: 10px; max-width: 600px; margin: auto; font-family: 'Apple SD Gothic Neo', sans-serif; color: white;}
.bubble-user {background-color: #fee500; color: black; padding: 10px 15px; border-radius: 15px; margin: 5px 0; max-width: 70%; align-self: flex-end;}
.bubble-bot {background-color: #e5e5ea; color: black; padding: 15px; border-radius: 15px; margin: 5px 0; max-width: 70%; align-self: flex-start;}
.chat-row {display: flex; flex-direction: column;}
.card-title {font-size: 16px; font-weight: bold; margin-bottom: 4px;}
.card-subtitle {font-size: 14px; color: #666; margin-bottom: 12px;}
.card-button-row {display: flex; justify-content: space-between; gap: 10px; margin-top: 12px;}
.card-button-row button {flex: 1; background-color: #f1f1f1; border: none; border-radius: 8px; padding: 10px; font-weight: bold; cursor: pointer;}
.card-button-row button:hover {background-color: #e0e0e0;}
</style>
""", unsafe_allow_html=True)

if not st.session_state.agreed:
    st.markdown("""
    <div style="background-color: white; color: black; padding: 30px; border-radius: 10px; max-width: 700px; margin: 100px auto;">
        <h4>📌 <b>투자 조언 면책 조항</b></h4>
        <p>
        본 서비스는 주식 시장 정보 및 일반적인 조언을 제공하기 위한 목적입니다.<br>
        제공되는 정보는 <b>투자 권유가 아니며</b>, 실제 투자 판단은 사용자 본인의 책임 하에 이루어져야 합니다.<br>
        본 서비스로 인해 발생한 손익에 대해 <b>CHAT JOY</b>는 법적 책임을 지지 않습니다.<br>
        투자 전 반드시 전문가 상담을 권장드립니다.
        </p>
    </div>
    """, unsafe_allow_html=True)
    if st.button("✅ 동의하고 계속하기"):
        st.session_state.agreed = True
        st.rerun()

if st.session_state.agreed:
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    if not st.session_state.messages:
        st.session_state.messages.append(("bot", "카드웰컴"))

    for sender, msg in st.session_state.messages:
        if sender == "user":
            st.markdown(f"<div class='chat-row'><div class='bubble-user'>{msg}</div></div>", unsafe_allow_html=True)
        elif isinstance(msg, dict) and msg.get("chart"):
            st.markdown(f"<div class='chat-row'><div class='bubble-bot'><b>{msg['name']} 차트</b></div></div>", unsafe_allow_html=True)
            fig = plot_stock_chart(msg["chart"], msg["name"])
            st.pyplot(fig)
            plt.close(fig)
        elif msg == "카드웰컴":
            st.markdown("""
            <div class="chat-row">
                <div class="bubble-bot">
                    <div class="card-title">주식의 길라잡이 CHAT JOY</div>
                    <div class="card-subtitle">무엇을 도와드릴까요?</div>
                    <div class="card-button-row">
            """, unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("오늘의 시장 요약", key="summary"):
                    st.session_state.messages.append(("user", "오늘의 시장 요약"))
                    st.session_state.messages.append(("bot", "📈 오늘 시장은 코스피 +0.42%, 나스닥 +0.58%로 상승 마감했습니다."))
                    st.rerun()
            with col2:
                if st.button("실시간 주식 시세", key="price"):
                    st.session_state.messages.append(("user", "실시간 주식 시세"))
                    st.session_state.messages.append(("bot", "관심 있는 종목명을 입력해주시면 실시간 시세를 안내해드릴게요!"))
                    st.rerun()
            st.markdown("</div></div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div class='chat-row'><div class='bubble-bot'>{msg}</div></div>", unsafe_allow_html=True)

    user_input = st.chat_input("종목명을 입력하세요...")
    if user_input:
        st.session_state.messages.append(("user", user_input))
        ticker = get_ticker_from_name(user_input)
        if ticker:
            try:
                stock_data = get_stock_info(ticker)
                if stock_data:
                    currency = stock_data['currency']
                    price_str = f"{currency}{int(stock_data['price']):,d}"
                    change_str = f"({stock_data['change_pct']:+.1f}%)"
                    basic_info = (
                        f"**{stock_data['name']} ({ticker})**\n"
                        f"- 현재가: {price_str} {change_str}\n"
                        f"- 시가총액: {stock_data['market_cap']:,.1f} {stock_data['market_cap_unit']}\n"
                        f"- 52주 고가: {currency}{int(stock_data['high_52w']):,d}\n"
                        f"- 52주 저가: {currency}{int(stock_data['low_52w']):,d}\n"
                        f"- RSI: {stock_data['rsi']:.1f}\n"
                        f"- 환율 적용: 1 USD = {exchange_rate:,.0f} KRW\n"
                    )
                    analysis = get_ai_analysis(stock_data)
                    st.session_state.messages.append(("bot", basic_info))
                    st.session_state.messages.append(("bot", f"**🤖 AI 분석**\n{analysis}"))
                    st.session_state.messages.append(("bot", {"chart": stock_data, "name": stock_data["name"]}))
                else:
                    st.session_state.messages.append(
                        ("bot", f"❌ [{ticker}]에 대한 정보를 불러올 수 없습니다. (야후 파이낸스 KRX 데이터가 없는 경우일 수 있습니다)")
                    )
            except RuntimeError as e:
                st.session_state.messages.append(
                    ("bot", "❌ 데이터 요청이 너무 많아 야후 파이낸스에서 차단되었습니다. 잠시 후 다시 시도해 주세요.")
                )
            except Exception as e:
                st.session_state.messages.append(
                    ("bot", f"❌ 데이터 조회 중 에러 발생: {e}")
                )
        else:
            st.session_state.messages.append(
                ("bot", "❌ 종목명을 인식할 수 없습니다. 정확한 종목명을 입력하거나, 티커를 직접 입력해 주세요.")
            )
    st.markdown('</div>', unsafe_allow_html=True)