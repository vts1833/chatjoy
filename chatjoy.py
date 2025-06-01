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
from datetime import datetime
from xml.etree import ElementTree

warnings.filterwarnings('ignore')

# ====== 주식 용어 사전 ======
term_dict = {
    "PER": "주가수익비율은 주가를 주당순이익(EPS)으로 나눈 값입니다. 숫자가 작을수록 저평가된 주식일 수 있습니다.",
    "PBR": "주가순자산비율은 주가를 주당순자산(BPS)으로 나눈 값입니다. 1보다 낮으면 자산 대비 주가가 낮은 상태입니다.",
    "시가총액": "기업의 전체 시장 가치입니다. 주가 × 총 주식 수로 계산합니다.",
    "배당": "기업이 이익의 일부를 주주에게 돌려주는 것을 말합니다. 배당 수익률은 투자자 입장에서 중요한 수익 요소입니다.",
    "우선주": "의결권은 없지만 보통주보다 배당을 우선적으로 받을 수 있는 주식입니다.",
    "분할": "주식을 쪼개는 것(예: 1주 → 5주). 유동성을 높이고 개인 투자자 접근성을 높입니다.",
    "ETF": "여러 종목을 묶어 하나처럼 거래하는 상장지수펀드입니다. 분산투자에 유리합니다.",
}

# ====== FAQ 목록 (고객센터용) ======
faq_list = [
    {"question": "주식 분석은 어떻게 하나요?", "answer": "종목명을 입력하면 주가, 시가총액, 52주 범위, RSI 등을 분석하고 AI 기반의 투자 의견을 제공합니다.", "keywords": ["주식 분석", "분석 방법"]},
    {"question": "환율은 어떻게 적용되나요?", "answer": "미국 주식의 경우 USD를 KRW로 변환하기 위해 네이버 환율 API를 사용하며, 기본값은 1340원입니다.", "keywords": ["환율", "환율 적용"]},
    {"question": "관심 종목은 몇 개까지 추가 가능하나요?", "answer": "최대 10개의 종목을 관심 목록에 추가할 수 있습니다.", "keywords": ["관심 종목", "추가 가능"]},
    {"question": "뉴스 데이터는 어디서 가져오나요?", "answer": "네이버 뉴스 API를 통해 최신 주식 관련 뉴스를 제공합니다.", "keywords": ["뉴스", "데이터 출처"]},
]

# ====== 네이버 뉴스 API ======
client_id = "tkTiayD7fq2F1vrMY4kj"  # ★본인 키로 교체 필요
client_secret = "z6xSBpF14j"  # ★본인 키로 교체 필요

def search_naver_news(query, display=100):
    url = "https://openapi.naver.com/v1/search/news.xml"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": display,
        "sort": "date"
    }
    try:
        res = requests.get(url, headers=headers, params=params)
        res.raise_for_status()
        root = ElementTree.fromstring(res.content)
        news_list = []
        for item in root.findall('./channel/item'):
            title = item.findtext('title').replace("<b>", "").replace("</b>", "")
            link = item.findtext('link')
            pubDate = item.findtext('pubDate')
            pubDate = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d %H:%M")
            news_list.append((pubDate, title, link))
        return news_list
    except Exception as e:
        st.error(f"뉴스 검색 중 오류 발생: {str(e)}")
        return []

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
            return font_prop, True
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['axes.unicode_minus'] = False
            st.warning("NanumGothic 폰트를 찾을 수 없습니다. 기본 폰트로 출력됩니다.")
            return None, False
    except Exception as e:
        st.error(f"폰트 설정 중 오류 발생: {str(e)}")
        plt.rcParams['font.family'] = 'sans-serif'
        return None, False

font_prop, font_available = setup_font()

# KRX 종목명-티커 매핑
try:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        krx_map = json.load(f)
except FileNotFoundError:
    st.warning(f"krx_ticker_map.json 파일을 찾을 수 없습니다: {JSON_PATH}")
    krx_map = {}

# 환율 API (네이버 기반)
def get_exchange_rate():
    try:
        url = "https://m.search.naver.com/p/csearch/content/qapirender.nhn?key=calculator&pkid=141&q=%ED%99%98%EC%9C%A8&where=m&u1=keb&u6=standardUnit&u7=0&u3=USD&u4=KRW&u8=down&u2=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=5).json()
        if 'country' in res and len(res['country']) > 1:
            krw_rate = float(res['country'][1]['value'].replace(',', ''))
            return krw_rate
        else:
            st.warning("API 응답 오류. 기본 환율 1340 적용.")
            return 1340
    except Exception as e:
        st.warning(f"환율 API 요청 실패: {str(e)}. 기본 환율 1340 적용.")
        return 1340

exchange_rate = get_exchange_rate()

# OpenAI API 세팅 (Azure)
openai.api_key = "3p1vX5a5zu1nTmEdd0lxhT1E0lpkNKq2vmUif4GrGv0eRa1jV7rHJQQJ99BCACHYHv6XJ3w3AAAAACOGR64o"
openai.api_base = "https://ai-jhs51470758ai014414829313.openai.azure.com/"
openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"

# 티커 조회
def get_ticker_from_name(stock_name, kr_tickers):
    name = stock_name.strip()
    if name in kr_tickers:
        return kr_tickers[name]
    if name.isupper() and len(name) <= 6:
        return name
    return None

# 주식 정보 조회
@lru_cache(maxsize=64)
def get_stock_info(stock_symbol, exchange_rate):
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
        
        # 한국 주식 여부 확인: 티커가 .KS 또는 .KQ로 끝나면 한국 주식
        is_korean_stock = stock_symbol.endswith('.KS') or stock_symbol.endswith('.KQ')
        currency = '₩'
        
        # 시장별 가격 처리
        if is_korean_stock:
            current_price_won = current_price
            high_52w_won = info.get('fiftyTwoWeekHigh', 0)
            low_52w_won = info.get('fiftyTwoWeekLow', 0)
            market_cap = info.get('marketCap', 0) / 1e12
            ma_5_converted = float(ma_5)
            ma_20_converted = float(ma_20)
            ma_60_converted = float(ma_60)
            ma_120_converted = float(ma_120)
        else:
            current_price_won = current_price * exchange_rate
            high_52w_won = info.get('fiftyTwoWeekHigh', 0) * exchange_rate
            low_52w_won = info.get('fiftyTwoWeekLow', 0) * exchange_rate
            market_cap = info.get('marketCap', 0) * exchange_rate / 1e12
            ma_5_converted = float(ma_5) * exchange_rate
            ma_20_converted = float(ma_20) * exchange_rate
            ma_60_converted = float(ma_60) * exchange_rate
            ma_120_converted = float(ma_120) * exchange_rate
        
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
            'ma_5': ma_5_converted,
            'ma_20': ma_20_converted,
            'ma_60': ma_60_converted,
            'ma_120': ma_120_converted,
            'rsi': float(rsi),
            'history': data,
            'currency': currency
        }
    except RuntimeError as e:
        raise
    except Exception as e:
        print(f"Failed to get ticker '{stock_symbol}' reason: {e}")
        return None

# 기술적 지표 계산
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

# AI 분석
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

# 차트 생성
def plot_stock_chart(stock_data, stock_name, font_prop):
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

# ====== 투자 성향 테스트 모듈 ======
questions = {
    1: ["주가가 갑자기 하락하면 어떻게 하시겠습니까?", ["손절한다", "기다린다", "추가매수한다"]],
    2: ["투자 목적은 무엇입니까?", ["단기수익", "장기성장", "기회형수익"]],
    3: ["감수할 수 있는 손실 범위는?", ["5퍼센트 이하", "10~15퍼센트", "20퍼센트 이상"]],
    4: ["급락장이 오면 어떻게 하시겠습니까?", ["현금화", "유지", "추가매수"]],
    5: ["본인의 투자 경험은?", ["처음이다", "약간 있다", "전문가 수준"]]
}

def get_profile(total):
    if total <= 7:
        return "안정형 투자자"
    elif total <= 11:
        return "중립형 투자자"
    else:
        return "공격형 투자자"

# ====== UI 렌더링 함수 ======
def render_chat_bubble(role, text):
    if role == "user":
        st.markdown(f"<div class='chat-row'><div class='bubble-user'>{text}</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='chat-row'><div class='bubble-bot'>{text}</div></div>", unsafe_allow_html=True)

# ====== UI (카카오톡 스타일 CSS) ======
st.markdown("""
<style>
.chat-container {background-color: transparent; padding: 0; border-radius: 10px; max-width: 600px; margin: auto; font-family: 'Apple SD Gothic Neo', sans-serif; color: white; min-height: 0;}
.bubble-user {background-color: #fee500; color: black; padding: 10px 15px; border-radius: 15px; margin: 5px 0; max-width: 70%; align-self: flex-end;}
.bubble-bot {background-color: #e5e5ea; color: black; padding: 15px; border-radius: 15px; margin: 5px 0; max-width: 70%; align-self: flex-start;}
.chat-row {display: flex; flex-direction: column;}
.card-title {font-size: 16px; font-weight: bold; margin-bottom: 4px;}
.card-subtitle {font-size: 14px; color: #666; margin-bottom: 12px;}
</style>
""", unsafe_allow_html=True)

# ====== 사이드바 메뉴 ======
st.sidebar.title("메뉴")
app_mode = st.sidebar.selectbox("기능 선택", ["주식 분석", "투자 성향 테스트", "네이버 뉴스 요약", "주식 용어 사전", "관심 종목 관리", "고객센터"])

# ====== 세션 상태 초기화 ======
if "agreed" not in st.session_state:
    st.session_state.agreed = False
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "주식의 길라잡이 CHAT JOY<br>분석할 종목명을 말씀해 주세요! (예: 삼성전자, AAPL)"}
    ]
if 'question_number' not in st.session_state:
    st.session_state.question_number = 1
if 'answers' not in st.session_state:
    st.session_state.answers = []
if 'test_chat_log' not in st.session_state:
    st.session_state.test_chat_log = []
if 'result_shown' not in st.session_state:
    st.session_state.result_shown = False
if 'news_messages' not in st.session_state:
    st.session_state.news_messages = []
if "news_items" not in st.session_state:
    st.session_state.news_items = []
if "news_display_count" not in st.session_state:
    st.session_state.news_display_count = 5
if "news_query" not in st.session_state:
    st.session_state.news_query = ""
if "interest_list" not in st.session_state:
    st.session_state.interest_list = []
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None
if "terms_messages" not in st.session_state:
    st.session_state.terms_messages = []
if "last_term_search" not in st.session_state:
    st.session_state.last_term_search = ""
if "interest_chat_log" not in st.session_state:
    st.session_state.interest_chat_log = []
if "faq_messages" not in st.session_state:
    st.session_state.faq_messages = []
if "bot_icon_base64" not in st.session_state:
    st.session_state.bot_icon_base64 = ""  # 아이콘 미사용 시 빈 문자열

# ====== 모드 전환 시 대화 로그 초기화 ======
if "last_mode" not in st.session_state:
    st.session_state.last_mode = app_mode
if st.session_state.last_mode != app_mode:
    if app_mode == "투자 성향 테스트":
        st.session_state.test_chat_log = []
        st.session_state.question_number = 1
        st.session_state.answers = []
        st.session_state.result_shown = False
    elif app_mode == "관심 종목 관리":
        st.session_state.interest_chat_log = []
        st.session_state.selected_stock = None
    elif app_mode == "주식 용어 사전":
        st.session_state.terms_messages = []
        st.session_state.last_term_search = ""
    elif app_mode == "고객센터":
        st.session_state.faq_messages = []
    st.session_state.last_mode = app_mode

# ====== 주식 분석 모드 ======
if app_mode == "주식 분석":
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
    else:
        with st.container():
            for msg in st.session_state.messages:
                if msg.get('chart_data'):
                    render_chat_bubble("assistant", f"<b>{msg['stock_name']} 차트</b>")
                    fig = plot_stock_chart(msg['chart_data'], msg['stock_name'], font_prop)
                    st.pyplot(fig)
                    plt.close(fig)
                else:
                    render_chat_bubble(msg['role'], msg['content'])

            def handle_input():
                stock_name = st.session_state.stock_input
                if not stock_name:
                    return
                st.session_state.messages.append({"role": "user", "content": stock_name})
                ticker = get_ticker_from_name(stock_name, krx_map)
                if not ticker:
                    st.session_state.messages.append({"role": "assistant", "content": "❌ 종목명을 찾을 수 없습니다."})
                else:
                    with st.spinner("분석 중..."):
                        data = get_stock_info(ticker, exchange_rate)
                        if data:
                            currency = data['currency']
                            price_str = f"{currency}{int(data['price']):,d}"
                            change_str = f"({data['change_pct']:+.1f}%)"
                            basic_info = (
                                f"<b>{data['name']} ({ticker})</b><br>"
                                f"- 현재가: {price_str} {change_str}<br>"
                                f"- 시가총액: {data['market_cap']:,.1f} {data['market_cap_unit']}<br>"
                                f"- 52주 고가: {currency}{int(data['high_52w']):,d}<br>"
                                f"- 52주 저가: {currency}{int(data['low_52w']):,d}<br>"
                                f"- RSI: {data['rsi']:.1f}<br>"
                                f"- 환율 적용: 1 USD = {exchange_rate:,.0f} KRW"
                            )
                            analysis = get_ai_analysis(data)
                            response = f"{basic_info}<br><br><b>🤖 AI 분석</b><br>{analysis}"
                            st.session_state.messages.append({"role": "assistant", "content": response})
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"<b>{stock_name} 차트</b>",
                                "chart_data": data,
                                "stock_name": stock_name
                            })
                        else:
                            st.session_state.messages.append({
                                "role": "assistant",
                                "content": f"❌ [{ticker}]에 대한 정보를 불러올 수 없습니다."
                            })
                st.session_state.stock_input = ""

            st.text_input("종목명을 입력하세요 (예: 삼성전자, AAPL)", key="stock_input", on_change=handle_input)

# ====== 투자 성향 테스트 모드 ======
elif app_mode == "투자 성향 테스트":
    with st.container():
        for msg in st.session_state.test_chat_log:
            render_chat_bubble(msg['role'], msg['text'])

        q_num = st.session_state.question_number
        if q_num <= 5:
            question, choices = questions[q_num]
            q_text = f"Q{q_num}. {question}"
            render_chat_bubble("bot", q_text)

            cols = st.columns(len(choices))
            for idx, choice in enumerate(choices):
                with cols[idx]:
                    if st.button(choice, key=f"choice_{q_num}_{idx}"):
                        st.session_state.answers.append(idx + 1)
                        st.session_state.test_chat_log.append({"role": "user", "text": choice})
                        st.session_state.question_number += 1
                        st.rerun()

        elif not st.session_state.result_shown:
            total = sum(st.session_state.answers)
            profile = get_profile(total)
            result_text = f"✅ 테스트 완료! 당신은 '{profile}'입니다."
            st.session_state.test_chat_log.append({"role": "bot", "text": result_text})
            st.session_state.result_shown = True
            st.rerun()

        if st.button("🔄 다시 테스트하기"):
            for key in ['question_number', 'answers', 'test_chat_log', 'result_shown']:
                st.session_state.pop(key, None)
            st.rerun()

# ====== 네이버 뉴스 요약 모드 ======
elif app_mode == "네이버 뉴스 요약":
    with st.container():
        st.markdown("<b>📰 네이버 뉴스 요약</b><br>종목명을 입력하여 관련 뉴스를 확인하세요.", unsafe_allow_html=True)

        for sender, msg in st.session_state.news_messages:
            render_chat_bubble(sender, msg)

        query = st.text_input("종목명을 입력하세요 (예: 삼성전자)", key="news_query_input")
        if query and query != st.session_state.news_query:
            ticker = get_ticker_from_name(query, krx_map)
            st.session_state.news_query = query
            if ticker:
                st.session_state.news_items = search_naver_news(ticker)
                st.session_state.news_display_count = 5
                st.session_state.news_messages = [("user", query)]
                if st.session_state.news_items:
                    for i, (pubDate, title, link) in enumerate(st.session_state.news_items[:5]):
                        news_text = f"🔗 <a href='{link}' target='_blank'>{title}</a> - 🕒 {pubDate}"
                        st.session_state.news_messages.append(("bot", news_text))
                else:
                    st.session_state.news_messages.append(("bot", "❌ 뉴스를 불러오지 못했습니다."))
            else:
                st.session_state.news_messages = [("user", query), ("bot", "❌ 유효한 티커를 찾을 수 없습니다.")]
            st.rerun()

        if st.session_state.news_items and len(st.session_state.news_items) > st.session_state.news_display_count:
            if st.button("더보기"):
                start = st.session_state.news_display_count
                end = min(start + 5, len(st.session_state.news_items))
                for i in range(start, end):
                    pubDate, title, link = st.session_state.news_items[i]
                    news_text = f"🔗 <a href='{link}' target='_blank'>{title}</a> - 🕒 {pubDate}"
                    st.session_state.news_messages.append(("bot", news_text))
                st.session_state.news_display_count = end
                st.rerun()

# ====== 주식 용어 사전 모드 ======
elif app_mode == "주식 용어 사전":
    with st.container():
        st.markdown("<b>📚 주식 초보자용 용어 사전</b><br>초보 투자자들이 자주 접하는 주식 용어를 쉽게 설명합니다.", unsafe_allow_html=True)

        for sender, msg in st.session_state.terms_messages:
            render_chat_bubble(sender, msg)

        user_input = st.chat_input("궁금한 용어를 입력해보세요 (예: PER, 배당, ETF 등)", key="term_input")
        if user_input:
            st.session_state.terms_messages.append(("user", user_input))
            key = user_input.strip().upper().replace(" ", "")
            matched = None
            for term in term_dict:
                if key in term.upper().replace(" ", ""):
                    matched = term
                    break
            if matched:
                response = f"✅ <b>{matched}</b><br>{term_dict[matched]}"
                st.session_state.terms_messages.append(("bot", response))
            else:
                st.session_state.terms_messages.append(("bot", "❗ 용어를 찾을 수 없습니다. 다른 키워드를 시도해보세요."))
            st.session_state.last_term_search = user_input
            st.rerun()

        with st.expander("📘 전체 용어 목록 보기"):
            for term, desc in term_dict.items():
                st.markdown(f"<div style='margin-bottom: 10px;'><b>{term}</b>: {desc}</div>", unsafe_allow_html=True)

# ====== 관심 종목 관리 모드 ======
elif app_mode == "관심 종목 관리":
    with st.container():
        st.markdown("<b>📈 관심 종목 관리</b><br>종목을 추가하거나 삭제하고 주가 정보를 확인하세요.", unsafe_allow_html=True)

        for msg in st.session_state.interest_chat_log:
            render_chat_bubble(msg['role'], msg['text'])

        user_input = st.chat_input("예: 삼성전자 추가 / 카카오 삭제")
        if user_input:
            st.session_state.interest_chat_log.append({"role": "user", "text": user_input})
            utterance = user_input.strip()
            reply_log = []
            stock_name = utterance.replace("추가", "").replace("삭제", "").replace("제거", "").replace("빼", "").replace("지워", "").strip()
            current = st.session_state.interest_list

            if stock_name in krx_map:
                if any(word in utterance for word in ["삭제", "제거", "빼", "지워"]):
                    if stock_name in current:
                        current.remove(stock_name)
                        reply_log.append(f"✅ {stock_name} 삭제되었습니다.")
                    else:
                        reply_log.append(f"⚠️ {stock_name}은(는) 등록되어 있지 않아요.")
                else:
                    if stock_name not in current:
                        if len(current) < 10:
                            current.append(stock_name)
                            reply_log.append(f"✅ {stock_name} 종목이 추가되었습니다.")
                        else:
                            reply_log.append("❗ 최대 10개까지 등록 가능합니다.")
                    else:
                        reply_log.append(f"⚠️ {stock_name}은(는) 이미 등록되어 있어요.")
            else:
                reply_log.append(f"⚠️ {stock_name}은(는) 유효한 종목명이 아닙니다.")

            for line in reply_log:
                st.session_state.interest_chat_log.append({"role": "bot", "text": line})
            if current:
                msg = f"📋 현재 관심 종목은 {len(current)}개입니다."
                st.session_state.interest_chat_log.append({"role": "bot", "text": msg})
            st.rerun()

        if not st.session_state.interest_chat_log and st.session_state.interest_list:
            current = st.session_state.interest_list
            intro_msg = f"📋 현재 관심 종목은 {len(current)}개입니다."
            st.session_state.interest_chat_log.append({"role": "bot", "text": intro_msg})
            render_chat_bubble("bot", intro_msg)

        if st.session_state.interest_list:
            st.markdown("### 📈 관심 종목 주가 보기")
            cols = st.columns(min(len(st.session_state.interest_list), 5))
            for i, stock in enumerate(st.session_state.interest_list):
                with cols[i % 5]:
                    if st.button(stock):
                        st.session_state.selected_stock = stock
                        st.rerun()

        selected = st.session_state.get("selected_stock")
        if selected and selected in krx_map:
            try:
                ticker = krx_map[selected]
                stock = yf.Ticker(ticker)
                info = stock.info

                price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
                change = info.get("regularMarketChangePercent", 0.0)
                per = info.get("trailingPE", "-")
                pbr = info.get("priceToBook", "-")
                market_cap = info.get("marketCap", 0)

                summary = (
                    f"✅ <b>{selected} 주가 요약</b><br>"
                    f"- 현재가: {int(price):,}원<br>"
                    f"- 변동률: {change:.2f}%<br>"
                    f"- 시가총액: {market_cap / 1e12:.2f}조 원<br>"
                    f"- PER: {per}<br>"
                    f"- PBR: {pbr}"
                )
                st.session_state.interest_chat_log.append({"role": "bot", "text": summary})
                render_chat_bubble("bot", summary)
                st.session_state.selected_stock = None
                st.rerun()
            except Exception as e:
                error_msg = f"⚠️ {selected} 데이터를 불러오는 데 실패했습니다.<br>{str(e)}"
                st.session_state.interest_chat_log.append({"role": "bot", "text": error_msg})
                render_chat_bubble("bot", error_msg)
                st.session_state.selected_stock = None
                st.rerun()

# ====== 고객센터 모드 ======
elif app_mode == "고객센터":
    with st.container():
        st.title("📞 고객센터 챗봇")
        st.markdown("무엇을 도와드릴까요? 아래에서 자주 묻는 질문을 확인해보세요.")

        # 카드형 FAQ 보기
        st.subheader("📋 자주 묻는 질문")
        for item in faq_list:
            with st.expander("❓ " + item["question"]):
                st.markdown("💬 " + item["answer"])

        user_input = st.chat_input("추가 문의가 있다면 입력해주세요.", key="faq_input")
        if user_input:
            st.session_state.faq_messages.append(("user", user_input))
            matched_faq = None
            user_input_lower = user_input.lower().strip()
            for faq in faq_list:
                for keyword in faq["keywords"]:
                    if keyword.lower() in user_input_lower:
                        matched_faq = faq
                        break
                if matched_faq:
                    break
            if matched_faq:
                response = f"✅ <b>{matched_faq['question']}</b><br>{matched_faq['answer']}"
            else:
                response = "죄송합니다. 현재는 등록된 질문에만 답변 가능합니다. 상단 FAQ를 참고해주세요!"
            st.session_state.faq_messages.append(("assistant", response))
            st.rerun()

        for sender, msg in st.session_state.faq_messages:
            render_chat_bubble(sender, msg)
