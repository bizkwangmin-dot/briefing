#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트 스크립트
GitHub Actions에서 실행 (오전 7:30 / 오후 5:30 KST)
Gemini Flash API로 5줄 요약 자동 생성 (무료)
"""

import os, re, sys, time
from datetime import datetime
from email.utils import parsedate_to_datetime
import pytz
import requests
from bs4 import BeautifulSoup

# ─────────────────────────────────────────
# Gemini API 설정
# ─────────────────────────────────────────
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_KEY)
        gemini_model = genai.GenerativeModel("gemini-2.0-flash")
        print("✅ Gemini API 연결 완료")
    except Exception as e:
        print(f"⚠️  Gemini 초기화 실패: {e}")
else:
    print("⚠️  GEMINI_API_KEY 없음 — 요약 없이 제목만 사용")

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

RSS_SOURCES = {
    "경제 · 금융": [
        ("매일경제", "e", "https://www.mk.co.kr/rss/30000001/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/economy.xml"),
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
    ],
    "기 업": [
        ("매일경제", "e", "https://www.mk.co.kr/rss/30200030/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/economy.xml"),
    ],
    "정책 · 사회": [
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/"),
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/politics.xml"),
    ],
    "국 제": [
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/international.xml"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/international/"),
    ],
}

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

def get_summary(title):
    """Gemini로 뉴스 제목 → 5줄 요약"""
    if not gemini_model:
        return None
    prompt = f"""뉴스 기사 제목: '{title}'

이 뉴스의 핵심 내용을 5줄로 요약해줘.
규칙:
- 각 줄은 숫자나 기호 없이 바로 내용만
- 한 줄에 50자 이내
- 구체적인 수치나 사실 위주로
- 한국어로 작성
- 5줄만 출력 (그 외 설명 없이)"""
    try:
        response = gemini_model.generate_content(prompt)
        lines = [l.strip().lstrip('·-•123456789. ').strip()
                 for l in response.text.strip().split('\n') if l.strip()]
        return [l for l in lines if l][:5]
    except Exception as e:
        print(f"    ⚠️  요약 실패: {e}")
        return None

def fetch_rss(source, src_class, url, max_items=5):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            title_tag = item.find("title")
            link_tag  = item.find("link")
            pub_tag   = item.find("pubDate") or item.find("dc:date")
            if not title_tag: continue
            title_text = title_tag.get_text(strip=True)
            link_text  = link_tag.get_text(strip=True) if link_tag else "#"
            if not link_text:
                link_text = str(link_tag.next_sibling).strip() if link_tag and link_tag.next_sibling else "#"
            pub_iso = now_iso
            if pub_tag:
                try:
                    pub_dt  = parsedate_to_datetime(pub_tag.get_text(strip=True))
                    pub_kst = pub_dt.astimezone(KST)
                    pub_iso = pub_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except: pass
            items.append({
                "source": source, "src_class": src_class,
                "title": title_text, "url": link_text, "pubtime": pub_iso,
            })
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

# ─────────────────────────────────────────
# 뉴스 수집 + Gemini 요약
# ─────────────────────────────────────────
print("📡 뉴스 RSS 수집 + Gemini 요약 시작...")
section_news = {}
total = 0

for section, sources in RSS_SOURCES.items():
    seen_titles = set()
    news_list = []
    for source, src_class, url in sources:
        items = fetch_rss(source, src_class, url, max_items=4)
        for item in items:
            key = item["title"][:15]
            if key not in seen_titles:
                seen_titles.add(key)
                print(f"  🤖 [{source}] {item['title'][:30]}...")
                item["bullets"] = get_summary(item["title"])
                news_list.append(item)
                time.sleep(4)  # Gemini 무료 한도: 분당 15회 제한
        if len(news_list) >= 3:
            break
    section_news[section] = news_list[:3]
    total += len(news_list[:5])
    print(f"  ✅ {section}: {len(news_list[:5])}건 완료")

print(f"  📰 총 {total}건 처리 완료")

# ─────────────────────────────────────────
# HTML 카드 생성
# ─────────────────────────────────────────
def make_card(item, card_color):
    title   = item["title"].replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    url     = item["url"]
    source  = item["source"]
    src_cls = item["src_class"]
    pub     = item["pubtime"]
    bullets = item.get("bullets")

    bullets_html = ""
    if bullets:
        bullets_html = '<ul class="cpts">' + "".join(
            f"<li>{b}</li>" for b in bullets
        ) + "</ul>"

    return f'''
    <div class="card {card_color}">
      <div class="ct">
        <span class="src {src_cls}">{source}</span>
        <span class="ctime" data-pubtime="{pub}">🕒 --</span>
      </div>
      <div class="ch"><a href="{url}" class="ch-link" target="_blank">{title}</a></div>
      {bullets_html}
      <div class="card-history-row">
        <a href="{url}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;">↗ 원문 보기</a>
      </div>
    </div>'''

def make_section_html(section_name, items, color, card_color):
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

# last-updated 갱신
meta_new = f'<meta name="last-updated" content="{now_iso}">'
if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n{meta_new}')

# AUTO_NEWS 마커 사이 교체
new_news_html = "\n"
for section, items in section_news.items():
    if items:
        new_news_html += make_section_html(
            section, items, SECTION_COLORS[section], CARD_COLORS[section]
        )

auto_block = f"<!-- AUTO_NEWS_START -->{new_news_html}\n    <!-- AUTO_NEWS_END -->"

if "<!-- AUTO_NEWS_START -->" in html and "<!-- AUTO_NEWS_END -->" in html:
    html = re.sub(
        r'<!-- AUTO_NEWS_START -->.*?<!-- AUTO_NEWS_END -->',
        auto_block, html, flags=re.DOTALL
    )
    print("✅ 뉴스 섹션 교체 완료")
else:
    print("⚠️  AUTO_NEWS 마커 없음")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"💾 index.html 저장 완료")
print(f"[{now_display}] 🎉 모든 업데이트 완료!")
