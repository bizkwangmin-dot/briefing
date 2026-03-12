#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트
- Gemini REST API 직접 호출 (gemini-2.0-flash-lite: 무료, 안정)
- 뉴스 3줄 요약 + 인포그래픽 자동 갱신
- 하루 2회 (오전 7:30 / 오후 5:30 KST)
"""

import os, re, sys, time, json
from datetime import datetime
from email.utils import parsedate_to_datetime
import pytz
import requests
from bs4 import BeautifulSoup

# ── Gemini REST API ──────────────────────
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
# gemini-2.0-flash-lite: 무료 티어 가장 안정적
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-lite:generateContent?key=" + GEMINI_KEY
)

def gemini(prompt, max_tokens=300):
    """Gemini REST API 직접 호출"""
    if not GEMINI_KEY:
        return None
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_tokens},
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_NONE"}
            for c in ["HARM_CATEGORY_HARASSMENT","HARM_CATEGORY_HATE_SPEECH",
                      "HARM_CATEGORY_SEXUALLY_EXPLICIT","HARM_CATEGORY_DANGEROUS_CONTENT"]
        ]
    }
    try:
        r = requests.post(GEMINI_URL, json=payload, timeout=20)
        if r.status_code == 200:
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            err = r.json().get("error", {})
            print(f"    ⚠️  Gemini {r.status_code}: {err.get('message','')[:80]}")
            return None
    except Exception as e:
        print(f"    ⚠️  요청 실패: {e}")
        return None

def get_summary(title):
    """뉴스 제목 → 3줄 요약"""
    prompt = f"""뉴스 제목: '{title}'
핵심 내용을 3줄로 요약해줘.
규칙: 줄 앞에 기호 없이 내용만, 한 줄 45자 이내, 수치·사실 위주, 한국어, 딱 3줄만"""
    text = gemini(prompt, max_tokens=200)
    if not text:
        return None
    lines = [l.strip().lstrip('·-•*0123456789.) ').strip()
             for l in text.split('\n') if l.strip()]
    result = [l for l in lines if len(l) > 3][:3]
    return result if result else None

# ── 기본 설정 ────────────────────────────
KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")
print(f"[{now_display}] 브리핑 업데이트 시작")
print(f"Gemini 키: {'✅ 있음' if GEMINI_KEY else '⚠️  없음'}")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                  'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36'
}

# ── RSS 소스 ─────────────────────────────
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

# ── RSS 수집 ─────────────────────────────
def fetch_rss(source, src_class, url, max_items=4):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            t   = item.find("title")
            lk  = item.find("link")
            pub = item.find("pubDate") or item.find("dc:date")
            if not t: continue
            title = t.get_text(strip=True)
            link  = lk.get_text(strip=True) if lk else "#"
            if not link and lk:
                link = str(lk.next_sibling).strip()
            pub_iso = now_iso
            if pub:
                try:
                    pd = parsedate_to_datetime(pub.get_text(strip=True))
                    pub_iso = pd.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except: pass
            items.append({
                "source": source, "src_class": src_class,
                "title": title, "url": link or "#", "pubtime": pub_iso,
            })
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

# ── 뉴스 수집 + 3줄 요약 ─────────────────
print("📡 뉴스 수집 + 3줄 요약 시작...")
section_news = {}
all_titles   = []   # 인포그래픽 생성에 사용
total = 0

for section, sources in RSS_SOURCES.items():
    seen = set()
    news = []
    for source, src_class, url in sources:
        for item in fetch_rss(source, src_class, url):
            key = item["title"][:15]
            if key not in seen:
                seen.add(key)
                print(f"  🤖 [{source}] {item['title'][:30]}...")
                item["bullets"] = get_summary(item["title"])
                if item["bullets"]:
                    print(f"      ✅ 요약 완료")
                news.append(item)
                all_titles.append(item["title"])
                time.sleep(5)   # 분당 12회 — 무료 한도(15회) 안전 준수
        if len(news) >= 5:
            break
    section_news[section] = news[:5]
    total += len(news[:5])
    print(f"  ✅ {section}: {len(news[:5])}건")

print(f"  📰 총 {total}건 수집 완료")

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

def make_section(name, items):
    color = SECTION_COLORS[name]
    card_color = CARD_COLORS[name]
    h = f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{name}</span><div class="sec-line"></div></div>\n'
    for item in items:
        h += make_card(item, card_color)
    return h

# ── 인포그래픽 자동 갱신 ─────────────────
def make_infographic(titles):
    """수집된 뉴스 제목들로 오늘의 트렌드 인포그래픽 생성"""
    print("\n📊 인포그래픽 생성 중...")
    titles_str = "\n".join(f"- {t}" for t in titles[:20])
    today = now_kst.strftime("%Y년 %m월 %d일")

    prompt = f"""오늘({today}) 뉴스 제목 목록:
{titles_str}

위 뉴스를 분석해서 아래 JSON 형식으로 오늘의 뉴스 트렌드 인포그래픽 데이터를 만들어줘.
JSON만 출력하고 다른 텍스트 없이:
{{
  "핵심수치": [
    {{"label": "라벨(5자이내)", "value": "숫자+단위", "desc": "설명(8자이내)"}},
    {{"label": "라벨", "value": "숫자+단위", "desc": "설명"}},
    {{"label": "라벨", "value": "숫자+단위", "desc": "설명"}}
  ],
  "키워드": [
    {{"word": "키워드1", "count": 5}},
    {{"word": "키워드2", "count": 4}},
    {{"word": "키워드3", "count": 3}},
    {{"word": "키워드4", "count": 3}},
    {{"word": "키워드5", "count": 2}}
  ],
  "주요이슈": [
    {{"title": "이슈 제목(15자이내)", "desc": "한줄 설명(30자이내)", "tag": "태그"}},
    {{"title": "이슈 제목", "desc": "한줄 설명", "tag": "태그"}},
    {{"title": "이슈 제목", "desc": "한줄 설명", "tag": "태그"}}
  ]
}}"""

    text = gemini(prompt, max_tokens=600)
    if not text:
        return None
    try:
        text = re.sub(r'^```json\s*|```\s*$', '', text.strip())
        return json.loads(text)
    except Exception as e:
        print(f"  ⚠️  JSON 파싱 실패: {e}")
        return None

def render_infographic(data, today_str):
    """인포그래픽 HTML 생성"""
    nums = data.get("핵심수치", [])
    keywords = data.get("키워드", [])
    issues = data.get("주요이슈", [])
    max_count = max((k["count"] for k in keywords), default=1)

    # 핵심 수치 카드
    num_html = ""
    for n in nums[:3]:
        num_html += f'''
  <div class="icard">
    <div class="ititle">📌 {n["label"]}</div>
    <div class="isub">{n["desc"]}</div>
    <div style="font-size:32px;font-weight:800;color:var(--red);margin:12px 0">{n["value"]}</div>
  </div>'''

    # 키워드 바 차트
    kw_rows = ""
    for k in keywords[:5]:
        pct = int(k["count"] / max_count * 100)
        kw_rows += f'''
      <div class="brow">
        <span class="blbl">{k["word"]}</span>
        <div class="btrack"><div class="bfill" style="width:{pct}%"></div></div>
        <span class="bval">{k["count"]}</span>
      </div>'''

    kw_html = f'''
  <div class="icard r">
    <div class="ititle">🔥 오늘의 키워드</div>
    <div class="isub">{today_str} 뉴스 빈도 분석</div>
    <div class="bchart">{kw_rows}
    </div>
  </div>'''

    # 주요 이슈
    issue_html = ""
    for iss in issues[:3]:
        issue_html += f'''
  <div class="icard">
    <div class="ititle">⚡ {iss["title"]}</div>
    <div class="isub">{iss.get("tag","이슈")}</div>
    <p style="font-size:13px;color:var(--text);margin:10px 0">{iss["desc"]}</p>
  </div>'''

    return f'''<div class="info-grid">
{num_html}
{kw_html}
{issue_html}
</div>'''

# ── index.html 업데이트 ──────────────────
INDEX_PATH = "index.html"
if not os.path.exists(INDEX_PATH):
    print("❌ index.html 없음")
    sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# last-updated 갱신
meta_new = f'<meta name="last-updated" content="{now_iso}">'
if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n  {meta_new}')

# ── 뉴스 섹션 교체 ──
new_news_html = "\n"
for section, items in section_news.items():
    if items:
        new_news_html += make_section(section, items)

news_block = f"<!-- AUTO_NEWS_START -->{new_news_html}\n    <!-- AUTO_NEWS_END -->"
if "<!-- AUTO_NEWS_START -->" in html:
    html = re.sub(r'<!-- AUTO_NEWS_START -->.*?<!-- AUTO_NEWS_END -->', news_block, html, flags=re.DOTALL)
    print("✅ 뉴스 섹션 교체 완료")
else:
    print("❌ AUTO_NEWS 마커 없음")
    sys.exit(1)

# ── 인포그래픽 섹션 교체 ──
if all_titles and "<!-- AUTO_INFO_START -->" in html:
    time.sleep(3)
    info_data = make_infographic(all_titles)
    if info_data:
        today_str = now_kst.strftime("%m월 %d일")
        info_html = render_infographic(info_data, today_str)
        info_block = f"<!-- AUTO_INFO_START -->\n{info_html}\n<!-- AUTO_INFO_END -->"
        html = re.sub(r'<!-- AUTO_INFO_START -->.*?<!-- AUTO_INFO_END -->', info_block, html, flags=re.DOTALL)
        print("✅ 인포그래픽 갱신 완료")
    else:
        print("⚠️  인포그래픽 생성 실패 — 기존 유지")
else:
    print("⚠️  AUTO_INFO 마커 없거나 뉴스 없음 — 인포그래픽 스킵")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n💾 저장 완료")
print(f"🎉 [{now_display}] 완료!")
