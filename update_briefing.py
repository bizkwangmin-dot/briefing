import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
import os

# ===== 기본 설정 =====
KST = pytz.timezone('Asia/Seoul')

NEWS_SOURCES = [
    # 국내
    ("조선일보", "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("중앙일보", "https://rss.joins.com/joins_money_list.xml"),
    ("한국경제", "https://www.hankyung.com/feed/economy"),

    # 해외
    ("WSJ", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("Reuters", "https://www.reutersagency.com/feed/?best-topics=business-finance"),
]

# ===== 뉴스 수집 =====
def fetch_news():
    news_list = []

    for source_name, url in NEWS_SOURCES:
        try:
            res = requests.get(url, timeout=10)
            res.encoding = 'utf-8'

            soup = BeautifulSoup(res.text, "xml")

            for item in soup.find_all("item")[:5]:
                news_list.append({
                    "title": item.title.text.strip(),
                    "link": item.link.text.strip(),
                    "source": source_name
                })

        except Exception as e:
            print(f"{source_name} 오류:", e)

    return deduplicate(news_list)


def deduplicate(news_list):
    seen = set()
    result = []

    for n in news_list:
        key = n['title'][:50]
        if key not in seen:
            seen.add(key)
            result.append(n)

    return result


# ===== 카테고리 분류 =====
CATEGORY_RULES = {
    "AI": ["AI", "인공지능", "반도체"],
    "금융": ["금리", "은행", "환율"],
    "부동산": ["부동산", "아파트"],
    "글로벌": ["미국", "중국", "유럽"]
}


def classify(title):
    for cat, keywords in CATEGORY_RULES.items():
        for k in keywords:
            if k in title:
                return cat
    return "기타"


# ===== Claude 호출 =====
def ai_call(prompt):
    try:
        import anthropic

        client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

        res = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return res.content[0].text

    except Exception as e:
        return "생성 실패"


# ===== 기능 =====

def summarize(news):
    prompt = f"""
    아래 뉴스를 3줄로 요약해라.

    {news}
    """
    return ai_call(prompt)


def generate_column(news_list):
    prompt = f"""
    아래 뉴스들을 기반으로
    경제 칼럼 작성

    300자 이내
    핵심 인사이트 포함

    {news_list}
    """
    return ai_call(prompt)


def generate_impact(news):
    prompt = f"""
    아래 뉴스의 파급효과를 단계적으로 작성

    A → B → C 형식

    {news}
    """
    return ai_call(prompt)


def generate_feed(news_list):
    if not news_list:
        return "뉴스 없음"

    prompt = f"""
    오늘 뉴스 핵심 5줄 요약

    {news_list[:5]}
    """
    return ai_call(prompt)


# ===== 해외 시각 언론사 리스트 추출 =====
def extract_global_sources(news_list):
    global_sources = set()

    for n in news_list:
        if n['source'] not in ["조선일보", "중앙일보", "한국경제"]:
            global_sources.add(n['source'])

    return list(global_sources)


# ===== HTML 생성 =====
def generate_html(news_list):

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    global_sources = extract_global_sources(news_list)

    html = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>세줄뉴스</title>
    </head>
    <body>
        <h1>세줄뉴스</h1>
        <p>{now}</p>

        <h2>뉴스</h2>
    """

    for n in news_list:
        summary = summarize(n['title'])
        impact = generate_impact(n['title'])

        html += f"""
        <div>
            <h3>{n['title']}</h3>
            <p>{summary}</p>
            <p><b>파급:</b> {impact}</p>
            <a href="{n['link']}">원문</a>
        </div>
        """

    # ===== 해외 시각 (원래 구조 유지) =====
    html += "<h2>해외 시각</h2>"

    for src in global_sources:
        html += f"<p>{src}</p>"

    # ===== 뉴스 피드 =====
    feed = generate_feed(news_list)
    html += f"<h2>오늘의 뉴스</h2><p>{feed}</p>"

    # ===== 칼럼 =====
    column = generate_column(news_list)
    html += f"<h2>칼럼</h2><p>{column}</p>"

    html += "</body></html>"

    return html


# ===== 실행 =====
def main():
    news = fetch_news()
    html = generate_html(news)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
