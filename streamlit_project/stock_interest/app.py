import streamlit as st
import json
import yfinance as yf
from components.render_bubble import render_bubble

# ✅ 종목 데이터 로딩
with open("data/krx_ticker_map.json", encoding="utf-8") as f:
    stock_dict = json.load(f)
stock_names = list(stock_dict.keys())

# ✅ 세션 초기화
if "interest_list" not in st.session_state:
    st.session_state.interest_list = []
if "chat_log" not in st.session_state:
    st.session_state.chat_log = []
if "selected_stock" not in st.session_state:
    st.session_state.selected_stock = None

# ✅ 사용자 입력 처리 전 미리 렌더링
user_input = st.chat_input("예: 삼성전자 추가 / 카카오 삭제")
if user_input:
    st.session_state.chat_log.append({"role": "user", "text": user_input})
    utterance = user_input.strip()
    reply_log = []
    found_stocks = [name for name in stock_names if name in utterance]
    current = st.session_state.interest_list

    if any(word in utterance for word in ["삭제", "제거", "빼", "지워"]):
        for stock in found_stocks:
            if stock in current:
                current.remove(stock)
                reply_log.append(f"✅ {stock} 삭제되었습니다.")
            else:
                reply_log.append(f"⚠️ {stock}은(는) 등록되어 있지 않아요.")
    else:
        for stock in found_stocks:
            if stock not in current:
                if len(current) < 10:
                    current.append(stock)
                    reply_log.append(f"✅ {stock} 종목이 추가되었습니다.")
                else:
                    reply_log.append("❗ 최대 10개까지 등록 가능합니다.")
                    break
            else:
                reply_log.append(f"⚠️ {stock}은(는) 이미 등록되어 있어요.")

    for line in reply_log:
        st.session_state.chat_log.append({"role": "assistant", "text": line})
    if current:
        msg = f"📋 현재 관심 종목은 {len(current)}개입니다."
        st.session_state.chat_log.append({"role": "assistant", "text": msg})

    st.rerun()

# ✅ 채팅 로그 출력
for msg in st.session_state.chat_log:
    render_bubble(msg["text"], role=msg["role"])

# ✅ 최초 진입 시 현재 관심 종목 자동 응답
if not st.session_state.chat_log and st.session_state.interest_list:
    current = st.session_state.interest_list
    intro_msg = f"📋 현재 관심 종목은 {len(current)}개입니다."
    st.session_state.chat_log.append({"role": "assistant", "text": intro_msg})
    render_bubble(intro_msg, role="assistant")

# ✅ 관심 종목 카드형 버튼 출력
if st.session_state.interest_list:
    st.markdown("### 📈 관심 종목 주가 보기")
    cols = st.columns(len(st.session_state.interest_list))
    for i, stock in enumerate(st.session_state.interest_list):
        with cols[i]:
            if st.button(stock):
                st.session_state.selected_stock = stock
                st.rerun()

# ✅ 종목 선택 시 주가 정보 표시
selected = st.session_state.get("selected_stock")
if selected and selected in stock_dict:
    try:
        ticker = stock_dict[selected]
        stock = yf.Ticker(ticker)
        info = stock.info

        price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
        change = info.get("regularMarketChangePercent", 0.0)
        per = info.get("trailingPE", "-")
        pbr = info.get("priceToBook", "-")
        market_cap = info.get("marketCap", 0)

        summary = f"""
✅ **{selected} 주가 요약**
- 현재가: {int(price):,}원
- 변동률: {change:.2f}%
- 시가총액: {market_cap / 1e12:.2f}조 원
- PER: {per}, PBR: {pbr}
        """
    except Exception as e:
        summary = f"⚠️ {selected} 데이터를 불러오는 데 실패했습니다.\n{str(e)}"

    st.session_state.chat_log.append({"role": "assistant", "text": summary})
    render_bubble(summary, role="assistant")
    st.session_state.selected_stock = None
