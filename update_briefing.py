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

KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")
print(f"[{now_display}] 브리핑 자동 업데이트 시작")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0 Safari/537.36'
}

# ─────────────────────────────────────────
# RSS 소스 정의 (섹션별)
# ─────────────────────────────────────────
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

# 섹션 색상
SECTION_COLORS = {
    "경제 · 금융": "var(--red)",
    "기 업":       "var(--navy)",
    "정책 · 사회": "var(--gold)",
    "국 제":       "var(--dark)",
}
CARD_COLORS = {
    "경제 · 금융": "red",
    "기 업":       "navy",
    "정책 · 사회": "gold",
    "국 제":       "dk",
}

def fetch_rss(source, src_class, url, max_items=4):
    """RSS 피드에서 최신 기사 가져오기"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate") or item.find("dc:date")
            if not title or not link: continue

            title_text = title.get_text(strip=True)
            link_text  = link.get_text(strip=True).strip()
            if not link_text or link_text == url:
                link_text = link.next_sibling
                if link_text:
                    link_text = str(link_text).strip()

            # 발행 시간 파싱
            pub_iso = now_iso
            if pub:
                try:
                    pub_dt = parsedate_to_datetime(pub.get_text(strip=True))
                    pub_kst = pub_dt.astimezone(KST)
                    pub_iso = pub_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except:
                    pass

            items.append({
                "source":    source,
                "src_class": src_class,
                "title":     title_text,
                "url":       link_text,
                "pubtime":   pub_iso,
            })
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

# ─────────────────────────────────────────
# 뉴스 수집
# ─────────────────────────────────────────
print("📡 뉴스 RSS 수집 중...")
section_news = {}
for section, sources in RSS_SOURCES.items():
    seen_titles = set()
    news_list = []
    for source, src_class, url in sources:
        items = fetch_rss(source, src_class, url, max_items=3)
        for item in items:
            # 중복 제거 (제목 앞 10글자 기준)
            key = item["title"][:15]
            if key not in seen_titles:
                seen_titles.add(key)
                news_list.append(item)
        if len(news_list) >= 5:
            break
    section_news[section] = news_list[:5]
    total = sum(len(v) for v in section_news.values())
    print(f"  {section}: {len(news_list)}건")

print(f"  📰 총 {total}건 수집")

# ─────────────────────────────────────────
# HTML 카드 생성
# ─────────────────────────────────────────
def make_card(item, card_color):
    """뉴스 아이템으로 카드 HTML 생성"""
    title  = item["title"].replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
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
      <div class="card-history-row">
        <a href="{url}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;">↗ 원문 보기</a>
      </div>
    </div>'''

def make_section_html(section_name, items, color, card_color):
    """섹션 전체 HTML 생성"""
    html = f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{section_name}</span><div class="sec-line"></div></div>\n'
    for item in items:
        html += make_card(item, card_color)
    return html

# ─────────────────────────────────────────
# index.html 업데이트
# ─────────────────────────────────────────
INDEX_PATH = "index.html"
if not os.path.exists(INDEX_PATH):
    print(f"❌ {INDEX_PATH} 없음")
    sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# 1) last-updated 메타 갱신
meta_new = f'<meta name="last-updated" content="{now_iso}">'
if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n{meta_new}')
print("✅ last-updated 메타 갱신")

# 2) 뉴스 섹션 자동 교체
# <!-- AUTO_NEWS_START --> ~ <!-- AUTO_NEWS_END --> 사이를 교체
new_news_html = "\n"
for section, items in section_news.items():
    if items:
        color      = SECTION_COLORS[section]
        card_color = CARD_COLORS[section]
        new_news_html += make_section_html(section, items, color, card_color)

auto_block = f"<!-- AUTO_NEWS_START -->{new_news_html}\n    <!-- AUTO_NEWS_END -->"

if "<!-- AUTO_NEWS_START -->" in html and "<!-- AUTO_NEWS_END -->" in html:
    html = re.sub(
        r'<!-- AUTO_NEWS_START -->.*?<!-- AUTO_NEWS_END -->',
        auto_block,
        html,
        flags=re.DOTALL
    )
    print("✅ 뉴스 섹션 자동 교체")
else:
    print("⚠️  AUTO_NEWS 마커 없음 — index.html에 마커 추가 필요")
    # 마커 없으면 주석으로 추가 내용만 삽입
    html += f"\n{auto_block}"

# 3) 날짜 표시 업데이트
date_str = now_kst.strftime("%Y.%m.%d (%a)").replace(
    "Mon","월").replace("Tue","화").replace("Wed","수").replace(
    "Thu","목").replace("Fri","금").replace("Sat","토").replace("Sun","일")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"💾 index.html 저장 완료")
print(f"[{now_display}] 업데이트 완료 🎉")
