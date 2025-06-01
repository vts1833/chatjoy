import requests
from datetime import datetime
from xml.etree import ElementTree

# 클라이언트 키 (★본인 키로 교체 필요)
client_id = "tkTiayD7fq2F1vrMY4kj"
client_secret = "z6xSBpF14j"

def search_naver_news(query, display=5):
    url = "https://openapi.naver.com/v1/search/news.xml"
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    params = {
        "query": query,
        "display": display,
        "sort": "date"
    }

    res = requests.get(url, headers=headers, params=params)
    root = ElementTree.fromstring(res.content)
    news_list = []

    for item in root.findall('./channel/item'):
        title = item.findtext('title').replace("<b>", "").replace("</b>", "")
        link = item.findtext('link')
        pubDate = item.findtext('pubDate')
        pubDate = datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %z").strftime("%Y-%m-%d %H:%M")
        news_list.append((pubDate, title, link))

    return news_list
