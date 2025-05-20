import openai

openai.api_key = "YOUR_KEY"
openai.api_base = "YOUR_AZURE_BASE_URL"
openai.api_type = "azure"
openai.api_version = "2023-03-15-preview"

def get_ai_analysis(data):
    prompt = f"""
    {data['name']} 분석:
    - 현재가: ₩{int(data['price']):,d} ({data['change_pct']:+.1f}%)
    - 52주 범위: ₩{int(data['low_52w']):,d} ~ ₩{int(data['high_52w']):,d}
    - RSI: {data['rsi']:.1f}
    - MA: 5일({int(data['ma_5'])}), 20일({int(data['ma_20'])}), 60일({int(data['ma_60'])}), 120일({int(data['ma_120'])})
    """
    try:
        res = openai.ChatCompletion.create(
            engine="gpt-35-turbo",
            messages=[
                {"role": "system", "content": "주식 분석 전문가"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        return res['choices'][0]['message']['content']
    except Exception as e:
        return f"AI 분석 실패: {str(e)}"
