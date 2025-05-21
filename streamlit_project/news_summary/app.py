import streamlit as st
from naver_news import search_naver_news

st.set_page_config(page_title="네이버 뉴스 요약")

st.title("📰 네이버 뉴스 요약")
st.markdown("네이버에서 실시간으로 제공되는 뉴스입니다.")

query = st.text_input("검색어를 입력하세요", "증권")

if query:
    news_items = search_naver_news(query)
    if news_items:
        for pubDate, title, link in news_items:
            with st.chat_message("assistant"):
                st.markdown(f"🕒 **{pubDate}**\n\n🔗 [{title}]({link})")
    else:
        st.error("뉴스를 불러오지 못했습니다.")
