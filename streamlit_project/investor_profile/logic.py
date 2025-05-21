def get_profile(total):
    if total <= 7:
        return "안정형 투자자"
    elif total <= 11:
        return "중립형 투자자"
    else:
        return "공격형 투자자"
