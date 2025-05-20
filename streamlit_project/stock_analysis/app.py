import streamlit as st
from utils.font_setup import setup_font
from utils.exchange import get_exchange_rate
from utils.ticker import get_ticker_from_name
from utils.stock_info import get_stock_info
from utils.ai_analysis import get_ai_analysis
from utils.chart import plot_stock_chart
import json

# 초기 설정
font_prop, font_available = setup_font()
exchange_rate = get_exchange_rate()

# 한국 종목 매핑 로딩
try:
    with open('krx_ticker_map.json', 'r', encoding='utf-8') as f:
        kr_tickers = json.load(f)
except FileNotFoundError:
    st.warning("krx_ticker_map.json 파일이 없습니다.")
    kr_tickers = {}

st.title("📈 ChatJOY AI 주식 분석")

if 'messages' not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "분석할 종목명을 말씀해 주세요 (예: 삼성전자, AAPL)!"}
    ]

# 채팅창 렌더링
for msg in st.session_state.messages:
    if msg.get('chart_data'):
        st.write(f"**{msg['stock_name']} 차트**")
        fig = plot_stock_chart(msg['chart_data'], msg['stock_name'], font_prop)
        st.pyplot(fig)
    else:
        st.markdown(f"**{'사용자' if msg['role']=='user' else 'AI'}:** {msg['content']}")

# 입력 처리
def handle_input():
    stock_name = st.session_state.stock_input
    if not stock_name:
        return
    
    st.session_state.messages.append({"role": "user", "content": stock_name})
    ticker = get_ticker_from_name(stock_name, kr_tickers)
    if not ticker:
        st.session_state.messages.append({"role": "assistant", "content": "❌ 종목명을 찾을 수 없습니다."})
    else:
        with st.spinner("분석 중..."):
            data = get_stock_info(ticker, exchange_rate)
            basic_info = f"""**📊 기본 정보**
{data['name']} ({ticker})
현재가: ₩{int(data['price']):,d} ({data['change_pct']:+.1f}%)
시가총액: {data['market_cap']:,.1f} {data['market_cap_unit']}
52주 범위: ₩{int(data['low_52w']):,d} ~ ₩{int(data['high_52w']):,d}
RSI: {data['rsi']:.1f}
"""
            analysis = get_ai_analysis(data)
            response = f"{basic_info}\n**🤖 AI 분석**\n{analysis}"
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.messages.append({
                "role": "assistant", "content": f"**{stock_name} 차트**",
                "chart_data": data, "stock_name": stock_name
            })
    
    st.session_state.stock_input = ""

st.text_input("종목명을 입력하세요 (예: 삼성전자, AAPL)", key="stock_input", on_change=handle_input)
