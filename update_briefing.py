#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트
Gemini REST API 직접 호출 (라이브러리 버전 문제 우회)
"""

import os, re, sys, time, json
from datetime import datetime
from email.utils import parsedate_to_datetime
import pytz
import requests
from bs4 import BeautifulSoup

# ── Gemini REST API 설정 ─────────────────
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"

def get_summary(title):
    """Gemini REST API로 3줄 요약 (라이브러리 없이 직접 호출)"""
    if not GEMINI_KEY:
        return None
    payload = {
        "contents": [{"parts": [{"text": f"""뉴스 제목: '{title}'
핵심 내용을 딱 3줄로 요약해줘.
규칙: 각 줄 앞에 기호 없이 바로 내용, 한 줄 50자 이내, 구체적 수치 위주, 한국어만, 3줄만 출력"""}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 200}
    }
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=15)
        if r.status_code == 200:
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            lines = [l.strip().lstrip('·-•*0123456789. ').strip()
                     for l in text.split('\n') if l.strip()]
            result = [l for l in lines if l][:3]
            return result if result else None
        else:
            print(f"    ⚠️  Gemini {r.status_code}: {r.text[:100]}")
            return None
    except Exception as e:
        print(f"    ⚠️  요약 실패: {e}")
        return None

# ── 기본 설정 ────────────────────────────
KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")
print(f"[{now_display}] 브리핑 업데이트 시작")
print(f"Gemini 키: {'있음 ✅' if GEMINI_KEY else '없음 ⚠️'}")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
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

def fetch_rss(source, src_class, url, max_items=4):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            t  = item.find("title")
            lk = item.find("link")
            pub = item.find("pubDate") or item.find("dc:date")
            if not t: continue
            title = t.get_text(strip=True)
            link  = lk.get_text(strip=True) if lk else "#"
            if not link:
                link = str(lk.next_sibling).strip() if lk and lk.next_sibling else "#"
            pub_iso = now_iso
            if pub:
                try:
                    pd = parsedate_to_datetime(pub.get_text(strip=True))
                    pub_iso = pd.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except: pass
            items.append({
                "source": source, "src_class": src_class,
                "title": title, "url": link, "pubtime": pub_iso,
            })
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

# ── 수집 + 요약 ──────────────────────────
print("📡 뉴스 수집 + Gemini 3줄 요약 시작...")
section_news = {}
total = 0

for section, sources in RSS_SOURCES.items():
    seen = set()
    news = []
    for source, src_class, url in sources:
        for item in fetch_rss(source, src_class, url, max_items=4):
            key = item["title"][:15]
            if key not in seen:
                seen.add(key)
                print(f"  🤖 [{source}] {item['title'][:28]}...")
                item["bullets"] = get_summary(item["title"])
                news.append(item)
                time.sleep(5)  # 분당 12회 → 무료 한도(15회) 준수
        if len(news) >= 5:
            break
    section_news[section] = news[:5]
    total += len(news[:5])
    print(f"  ✅ {section}: {len(news[:5])}건")

print(f"  📰 총 {total}건 완료")

# ── 카드 HTML ────────────────────────────
def make_card(item, card_color):
    title   = item["title"].replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    url     = item["url"]
    src     = item["source"]
    sc      = item["src_class"]
    pub     = item["pubtime"]
    bullets = item.get("bullets")
    bhtml = ""
    if bullets:
        bhtml = '<ul class="cpts">' + "".join(f"<li>{b}</li>" for b in bullets) + "</ul>"
    return f'''
    <div class="card {card_color}">
      <div class="ct">
        <span class="src {sc}">{src}</span>
        <span class="ctime" data-pubtime="{pub}">🕒 --</span>
      </div>
      <div class="ch"><a href="{url}" class="ch-link" target="_blank">{title}</a></div>
      {bhtml}
      <div class="card-history-row">
        <a href="{url}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;">↗ 원문 보기</a>
      </div>
    </div>'''

def make_section(name, items, color, card_color):
    h = f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{name}</span><div class="sec-line"></div></div>\n'
    for item in items: h += make_card(item, card_color)
    return h

# ── index.html 업데이트 ──────────────────
INDEX_PATH = "index.html"
if not os.path.exists(INDEX_PATH):
    print("❌ index.html 없음"); sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# last-updated 갱신
meta_new = f'<meta name="last-updated" content="{now_iso}">'
if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n{meta_new}')

# AUTO_NEWS 마커 교체
new_html = "\n"
for section, items in section_news.items():
    if items:
        new_html += make_section(section, items, SECTION_COLORS[section], CARD_COLORS[section])

auto_block = f"<!-- AUTO_NEWS_START -->{new_html}\n    <!-- AUTO_NEWS_END -->"

if "<!-- AUTO_NEWS_START -->" in html and "<!-- AUTO_NEWS_END -->" in html:
    html = re.sub(
        r'<!-- AUTO_NEWS_START -->.*?<!-- AUTO_NEWS_END -->',
        auto_block, html, flags=re.DOTALL
    )
    print("✅ 뉴스 섹션 교체 완료")
else:
    print("❌ AUTO_NEWS 마커 없음"); sys.exit(1)

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"💾 저장 완료 — [{now_display}] 🎉")
