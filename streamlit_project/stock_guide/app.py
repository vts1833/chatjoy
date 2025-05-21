import streamlit as st

# 기본 용어 설명 사전
term_dict = {
    "PER": "PER(주가수익비율)은 주가를 주당순이익(EPS)으로 나눈 값입니다. 숫자가 작을수록 저평가된 주식일 수 있습니다.",
    "PBR": "PBR(주가순자산비율)은 주가를 주당순자산(BPS)으로 나눈 값입니다. 1보다 낮으면 자산 대비 주가가 낮은 상태입니다.",
    "시가총액": "시가총액은 기업의 전체 시장 가치입니다. 주가 × 총 주식 수로 계산합니다.",
    "배당": "기업이 이익의 일부를 주주에게 돌려주는 것을 말합니다. 배당 수익률은 투자자 입장에서 중요한 수익 요소입니다.",
    "우선주": "의결권은 없지만 보통주보다 배당을 우선적으로 받을 수 있는 주식입니다.",
    "분할": "주식을 쪼개는 것(예: 1주 → 5주). 유동성을 높이고 개인 투자자 접근성을 높입니다.",
    "ETF": "여러 종목을 묶어 하나처럼 거래하는 상장지수펀드입니다. 분산투자에 유리합니다.",
}

# 페이지 구성
st.set_page_config(page_title="📚 주식 용어 설명", layout="centered")
st.title("📚 주식 초보자용 용어 사전")
st.markdown("초보 투자자들이 자주 접하는 **주식 용어**들을 쉽게 설명합니다.")

# 검색창
search = st.text_input("궁금한 용어를 입력해보세요 (예: PER, 배당, ETF 등)")

# 용어 출력
if search:
    key = search.strip().upper().replace(" ", "")
    matched = None
    for term in term_dict:
        if key in term.upper().replace(" ", ""):
            matched = term
            break

    if matched:
        st.success(f"✅ {matched}")
        st.markdown(f"{term_dict[matched]}")
    else:
        st.warning("❗ 용어를 찾을 수 없습니다. 다른 키워드를 시도해보세요.")

# 전체 용어 목록 보기
with st.expander("📘 전체 용어 목록 보기"):
    for term, desc in term_dict.items():
        st.markdown(f"**🔹 {term}**\n- {desc}\n")
