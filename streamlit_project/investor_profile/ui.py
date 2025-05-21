import streamlit as st

def render_chat_bubble(role, text):
    if role == "user":
        st.markdown(f"""
        <div style="text-align:right;">
            <span style="background-color:#dcf8c6;padding:10px;border-radius:10px;display:inline-block;">{text}</span>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="text-align:left;">
            <span style="background-color:#f1f0f0;padding:10px;border-radius:10px;display:inline-block;">{text}</span>
        </div>
        """, unsafe_allow_html=True)
