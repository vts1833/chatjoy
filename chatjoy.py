import streamlit as st
import openai
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import json
import warnings
import os
import requests

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
            # st.success(f"{font_name} 폰트 설정 완료.") # Optional: for debugging
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
    # Ensure the path is correct if running from a specific directory or in Streamlit Cloud
    # For local development, 'krx_ticker_map.json' in the same directory is fine.
    # For Streamlit Cloud, ensure this file is in your repository.
    with open('krx_ticker_map.json', 'r', encoding='utf-8') as f:
        kr_tickers = json.load(f)
except FileNotFoundError:
    st.warning("krx_ticker_map.json 파일을 찾을 수 없습니다. 한국 종목명 검색이 제한될 수 있습니다.")
    kr_tickers = {}
except json.JSONDecodeError:
    st.error("krx_ticker_map.json 파일 형식 오류. 유효한 JSON 파일인지 확인하세요.")
    kr_tickers = {}


# 환율 API 설정 (exchangerate-api.com 사용)
def get_exchange_rate():
    try:
        api_key = "a7ce46583c0498045e014086"  # 실제 API 키
        url = f"https://v6.exchangerate-api.com/v6/a7ce46583c0498045e014086/latest/USD"
        response = requests.get(url, timeout=10) # Increased timeout
        response.raise_for_status() # Will raise an HTTPError if the HTTP request returned an unsuccessful status code
        data = response.json()
        if data['result'] == 'success' and 'conversion_rates' in data and 'KRW' in data['conversion_rates']:
            return data['conversion_rates']['KRW']
        else:
            st.warning(f"환율 API 응답 오류: {data.get('error-type', '알 수 없는 오류')}. 기본 환율(1350)을 사용합니다.")
            return 1350 # Default exchange rate
    except requests.exceptions.RequestException as e:
        st.warning(f"환율 API 요청 실패 (네트워크 또는 API 서버 문제): {str(e)}. 기본 환율(1350)을 사용합니다.")
        return 1350
    except Exception as e: # Catch other potential errors like JSONDecodeError if response is not JSON
        st.warning(f"환율 정보 처리 중 예상치 못한 오류: {str(e)}. 기본 환율(1350)을 사용합니다.")
        return 1350

exchange_rate = get_exchange_rate()

# OpenAI 설정
# 환경 변수에서 API 키를 로드하는 것이 더 안전합니다.
# 예: openai.api_key = os.getenv("AZURE_OPENAI_API_KEY")
# openai.api_key = "YOUR_AZURE_OPENAI_KEY" # 실제 키로 교체하거나 환경 변수 사용
# openai.api_base = "YOUR_AZURE_OPENAI_ENDPOINT" # 실제 엔드포인트로 교체하거나 환경 변수 사용
# openai.api_type = "azure"
# openai.api_version = "2023-03-15-preview" # 또는 사용 가능한 최신 안정 버전

# For testing without exposing real keys directly in code
# Please replace with your actual keys or use environment variables for production
try:
    openai.api_key = st.secrets["azure_openai"]["api_key"]
    openai.api_base = st.secrets["azure_openai"]["api_base"]
    openai.api_type = st.secrets["azure_openai"]["api_type"]
    openai.api_version = st.secrets["azure_openai"]["api_version"]
    AZURE_OPENAI_ENGINE = st.secrets["azure_openai"]["engine"]
except (KeyError, FileNotFoundError): # FileNotFoundError for local secrets.toml
    st.error("Azure OpenAI API 키 또는 엔드포인트가 설정되지 않았습니다. Streamlit secrets를 확인하세요.")
    # Provide dummy values or disable AI features if keys are not found
    openai.api_key = "DUMMY_KEY"
    openai.api_base = "DUMMY_BASE"
    openai.api_type = "azure"
    openai.api_version = "2023-03-15-preview"
    AZURE_OPENAI_ENGINE = "gpt-35-turbo" # default engine name
    st.info("AI 분석 기능이 제한될 수 있습니다.")


def get_ticker_from_name(stock_name_input):
    """
    한국 주식은 krx_ticker_map.json에서, 그 외에는 yfinance로 티커를 확인합니다.
    숫자로만 된 경우 한국 티커(.KS, .KQ)로 시도합니다.
    """
    stock_name_input_clean = stock_name_input.strip()
    stock_name_lower = stock_name_input_clean.lower()

    # 1. Check Korean name map first (exact match for Korean names)
    if stock_name_input_clean in kr_tickers:
        return kr_tickers[stock_name_input_clean]

    # 2. Try direct ticker with .KS or .KQ for Korean codes if input is numerical
    # Heuristic: if it's all digits and 6 chars long, common for KR tickers
    if stock_name_input_clean.isdigit() and len(stock_name_input_clean) == 6:
        for suffix in ['.KS', '.KQ']: # KOSPI, KOSDAQ
            try:
                ticker_candidate = stock_name_input_clean + suffix
                stock_test = yf.Ticker(ticker_candidate)
                # Check if info is populated and has a symbol (more reliable than just not erroring)
                if stock_test.info and 'symbol' in stock_test.info and stock_test.info['symbol'] == ticker_candidate:
                    return ticker_candidate
            except Exception: # Catches yfinance errors if ticker is invalid
                continue # Try next suffix or fall through

    # 3. Assume US or other international ticker (or KR ticker already with .KS/.KQ)
    try:
        # yfinance can sometimes find tickers even if they are not strictly uppercase.
        # If it already contains a '.', assume it's a full ticker like '005930.KS' or 'BRK-A'
        # Forcing uppercase can be an issue for some non-US tickers if not already specified.
        ticker_to_check = stock_name_input_clean
        if '.' not in ticker_to_check: # If no exchange specified, often US, so try uppercase
             ticker_to_check = stock_name_input_clean.upper()

        stock = yf.Ticker(ticker_to_check)
        if stock.info and 'symbol' in stock.info: # 'symbol' is a good check
            return stock.info['symbol'] # Return the validated symbol from yfinance

        # As a fallback, try the original input if the uppercase version failed
        if ticker_to_check != stock_name_input_clean:
            stock_orig = yf.Ticker(stock_name_input_clean)
            if stock_orig.info and 'symbol' in stock_orig.info:
                return stock_orig.info['symbol']
        return None
    except Exception as e:
        # st.info(f"yfinance 티커 조회 중 오류 (get_ticker_from_name): {e}") # For debugging
        return None

def calculate_technical_indicators(stock_symbol):
    data = yf.download(stock_symbol, period="1y", progress=False, auto_adjust=True) # auto_adjust True is often better
    if data.empty:
        raise ValueError(f"{stock_symbol}에 대한 데이터를 다운로드할 수 없습니다.")
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
    
    # Handle division by zero for RS
    rs = np.where(avg_loss == 0, np.inf if avg_gain.any() > 0 else 1, avg_gain / avg_loss) # Avoid division by zero
    rsi = 100 - (100 / (1 + rs))
    rsi = np.clip(rsi, 0, 100) # Ensure RSI is within 0-100

    return ma_5.iloc[-1], ma_20.iloc[-1], ma_60.iloc[-1], ma_120.iloc[-1], rsi.iloc[-1], data

def get_stock_info(stock_symbol):
    stock = yf.Ticker(stock_symbol)
    info = stock.info
    if not info or 'symbol' not in info: # Check if info was successfully retrieved
        st.error(f"{stock_symbol}에 대한 정보를 yfinance에서 가져올 수 없습니다. 티커를 확인해주세요.")
        return None

    # Determine if it's a Korean stock
    is_korean_stock = stock_symbol.endswith(('.KS', '.KQ'))
    applied_exchange_rate = False # Flag to track if exchange rate was applied

    # Download history and calculate indicators
    try:
        ma_5_raw, ma_20_raw, ma_60_raw, ma_120_raw, rsi, data = calculate_technical_indicators(stock_symbol)
    except ValueError as e:
        st.error(str(e))
        return None # Cannot proceed without data

    history = data # Use the data returned by calculate_technical_indicators
    current_price_raw = history['Close'].iloc[-1]
    prev_close_raw = history['Close'].iloc[-2] if len(history) > 1 else current_price_raw
    change_pct = (current_price_raw - prev_close_raw) / prev_close_raw * 100 if prev_close_raw else 0

    currency_symbol = '₩' # Default to Won as we convert everything to Won
    market_cap_unit = '조 원'
    raw_market_cap = info.get('marketCap', 0)

    if is_korean_stock:
        # Data is already in KRW
        current_price_converted = current_price_raw
        high_52w_converted = info.get('fiftyTwoWeekHigh', 0)
        low_52w_converted = info.get('fiftyTwoWeekLow', 0)
        # Market cap from yfinance for KR stocks is in KRW. Convert to 조 원.
        market_cap_converted = raw_market_cap / 1e12 if raw_market_cap else 0
        ma_5_converted = float(ma_5_raw)
        ma_20_converted = float(ma_20_raw)
        ma_60_converted = float(ma_60_raw)
        ma_120_converted = float(ma_120_raw)
    else:
        # Data is likely in USD (or other foreign currency, assuming yfinance standardizes to USD for .info['marketCap'])
        # Convert to KRW using the fetched exchange_rate
        current_price_converted = current_price_raw * exchange_rate
        high_52w_converted = info.get('fiftyTwoWeekHigh', 0) * exchange_rate
        low_52w_converted = info.get('fiftyTwoWeekLow', 0) * exchange_rate
        # Market cap from yfinance for US stocks is in USD. Convert to 조 원.
        market_cap_converted = (raw_market_cap * exchange_rate) / 1e12 if raw_market_cap else 0
        ma_5_converted = float(ma_5_raw) * exchange_rate
        ma_20_converted = float(ma_20_raw) * exchange_rate
        ma_60_converted = float(ma_60_raw) * exchange_rate
        ma_120_converted = float(ma_120_raw) * exchange_rate
        applied_exchange_rate = True

    return {
        'symbol': stock_symbol,
        'name': info.get('shortName', info.get('longName', stock_symbol)), # Fallback for name
        'price': current_price_converted,
        'change_pct': change_pct,
        'market_cap': market_cap_converted,
        'market_cap_unit': market_cap_unit,
        'high_52w': high_52w_converted,
        'low_52w': low_52w_converted,
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'ma_5': ma_5_converted,
        'ma_20': ma_20_converted,
        'ma_60': ma_60_converted,
        'ma_120': ma_120_converted,
        'rsi': float(rsi) if pd.notna(rsi) else np.nan, # Ensure RSI is float or NaN
        'history': history, # This data is NOT currency converted for MAs; MAs in the dict are.
        'currency_symbol': currency_symbol, # Symbol for display '₩'
        'applied_exchange_rate': applied_exchange_rate, # Boolean flag
        'original_currency': info.get('currency', 'USD' if not is_korean_stock else 'KRW') # Store original currency
    }

def get_ai_analysis(stock_data):
    if openai.api_key == "DUMMY_KEY": # Check if using dummy keys
        return "AI 분석을 위한 API 키가 설정되지 않았습니다. 관리자에게 문의하세요."

    currency = stock_data['currency_symbol']
    price_format = f"{currency}{int(stock_data['price']):,d}"
    high_52w_format = f"{currency}{int(stock_data['high_52w']):,d}"
    low_52w_format = f"{currency}{int(stock_data['low_52w']):,d}"
    ma_5_format = f"{currency}{int(stock_data['ma_5']):,d}"
    ma_20_format = f"{currency}{int(stock_data['ma_20']):,d}"
    ma_60_format = f"{currency}{int(stock_data['ma_60']):,d}"
    ma_120_format = f"{currency}{int(stock_data['ma_120']):,d}"
    market_cap_format = f"{stock_data['market_cap']:,.1f} {stock_data['market_cap_unit']}"
    rsi_value = stock_data['rsi']
    rsi_format = f"{rsi_value:.1f}" if pd.notna(rsi_value) else "N/A"


    prompt = f"""
    다음 데이터를 바탕으로 {stock_data['name']} ({stock_data['symbol']}) 주식에 대해 분석해 주세요. 모든 수치는 제공된 데이터를 정확히 사용하고, 자연스러운 한국어 문장으로 완결성 있게 작성해 주세요. 줄바꿈과 띄어쓰기를 명확히 하고, 특히 수치 데이터는 정확하게 반영해야 합니다.

    - 종목명: {stock_data['name']} ({stock_data['symbol']})
    - 현재가: {price_format} (전일 대비 {stock_data['change_pct']:+.1f}%)
    - 시가총액: {market_cap_format}
    - 52주 변동폭: {low_52w_format} ~ {high_52w_format}
    - 소속 업종: {stock_data['sector']} (산업: {stock_data['industry']})
    - 주요 이동평균선: 5일 이평선 {ma_5_format}, 20일 이평선 {ma_20_format}, 60일 이평선 {ma_60_format}, 120일 이평선 {ma_120_format}
    - 상대강도지수(RSI): {rsi_format}
    {f"- (참고: 미국 달러당 원화 환율 {exchange_rate:,.0f}원 적용됨)" if stock_data['applied_exchange_rate'] else ""}

    분석 요청사항:
    1.  **현재 주가 수준 평가:** 현재 주가가 52주 변동폭 및 주요 이동평균선들과 비교했을 때 어떤 수준에 있는지 상세히 설명해 주세요. 예를 들어, "현재 주가는 52주 최고가에 근접해 있으며, 모든 단기 및 장기 이동평균선 위에 위치하여 강세 신호로 해석될 수 있습니다." 와 같이 구체적으로 작성합니다.
    2.  **소속 업종 및 산업 내 위치:** 해당 기업이 속한 업종과 산업을 언급하고, 가능하다면 해당 분야에서의 기업의 간략한 시장 지위나 특징을 언급해주세요. (일반적인 정보 기반 또는 제공된 데이터 내에서 추론)
    3.  **이동평균선 분석:** 단기(5일, 20일) 이동평균선과 장기(60일, 120일) 이동평균선의 배열 상태(정배열, 역배열, 수렴, 확산 등)와 현재 주가와의 관계를 통해 기술적 추세를 분석해 주세요.
    4.  **종합 투자 의견:** 위 분석 내용을 종합하여, 현 시점에서 해당 종목에 대한 투자 매력도를 평가하고, 간략한 투자 전략(예: 보수적 접근, 분할 매수 고려 등)을 약 300자 내외로 제시해 주세요. RSI 수치도 의견에 포함시켜 주세요.

    출력 형식 예시 (실제 분석 내용은 데이터에 따라 달라져야 함):
    {stock_data['name']} ({stock_data['symbol']}) AI 주식 분석:\n
    - **주가 현황:** {stock_data['name']}의 현재 주가는 {price_format}으로, 전일 대비 {stock_data['change_pct']:+.1f}% 변동하였습니다. 이는 52주 변동폭 ({low_52w_format} ~ {high_52w_format}) 내에 있으며 [상단/중간/하단]에 위치합니다.
    - **주가 수준 평가:** [AI가 작성할 구체적인 평가 문장]
    - **업종 내 위치:** [AI가 작성할 경쟁력 및 시장 지위 관련 문장]
    - **이동평균선 분석:** [AI가 작성할 이평선 기반 기술적 분석 문장]
    - **종합 의견:** [AI가 작성할 투자 의견 및 전략]
    """

    try:
        response = openai.ChatCompletion.create(
            engine=AZURE_OPENAI_ENGINE, # Azure 배포 이름 사용
            messages=[
                {"role": "system", "content": "당신은 금융 데이터 분석 전문가입니다. 제공된 수치를 정확히 사용하여 한국어로 주식 분석 보고서를 작성합니다."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5, # 약간 낮춰서 더 사실 기반 응답 유도
            max_tokens=800 # 충분한 길이
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        st.error(f"Azure OpenAI API 호출 중 오류 발생: {e}")
        return f"AI 분석 중 오류가 발생했습니다: {str(e)}"

def plot_stock_chart(stock_data, stock_name):
    # history data's 'Close' is in original currency (USD for US stocks, KRW for KR stocks)
    # MAs in stock_data dict are converted to KRW. For plotting, we want MAs in original currency for consistency with 'Close'
    history = stock_data['history'].copy() # Use a copy to avoid modifying original
    close_prices = history['Close'] # Original currency prices

    # Recalculate MAs on original currency data for the plot
    history['MA5'] = close_prices.rolling(5).mean()
    history['MA20'] = close_prices.rolling(20).mean()
    history['MA60'] = close_prices.rolling(60).mean()
    history['MA120'] = close_prices.rolling(120).mean()

    fig, ax = plt.subplots(figsize=(10, 6)) # Adjust figure size
    ax.plot(history.index, close_prices, label="종가", color="blue", linewidth=1.5)
    ax.plot(history.index, history['MA5'], label="5일", color="red", linestyle='--')
    ax.plot(history.index, history['MA20'], label="20일", color="green", linestyle='--')
    ax.plot(history.index, history['MA60'], label="60일", color="orange", linestyle=':')
    ax.plot(history.index, history['MA120'], label="120일", color="purple", linestyle=':')

    title_font_prop = font_prop if font_available else fm.FontProperties(size=16) # Ensure title font is applied
    axis_font_prop = font_prop if font_available else fm.FontProperties(size=10)
    legend_font_prop = font_prop if font_available else fm.FontProperties(size=9)

    ax.set_title(f"{stock_name} ({stock_data['symbol']}) 주가 차트 ({stock_data['original_currency']})", fontproperties=title_font_prop)
    ax.set_xlabel("날짜", fontproperties=axis_font_prop)
    ax.set_ylabel(f"가격 ({stock_data['original_currency']})", fontproperties=axis_font_prop)
    ax.legend(prop=legend_font_prop)
    ax.grid(True, linestyle='--', alpha=0.7) # Add grid
    plt.xticks(rotation=30, ha='right', fontproperties=axis_font_prop) # Rotate x-axis labels
    plt.yticks(fontproperties=axis_font_prop)
    plt.tight_layout() # Adjust layout to prevent overlap
    return fig

# Streamlit 앱 시작
st.set_page_config(layout="wide") # Use wide layout
st.title("📈 ChatJOY AI 주식 분석")

# 세션 상태 초기화
if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "분석할 종목명을 입력해 주세요 (예: 삼성전자, 005930, AAPL, TSLA)."}
    ]

# 채팅 메시지 표시
for i, msg in enumerate(st.session_state.messages):
    is_user = msg['role'] == 'user'
    with st.chat_message(msg["role"]):
        if msg.get('chart_data'): # This is how we'll now store chart info
            st.write(f"**{msg['stock_name']} 주가 차트**")
            fig = plot_stock_chart(msg['chart_data'], msg['stock_name'])
            st.pyplot(fig)
            plt.close(fig)
        else:
            st.markdown(msg['content'])


# 종목명 입력 및 엔터 키 처리
def handle_input():
    user_input = st.session_state.stock_input # Get input from the text_input
    if user_input: # Process if there is input
        st.session_state.messages.append({"role": "user", "content": user_input})

        with st.chat_message("assistant"):
            with st.spinner("종목 정보 조회 중..."):
                ticker = get_ticker_from_name(user_input)

            if not ticker:
                st.session_state.messages.append({"role": "assistant", "content": f"❌ '{user_input}'에 해당하는 종목을 찾을 수 없습니다. 티커 또는 정확한 종목명을 입력해주세요."})
                st.rerun() # Rerun to display the new message
                return

            with st.spinner(f"{ticker} 데이터 분석 중... 잠시만 기다려 주세요. (최대 1분 소요)"):
                stock_data = get_stock_info(ticker)

            if not stock_data:
                st.session_state.messages.append({"role": "assistant", "content": f"❌ '{user_input}' ({ticker})의 상세 정보를 가져오는데 실패했습니다."})
                st.rerun()
                return

            # 기본 정보 생성
            currency_sym = stock_data['currency_symbol']
            price_str = f"{currency_sym}{int(stock_data['price']):,d}"
            change_str = f"({stock_data['change_pct']:+.1f}%)"
            market_cap_str = f"{stock_data['market_cap']:,.1f} {stock_data['market_cap_unit']}"
            high_52w_str = f"{currency_sym}{int(stock_data['high_52w']):,d}"
            low_52w_str = f"{currency_sym}{int(stock_data['low_52w']):,d}"
            rsi_val = stock_data['rsi']
            rsi_str = f"{rsi_val:.1f}" if pd.notna(rsi_val) else "N/A"

            exchange_rate_info_str = ""
            if stock_data['applied_exchange_rate']:
                exchange_rate_info_str = f"환율 적용: 1 USD = {exchange_rate:,.0f} KRW (정보: {stock_data['original_currency']} 기준)\n"

            basic_info = (
                f"**📊 {stock_data['name']} ({ticker}) 기본 정보**\n"
                f"현재가: {price_str} {change_str}\n"
                f"시가총액: {market_cap_str}\n"
                f"52주 고가: {high_52w_str}\n"
                f"52주 저가: {low_52w_str}\n"
                f"RSI (14일): {rsi_str}\n"
                f"{exchange_rate_info_str}"
            )
            st.session_state.messages.append({"role": "assistant", "content": basic_info})

            # AI 분석
            # Only run AI analysis if keys are likely real
            if openai.api_key != "DUMMY_KEY" and AZURE_OPENAI_ENGINE:
                with st.spinner("AI가 주식 리포트를 작성 중입니다... 🤖"):
                    ai_analysis_report = get_ai_analysis(stock_data)
                st.session_state.messages.append({"role": "assistant", "content": f"**🤖 AI 주식 분석 리포트**\n{ai_analysis_report}"})
            else:
                st.session_state.messages.append({"role": "assistant", "content": "**🤖 AI 주식 분석 리포트**\nAI 분석을 위한 API 설정이 필요합니다."})


            # 차트 데이터는 별도의 메시지 타입이나 속성으로 전달하여 위에서 처리
            st.session_state.messages.append({
                "role": "assistant", # Chart is part of assistant's response
                "content": "", # No primary text content for this message if chart is main part
                "chart_data": stock_data, # Store all necessary data for plotting
                "stock_name": stock_data['name'] # Pass name for chart title
            })

        # 입력창 초기화 및 rerun
        st.session_state.stock_input = "" # Clear the input box state variable
        st.rerun()

# 사용자 입력창 (채팅 입력 방식으로 변경)
# The on_change callback fires BEFORE the script reruns due to chat_input.
# So, handle_input should manage its own display logic or trigger a rerun.
if prompt := st.chat_input("종목명을 입력하세요 (예: 삼성전자, AAPL)"):
    st.session_state.stock_input = prompt # Store the input in session_state
    handle_input() # Call the handler immediately
