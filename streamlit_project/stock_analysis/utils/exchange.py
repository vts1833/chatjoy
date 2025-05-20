import requests
import streamlit as st

def get_exchange_rate():
    try:
        api_key = "a7ce46583c0498045e014086"
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/USD"
        res = requests.get(url, timeout=5).json()
        if res['result'] == 'success':
            return res['conversion_rates']['KRW']
        else:
            st.warning("API 응답 오류. 기본 환율 1340 적용.")
            return 1340
    except:
        st.warning("환율 API 요청 실패. 기본 환율 1340 적용.")
        return 1340
