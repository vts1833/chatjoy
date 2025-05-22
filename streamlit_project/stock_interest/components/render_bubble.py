#말풍선 스타일 유틸 함수
import streamlit as st

def render_bubble(text, role="assistant"):
    align = "flex-start" if role == "assistant" else "flex-end"
    bg_color = "#f1f3f5" if role == "assistant" else "#d2f4d2"
    st.markdown(
        f"""
        <div style='display: flex; justify-content: {align}; margin-bottom: 10px;'>
            <div style='background-color: {bg_color}; padding: 10px 15px; border-radius: 15px; max-width: 60%;'>
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
