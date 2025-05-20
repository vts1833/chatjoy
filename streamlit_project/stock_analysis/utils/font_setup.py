import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import streamlit as st

def setup_font():
    try:
        font_name = "NanumGothic"
        font_list = fm.findSystemFonts()
        font_path = next((f for f in font_list if font_name.lower() in f.lower()), None)

        if font_path:
            fm.fontManager.addfont(font_path)
            font_prop = fm.FontProperties(fname=font_path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
            return font_prop, True
        else:
            plt.rcParams['font.family'] = 'sans-serif'
            return None, False
    except Exception as e:
        st.error(f"폰트 설정 오류: {str(e)}")
        return None, False
