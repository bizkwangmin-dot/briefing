#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트 스크립트
GitHub Actions에서 실행 (오전 7:30 / 오후 5:30 KST)

동작:
  1. 주요 언론사 RSS 뉴스 수집 (제목 + 링크 + 시간)
  2. 섹션별로 카드 자동 생성
  3. index.html 업데이트
  4. GitHub Actions가 자동 커밋·푸시
"""

import os, re, sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import pytz
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai  # Gemini 추가

# Gemini API 설정
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")
print(f"[{now_display}] 브리핑 자동 업데이트 시작 (AI 요약 포함)")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
}

# --- (RSS_SOURCES, SECTION_COLORS, CARD_COLORS는 기존 코드와 동일) ---
RSS_SOURCES = {
    "경제 · 금융": [
        ("조선일보", "c", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/"),
        ("매일경제", "e", "https://www.mk.co.kr/rss/30000001/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/economy.xml"),
    ],
    "기 업": [
        ("조선일보", "c", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("매일경제", "e", "https://www.mk.co.kr/rss/30200030/"),
    ],
    "정책 · 사회": [
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/"),
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/politics.xml"),
    ],
    "국 제": [
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/international.xml"),
        ("조선일보", "c", "https://www.chosun.com/arc/outboundfeeds/rss/category/international/"),
    ],
}

SECTION_COLORS = {"경제 · 금융": "var(--red)", "기 업": "var(--navy)", "정책 · 사회": "var(--gold)", "국 제": "var(--dark)"}
CARD_COLORS = {"경제 · 금융": "red", "기 업": "navy", "정책 · 사회": "gold", "국 제": "dk"}

def get_ai_summary(title):
    """제목을 바탕으로 뉴스 내용을 예측하여 요약 (무료 티어 속도 고려)"""
    if not model:
        return "AI 요약을 불러올 수 없습니다."
    
    try:
        prompt = f"뉴스 제목: '{title}'\n이 뉴스의 핵심 내용을 5줄 이내로 요약해줘. 각 줄 끝에는 적절한 이모지를 붙여줘. 한국어로 작성해."
        response = model.generate_content(prompt)
        return response.text.replace("\n", "<br>")
    except Exception as e:
        print(f" 요약 실패: {e}")
        return "요약을 생성하는 중 오류가 발생했습니다."

def fetch_rss(source, src_class, url, max_items=4):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title").get_text(strip=True)
            link  = item.find("link").get_text(strip=True)
            pub   = item.find("pubDate") or item.find("dc:date")
            
            # 요약 생성
            print(f"  🤖 요약 중: {title[:20]}...")
            summary = get_ai_summary(title)

            pub_iso = now_iso
            if pub:
                try:
                    pub_dt = parsedate_to_datetime(pub.get_text(strip=True))
                    pub_kst = pub_dt.astimezone(KST)
                    pub_iso = pub_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except: pass

            items.append({
                "source": source, "src_class": src_class, "title": title,
                "url": link, "pubtime": pub_iso, "summary": summary
            })
        return items
    except Exception as e:
        print(f"  ⚠️ {source} RSS 실패: {e}")
        return []

# --- (뉴스 수집 로직) ---
print("📡 뉴스 RSS 수집 및 AI 요약 중...")
section_news = {}
for section, sources in RSS_SOURCES.items():
    seen_titles = set()
    news_list = []
    for source, src_class, url in sources:
        items = fetch_rss(source, src_class, url, max_items=2) # 속도를 위해 소스당 2개로 조정
        for item in items:
            key = item["title"][:15]
            if key not in seen_titles:
                seen_titles.add(key)
                news_list.append(item)
        if len(news_list) >= 3: # 섹션당 3개면 충분
            break
    section_news[section] = news_list[:3]

# ─────────────────────────────────────────
# HTML 카드 생성 (요약 칸 추가)
# ─────────────────────────────────────────
def make_card(item, card_color):
    title  = item["title"].replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    summary = item["summary"]
    url    = item["url"]
    source = item["source"]
    src_cls= item["src_class"]
    pub    = item["pubtime"]

    return f'''
    <div class="card {card_color}">
      <div class="ct">
        <span class="src {src_cls}">{source}</span>
        <span class="ctime" data-pubtime="{pub}">🕒 --</span>
      </div>
      <div class="ch"><a href="{url}" class="ch-link" target="_blank">{title}</a></div>
      <div class="card-summary" style="font-size:13px; color:#555; background:#f9f9f9; padding:10px; border-radius:8px; margin:10px 0;">
        {summary}
      </div>
      <div class="card-history-row">
        <a href="{url}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;">↗ 원문 보기</a>
      </div>
    </div>'''

# --- (이후 index.html 업데이트 로직은 기존과 동일) ---
def make_section_html(section_name, items, color, card_color):
    html = f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{section_name}</span><div class="sec-line"></div></div>\n'
    for item in items:
        html += make_card(item, card_color)
    return html

INDEX_PATH = "index.html"
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

meta_new = f'<meta name="last-updated" content="{now_iso}">'
html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html) if '<meta name="last-updated"' in html else html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n{meta_new}')

new_news_html = "\n"
for section, items in section_news.items():
    if items:
        new_news_html += make_section_html(section, items, SECTION_COLORS[section], CARD_COLORS[section])

auto_block = f"{new_news_html}\n    "
html = re.sub(r'.*?', auto_block, html, flags=re.DOTALL)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"💾 업데이트 완료 🎉")
