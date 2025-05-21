import streamlit as st
from questions import questions
from logic import get_profile
from ui import render_chat_bubble

st.set_page_config(page_title="투자 성향 테스트", layout="centered")

if 'question_number' not in st.session_state:
    st.session_state.question_number = 1
if 'answers' not in st.session_state:
    st.session_state.answers = []
if 'chat_log' not in st.session_state:
    st.session_state.chat_log = []
if 'result_shown' not in st.session_state:
    st.session_state.result_shown = False

# 채팅 로그 표시
for msg in st.session_state.chat_log:
    render_chat_bubble(msg['role'], msg['text'])

# 테스트 진행
q_num = st.session_state.question_number

if q_num <= 5:
    question, choices = questions[q_num]
    q_text = f"Q{q_num}. {question}\n\n" + "\n".join(choices)
    render_chat_bubble("bot", q_text)

    user_input = st.text_input("숫자 1~3 입력", key=f"input_{q_num}")

    if user_input:
        user_input = user_input.strip()
        if user_input in ['1', '2', '3']:
            st.session_state.answers.append(int(user_input))
            st.session_state.chat_log.append({"role": "user", "text": user_input})
            st.session_state.question_number += 1
            st.rerun()
        else:
            st.warning("❗ 1~3 숫자만 입력 가능합니다.")

# 결과
elif not st.session_state.result_shown:
    total = sum(st.session_state.answers)
    profile = get_profile(total)
    result_text = f"✅ 테스트 완료! 당신은 '{profile}'입니다."
    st.session_state.chat_log.append({"role": "bot", "text": result_text})
    st.session_state.result_shown = True
    st.rerun()

# 리셋 버튼
if st.button("🔄 다시 테스트하기"):
    for key in ['question_number', 'answers', 'chat_log', 'result_shown']:
        st.session_state.pop(key, None)
    st.rerun()
