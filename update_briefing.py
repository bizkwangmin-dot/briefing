#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트 (Claude API)
업데이트 항목:
  - 오늘의 뉴스 (4개 섹션 × 5기사, 3줄 요약)
  - 칼럼 (국내 주요 칼럼 RSS)
  - 우측 사이드바 (핵심수치 / 신문사 헤드라인 / 관전포인트 / 지난뉴스 요약)
"""

import os, re, sys, time, json
from datetime import datetime
from email.utils import parsedate_to_datetime
import pytz
import requests
from bs4 import BeautifulSoup

# ── Claude API ───────────────────────────
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_URL  = "https://api.anthropic.com/v1/messages"
CLAUDE_HDRS = {
    "x-api-key": CLAUDE_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json",
}

def claude(prompt, max_tokens=400):
    if not CLAUDE_KEY:
        return None
    try:
        r = requests.post(CLAUDE_URL, headers=CLAUDE_HDRS, json={
            "model": "claude-haiku-4-5",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }, timeout=25)
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
        print(f"  ⚠️  Claude {r.status_code}: {r.text[:80]}")
        return None
    except Exception as e:
        print(f"  ⚠️  {e}")
        return None

# ── 기본 설정 ────────────────────────────
KST = pytz.timezone("Asia/Seoul")
now_kst    = datetime.now(KST)
now_iso    = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_display= now_kst.strftime("%Y.%m.%d %H:%M KST")
today_str  = now_kst.strftime("%m월 %d일")
print(f"[{now_display}] 브리핑 업데이트 시작")
print(f"Claude 키: {'✅' if CLAUDE_KEY else '⚠️  없음'}")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# ── RSS 소스 정의 ────────────────────────
NEWS_SOURCES = {
    "경제 · 금융": [
        ("매일경제", "e", "https://www.mk.co.kr/rss/30000001/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/economy/"),
    ],
    "기 업": [
        ("매일경제", "e", "https://www.mk.co.kr/rss/30200030/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/"),
    ],
    "정책 · 사회": [
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("한겨레",   "p", "https://www.hani.co.kr/rss/"),
        ("매일경제", "e", "https://www.mk.co.kr/rss/30200001/"),
    ],
    "국 제": [
        ("한겨레",   "p", "https://www.hani.co.kr/rss/international/"),
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_world.xml"),
        ("매일경제", "e", "https://www.mk.co.kr/rss/30300001/"),
    ],
}

COLUMN_SOURCES = [
    ("한국경제", "e", "https://www.hankyung.com/feed/opinion"),
    ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_opinion.xml"),
    ("한겨레",   "p", "https://www.hani.co.kr/rss/opinion/"),
    ("매일경제", "e", "https://www.mk.co.kr/rss/30300001/"),
]

HEADLINE_SOURCES = [
    ("조선", "c", "https://www.chosun.com/arc/outboundfeeds/rss/"),
    ("매경", "e", "https://www.mk.co.kr/rss/30000001/"),
    ("한경", "e", "https://www.hankyung.com/feed/economy"),
    ("한겨레", "p", "https://www.hani.co.kr/rss/"),
    ("경향", "p", "https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
]

SECTION_COLORS = {
    "경제 · 금융": "var(--red)", "기 업": "var(--navy)",
    "정책 · 사회": "var(--gold)", "국 제": "var(--dark)",
}
CARD_COLORS = {
    "경제 · 금융": "red", "기 업": "navy",
    "정책 · 사회": "gold", "국 제": "dk",
}

# ── RSS 수집 ─────────────────────────────
def fetch_rss(source, src_class, url, max_items=5):
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

def get_summary(title):
    text = claude(
        f"뉴스 제목: '{title}'\n"
        "핵심 내용을 3줄로 요약해줘.\n"
        "규칙: 줄 앞에 기호 없이 내용만, 한 줄 40자 이내, 수치·사실 위주, 한국어, 딱 3줄만 출력",
        max_tokens=150
    )
    if not text: return None
    lines = [l.strip().lstrip('·-•*0123456789.) ').strip()
             for l in text.split('\n') if l.strip()]
    result = [l for l in lines if len(l) > 3][:3]
    return result if result else None

# ════════════════════════════════════════
# 1. 뉴스 수집 + 요약
# ════════════════════════════════════════
print("\n📡 [1/4] 뉴스 수집 + 요약...")
section_news = {}
all_titles   = []
total = 0

for section, sources in NEWS_SOURCES.items():
    seen = set(); news = []
    for source, src_class, url in sources:
        for item in fetch_rss(source, src_class, url):
            key = item["title"][:15]
            if key not in seen:
                seen.add(key)
                print(f"  ✍️  [{source}] {item['title'][:30]}...")
                item["bullets"] = get_summary(item["title"])
                news.append(item)
                all_titles.append(item["title"])
                time.sleep(0.3)
        if len(news) >= 5: break
    section_news[section] = news[:5]
    total += len(news[:5])
    print(f"  ✅ {section}: {len(news[:5])}건")
print(f"  📰 총 {total}건")

# ════════════════════════════════════════
# 2. 칼럼 수집 + 요약
# ════════════════════════════════════════
print("\n✍️  [2/4] 칼럼 수집...")
columns = []
seen_col = set()
for source, src_class, url in COLUMN_SOURCES:
    for item in fetch_rss(source, src_class, url, max_items=3):
        key = item["title"][:15]
        if key not in seen_col and len(columns) < 5:
            seen_col.add(key)
            print(f"  📝 [{source}] {item['title'][:30]}...")
            item["summary"] = claude(
                f"칼럼/사설 제목: '{item['title']}'\n"
                "이 칼럼의 핵심 주장을 2줄로 요약해줘. 한국어, 각 줄 40자 이내, 기호 없이.",
                max_tokens=100
            )
            columns.append(item)
            time.sleep(0.3)
print(f"  ✅ 칼럼 {len(columns)}건")

# ════════════════════════════════════════
# 3. 사이드바 생성 (Claude가 분석)
# ════════════════════════════════════════
print("\n📊 [3/4] 사이드바 생성...")
titles_str = "\n".join(f"- {t}" for t in all_titles[:20])

sidebar_json = claude(f"""오늘({today_str}) 뉴스 제목들:
{titles_str}

아래 JSON만 출력해 (다른 텍스트 없이):
{{
  "핵심수치": [
    {{"label": "라벨(5자이내)", "value": "숫자+단위", "desc": "설명(8자이내)"}},
    {{"label": "라벨", "value": "숫자+단위", "desc": "설명"}},
    {{"label": "라벨", "value": "숫자+단위", "desc": "설명"}}
  ],
  "헤드라인": [
    {{"src": "신문사명(3자이내)", "cls": "c또는e또는p또는w", "title": "헤드라인(18자이내)", "sub": "부제(16자이내)"}},
    {{"src": "신문사명", "cls": "e", "title": "헤드라인", "sub": "부제"}},
    {{"src": "신문사명", "cls": "p", "title": "헤드라인", "sub": "부제"}},
    {{"src": "신문사명", "cls": "p", "title": "헤드라인", "sub": "부제"}},
    {{"src": "신문사명", "cls": "w", "title": "헤드라인", "sub": "부제"}}
  ],
  "관전포인트": [
    {{"title": "제목(16자이내)", "sub": "설명(22자이내)"}},
    {{"title": "제목", "sub": "설명"}},
    {{"title": "제목", "sub": "설명"}},
    {{"title": "제목", "sub": "설명"}}
  ],
  "지난뉴스요약": {{"title": "오늘 핵심 3줄(60자이내 전체)", "items": ["이슈1(20자이내)", "이슈2(20자이내)", "이슈3(20자이내)"]}}
}}""", max_tokens=700)

sidebar_data = None
if sidebar_json:
    try:
        clean = re.sub(r'^```json\s*|```\s*$', '', sidebar_json.strip())
        sidebar_data = json.loads(clean)
        print("  ✅ 사이드바 데이터 생성")
    except Exception as e:
        print(f"  ⚠️  JSON 파싱 실패: {e}")

# ════════════════════════════════════════
# 4. HTML 빌드
# ════════════════════════════════════════
print("\n🔨 [4/4] HTML 빌드...")

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
    color = SECTION_COLORS[name]; cc = CARD_COLORS[name]
    h = f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{name}</span><div class="sec-line"></div></div>\n'
    for item in items: h += make_card(item, cc)
    return h

# 뉴스 HTML
news_html = "\n"
for section, items in section_news.items():
    if items: news_html += make_section(section, items)

# 칼럼 HTML
col_colors = ["red", "navy", "gold", "dk", "green"]
col_html = "\n"
col_html += '    <div class="sec"><span class="sec-tag" style="background:var(--navy)">오늘의 추천 칼럼</span><div class="sec-line"></div></div>\n'
for i, item in enumerate(columns):
    cc = col_colors[i % len(col_colors)]
    title = item["title"].replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')
    summ  = item.get("summary", "")
    summ_html = ""
    if summ:
        lines = [l.strip().lstrip('·-•*0123456789.) ').strip()
                 for l in summ.split('\n') if l.strip()][:2]
        summ_html = '<ul class="cpts">' + "".join(f"<li>{l}</li>" for l in lines if l) + "</ul>"
    col_html += f'''
    <div class="card {cc}">
      <div class="ct">
        <span class="src {item['src_class']}">{item['source']}</span>
        <span class="ctime" data-pubtime="{item['pubtime']}">🕒 --</span>
      </div>
      <div class="ch"><a href="{item['url']}" class="ch-link" target="_blank">{title}</a></div>
      {summ_html}
      <div class="card-history-row">
        <a href="{item['url']}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;">↗ 원문 보기</a>
      </div>
    </div>'''

# 우측 사이드바 HTML
def build_sidebar(data):
    if not data:
        return ""

    # 핵심 수치
    nums = data.get("핵심수치", [])
    stats_html = ""
    for n in nums[:3]:
        stats_html += f'''
        <div class="mstat">
          <div class="mnum r">{n["value"]}</div>
          <div class="mlbl">{n["label"]}<br><small style="font-size:9px;color:var(--ink3)">{n["desc"]}</small></div>
        </div>'''

    # 신문사 헤드라인
    headlines = data.get("헤드라인", [])
    hl_html = ""
    for h in headlines[:6]:
        hl_html += f'''
        <div class="hitem">
          <span class="hi-src src {h['cls']}">{h['src']}</span>
          <div><div class="hi-txt">{h['title']}</div><div class="hi-sub">{h['sub']}</div></div>
        </div>'''

    # 관전 포인트
    pts = data.get("관전포인트", [])
    pts_html = ""
    for i, p in enumerate(pts[:4]):
        pts_html += f'''
        <div class="hitem">
          <span class="hi-src src c" style="background:#f0ede6;color:#0f2744;font-weight:700">{'①②③④'[i]}</span>
          <div><div class="hi-txt">{p['title']}</div><div class="hi-sub">{p['sub']}</div></div>
        </div>'''

    # 지난뉴스 요약 (사이드바 하단)
    arch = data.get("지난뉴스요약", {})
    arch_items = arch.get("items", [])
    arch_html = ""
    if arch_items:
        items_html = "".join(f'<li style="margin-bottom:4px;font-size:12px;color:var(--ink2)">{it}</li>' for it in arch_items)
        arch_html = f'''
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--dark)"></span>오늘의 주요 이슈</div>
      <ul style="list-style:none;padding:0;margin:8px 0 0">{items_html}</ul>
    </div>'''

    return f'''
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--red)"></span>오늘의 핵심 수치</div>
      <div class="mini-stats">{stats_html}
      </div>
    </div>

    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--navy)"></span>신문사별 1면 헤드라인</div>
      <div class="hlist">{hl_html}
      </div>
    </div>

    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--gold)"></span>오늘의 관전 포인트</div>
      <div class="hlist">{pts_html}
      </div>
    </div>
{arch_html}'''

sidebar_html = build_sidebar(sidebar_data)

# ── index.html 교체 ──────────────────────
INDEX_PATH = "index.html"
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# last-updated
meta_new = f'<meta name="last-updated" content="{now_iso}">'
if '<meta name="last-updated"' in html:
    html = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html)
else:
    html = html.replace('<meta charset="UTF-8">', f'<meta charset="UTF-8">\n  {meta_new}')

def replace_block(html, start_marker, end_marker, new_content):
    if start_marker in html and end_marker in html:
        block = f"{start_marker}\n{new_content}\n{end_marker}"
        return re.sub(
            re.escape(start_marker) + r'.*?' + re.escape(end_marker),
            block, html, flags=re.DOTALL
        )
    return html

html = replace_block(html, '<!-- AUTO_NEWS_START -->',   '<!-- AUTO_NEWS_END -->',   news_html)
html = replace_block(html, '<!-- AUTO_COLUMN_START -->', '<!-- AUTO_COLUMN_END -->', col_html)
if sidebar_html:
    html = replace_block(html, '<!-- AUTO_RIGHT_START -->', '<!-- AUTO_RIGHT_END -->', sidebar_html)

print("✅ 뉴스 섹션 교체")
print("✅ 칼럼 섹션 교체")
print("✅ 사이드바 교체" if sidebar_html else "⚠️  사이드바 기존 유지")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n💾 저장 완료 [{now_display}] 🎉")
