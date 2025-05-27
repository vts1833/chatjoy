import requests
import streamlit as st

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
