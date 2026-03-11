#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트 스크립트
GitHub Actions에서 실행 (오전 7:30 / 오후 5:30 KST)

동작:
  1. 주요 언론사 RSS 스크래핑
  2. index.html의 <meta name="last-updated"> 갱신
  3. GitHub Actions가 자동 커밋·푸시

패키지: pip install requests beautifulsoup4 pytz lxml
"""

import os, re, sys
from datetime import datetime
import pytz
import requests
from bs4 import BeautifulSoup

KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")

print(f"[{now_display}] 브리핑 자동 업데이트 시작")

# ─────────────────────────────────────────
# RSS 소스 목록 (무료로 크롤링 가능한 RSS)
# ─────────────────────────────────────────
RSS_SOURCES = [
    ("조선일보",   "https://www.chosun.com/arc/outboundfeeds/rss/"),
    ("한겨레",     "https://www.hani.co.kr/rss/"),
    ("매일경제",   "https://www.mk.co.kr/rss/30000001/"),
    ("한국경제",   "https://www.hankyung.com/feed/all-news"),
    ("연합뉴스",   "https://www.yonhapnews.co.kr/rss/economy.xml"),
    ("경향신문",   "https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/120.0 Safari/537.36'
}

def fetch_rss(source, url, max_items=5):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            title = item.find("title")
            link  = item.find("link")
            pub   = item.find("pubDate") or item.find("dc:date")
            if not title: continue
            items.append({
                "source":  source,
                "title":   title.get_text(strip=True),
                "url":     link.get_text(strip=True) if link else "#",
                "pubDate": pub.get_text(strip=True) if pub else now_iso,
            })
        print(f"  ✅ {source}: {len(items)}건")
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

print("📡 뉴스 RSS 수집 중...")
all_news = []
for source, url in RSS_SOURCES:
    all_news.extend(fetch_rss(source, url))
print(f"  📰 총 {len(all_news)}건 수집")

# ─────────────────────────────────────────
# index.html 업데이트
#  → <meta name="last-updated"> 갱신
# ─────────────────────────────────────────
INDEX_PATH = "index.html"

if not os.path.exists(INDEX_PATH):
    print(f"❌ {INDEX_PATH} 없음 — 스크립트를 레포 루트에서 실행하세요")
    sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

meta_new = f'<meta name="last-updated" content="{now_iso}">'

if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
    print("✅ last-updated 메타 갱신")
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n{meta_new}')
    print("✅ last-updated 메타 삽입")

# ─────────────────────────────────────────
# (선택) RSS로 수집한 최신 뉴스 중 헤드라인 주석으로 남기기
# 향후 카드 자동 생성 기능 확장 가능
# ─────────────────────────────────────────
headlines_comment = "\n<!-- RSS_HEADLINES\n"
for n in all_news[:10]:
    headlines_comment += f"  [{n['source']}] {n['title']}\n  {n['url']}\n"
headlines_comment += "-->\n"

# 기존 RSS_HEADLINES 주석 교체 또는 삽입
if '<!-- RSS_HEADLINES' in html:
    html = re.sub(r'<!-- RSS_HEADLINES.*?-->', headlines_comment, html, flags=re.DOTALL)
else:
    html = html.replace('</head>', headlines_comment + '</head>')

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"💾 index.html 저장 완료")
print(f"[{now_display}] 업데이트 완료 🎉")
