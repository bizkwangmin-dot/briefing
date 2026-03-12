#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
세줄뉴스 자동 업데이트 (Claude API — claude-haiku-4-5)
업데이트 항목:
  ① 뉴스 4섹션 × 최대 5기사, 3줄 요약 + 버튼 3개
  ② 칼럼 최대 4건, 10줄(문단) 요약, 국내 신문사만
  ③ 사이드바: 핵심수치 / 인포그래픽 3개 / 헤드라인 / 관전포인트 / 주요이슈
  ④ 지난뉴스 아카이브 (날짜별 아코디언, 최근 7일)
"""

import os, re, sys, time, json, hashlib
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import pytz, requests
from bs4 import BeautifulSoup

# ── Claude API ──────────────────────────────────────────────
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_URL  = "https://api.anthropic.com/v1/messages"
CLAUDE_HDRS = {"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"}

def claude(prompt, max_tokens=400):
    if not CLAUDE_KEY: return None
    try:
        r = requests.post(CLAUDE_URL, headers=CLAUDE_HDRS, json={
            "model": "claude-haiku-4-5", "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }, timeout=25)
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
        print(f"  ⚠️  Claude {r.status_code}")
        return None
    except Exception as e:
        print(f"  ⚠️  {e}")
        return None

def claude_json(prompt, max_tokens=600):
    text = claude(prompt, max_tokens)
    if not text: return None
    try:
        clean = re.sub(r'^```json\s*|^```\s*|```\s*$', '', text.strip(), flags=re.MULTILINE)
        return json.loads(clean.strip())
    except Exception as e:
        print(f"  ⚠️  JSON 파싱: {e}")
        return None

# ── 기본 설정 ────────────────────────────────────────────────
KST        = pytz.timezone("Asia/Seoul")
now_kst    = datetime.now(KST)
now_iso    = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_ymd    = now_kst.strftime("%Y.%m.%d")
now_display= now_kst.strftime("%Y.%m.%d %H:%M KST")
today_str  = now_kst.strftime("%-m월 %-d일")
today_day  = now_kst.strftime("%-d")
today_sub  = now_kst.strftime("%-m월 · ") + ['일','월','화','수','목','금','토'][now_kst.weekday()]

print(f"[{now_display}] 세줄뉴스 업데이트 시작")
print(f"Claude 키: {'✅ 있음' if CLAUDE_KEY else '⚠️  없음'}")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

# ── RSS 소스 ─────────────────────────────────────────────────
NEWS_SOURCES = {
    "경제 · 금융": [
        ("매일경제","e","https://www.mk.co.kr/rss/30000001/"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/economy/"),
    ],
    "기 업": [
        ("매일경제","e","https://www.mk.co.kr/rss/30200030/"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/"),
    ],
    "정책 · 사회": [
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/"),
        ("매일경제","e","https://www.mk.co.kr/rss/30200001/"),
    ],
    "국 제": [
        ("한겨레",  "p","https://www.hani.co.kr/rss/international/"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_world.xml"),
        ("매일경제","e","https://www.mk.co.kr/rss/30300001/"),
    ],
}
COLUMN_SOURCES = [
    ("한국경제","e","https://www.hankyung.com/feed/opinion"),
    ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_opinion.xml"),
    ("한겨레",  "p","https://www.hani.co.kr/rss/opinion/"),
    ("매일경제","e","https://www.mk.co.kr/rss/30300001/"),
]
HEADLINE_SOURCES = [
    ("조선","c","https://www.chosun.com/arc/outboundfeeds/rss/"),
    ("매경","e","https://www.mk.co.kr/rss/30000001/"),
    ("한경","e","https://www.hankyung.com/feed/economy"),
    ("한겨레","p","https://www.hani.co.kr/rss/"),
    ("경향","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
]
SECTION_COLORS = {"경제 · 금융":"var(--red)","기 업":"var(--navy)","정책 · 사회":"var(--gold)","국 제":"var(--dark)"}
CARD_COLORS    = {"경제 · 금융":"red","기 업":"navy","정책 · 사회":"gold","국 제":"dk"}
HIST_KEYS      = {"경제 · 금융":"us_tariff","기 업":"samsung_buyback","정책 · 사회":"kospi_drop","국 제":"iran_war"}

def fetch_rss(source, src_class, url, max_items=6):
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "lxml-xml")
        items = []
        for item in soup.find_all("item")[:max_items]:
            t=item.find("title"); lk=item.find("link")
            pub=item.find("pubDate") or item.find("dc:date")
            if not t: continue
            title=t.get_text(strip=True)
            link=lk.get_text(strip=True) if lk else "#"
            if not link and lk: link=str(lk.next_sibling).strip()
            pub_iso=now_iso
            if pub:
                try:
                    pd=parsedate_to_datetime(pub.get_text(strip=True))
                    pub_iso=pd.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                except: pass
            items.append({"source":source,"src_class":src_class,"title":title,"url":link or "#","pubtime":pub_iso})
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

def get_summary_3(title):
    """뉴스 3줄 요약 — 기호 없이"""
    text = claude(
        f"뉴스 제목: '{title}'\n"
        "핵심 내용을 반드시 3줄로 요약해줘.\n"
        "규칙: 각 줄 앞에 어떤 기호도 없이 내용만, 한 줄 40자 이내, 수치·사실 중심, 한국어, 딱 3줄만 출력",
        max_tokens=150
    )
    if not text: return None
    lines=[l.strip().lstrip('·-•*①②③1234567890.) ').strip() for l in text.split('\n') if l.strip()]
    result=[l for l in lines if len(l)>4][:3]
    return result if len(result)>=2 else None

def get_column_summary(title):
    """칼럼 10줄 요약"""
    text = claude(
        f"칼럼/사설 제목: '{title}'\n"
        "이 칼럼의 내용을 10줄로 요약해줘.\n"
        "규칙: 각 줄 35자 이내, 핵심 주장·근거·결론 포함, 기호 없이 내용만, 한국어, 10줄만 출력",
        max_tokens=350
    )
    if not text: return []
    lines=[l.strip().lstrip('·-•*①②③1234567890.) ').strip() for l in text.split('\n') if l.strip()]
    return [l for l in lines if len(l)>4][:10]

# ════════════════════════════════════════════════════════════
# STEP 1: 뉴스 수집 + 3줄 요약
# ════════════════════════════════════════════════════════════
print("\n📡 [1/4] 뉴스 수집 + 3줄 요약...")
section_news={}; all_titles=[]

for section, sources in NEWS_SOURCES.items():
    seen=set(); news=[]
    for source, src_class, url in sources:
        for item in fetch_rss(source, src_class, url):
            key=item["title"][:15]
            if key not in seen:
                seen.add(key)
                print(f"  ✍️  [{source}] {item['title'][:30]}...")
                item["bullets"]=get_summary_3(item["title"])
                news.append(item); all_titles.append(item["title"])
                time.sleep(0.4)
        if len(news)>=5: break
    section_news[section]=news[:5]
    print(f"  ✅ {section}: {len(news[:5])}건")

# ════════════════════════════════════════════════════════════
# STEP 2: 칼럼 수집 + 10줄 요약 (국내만)
# ════════════════════════════════════════════════════════════
print("\n✍️  [2/4] 칼럼 수집 (국내 신문사)...")
columns=[]; seen_col=set()
for source, src_class, url in COLUMN_SOURCES:
    for item in fetch_rss(source, src_class, url, max_items=3):
        key=item["title"][:15]
        if key not in seen_col and len(columns)<4:
            seen_col.add(key)
            print(f"  📝 [{source}] {item['title'][:30]}...")
            item["summary_lines"]=get_column_summary(item["title"])
            columns.append(item)
            time.sleep(0.4)
print(f"  ✅ 칼럼 {len(columns)}건")

# ════════════════════════════════════════════════════════════
# STEP 3: 사이드바 (Claude 분석)
# ════════════════════════════════════════════════════════════
print("\n📊 [3/4] 사이드바 생성...")
hl_items=[]
for source, src_class, url in HEADLINE_SOURCES:
    items=fetch_rss(source, src_class, url, max_items=1)
    if items: hl_items.append({"src":source,"cls":src_class,"title":items[0]["title"],"url":items[0]["url"]})

titles_str="\n".join(f"- {t}" for t in all_titles[:20])
sidebar_data = claude_json(f"""오늘({today_str}) 뉴스 제목들:
{titles_str}

JSON만 출력 (다른 텍스트 없이):
{{
  "핵심수치": [
    {{"label":"5자이내","value":"숫자+단위","desc":"8자이내","up":true}},
    {{"label":"5자이내","value":"숫자+단위","desc":"8자이내","up":false}},
    {{"label":"5자이내","value":"숫자+단위","desc":"8자이내","up":true}}
  ],
  "인포그래픽": [
    {{"label":"항목명(8자이내)","value":"숫자+단위","pct":70,"color":"navy"}},
    {{"label":"항목명(8자이내)","value":"숫자+단위","pct":45,"color":"gold"}},
    {{"label":"항목명(8자이내)","value":"숫자+단위","pct":30,"color":"red"}}
  ],
  "관전포인트": [
    {{"title":"16자이내","sub":"22자이내"}},
    {{"title":"16자이내","sub":"22자이내"}},
    {{"title":"16자이내","sub":"22자이내"}},
    {{"title":"16자이내","sub":"22자이내"}}
  ],
  "주요이슈": ["22자이내 이슈1","22자이내 이슈2","22자이내 이슈3"],
  "칼럼논점": "오늘 칼럼들의 핵심 논점 한 문장 40자이내"
}}""", max_tokens=650)

if not sidebar_data:
    sidebar_data={"핵심수치":[{"label":"업데이트","value":"--","desc":"대기중","up":True}]*3,
                  "인포그래픽":[{"label":"업데이트","value":"--","pct":0,"color":"navy"}]*3,
                  "관전포인트":[{"title":"업데이트 대기","sub":"자동 갱신 예정"}],
                  "주요이슈":["업데이트 대기 중"],"칼럼논점":"업데이트 대기 중"}
    print("  ⚠️  기본값 사용")
else:
    print("  ✅ 사이드바 생성 완료")

# ════════════════════════════════════════════════════════════
# STEP 4: HTML 빌드
# ════════════════════════════════════════════════════════════
print("\n🔨 [4/4] HTML 빌드...")

# ── 뉴스 카드 ─────────────────────────────────────────────
def make_news_card(item, card_color, hist_key):
    title=esc(item["title"]); url=item["url"]
    src=item["source"]; sc=item["src_class"]; pub=item["pubtime"]
    bullets=item.get("bullets") or []
    bhtml=""
    if bullets:
        li="".join(f"<li>{esc(b)}</li>" for b in bullets[:3])
        bhtml=f'<ul class="cpts">{li}</ul>'
    return f'''
    <div class="card {card_color}">
      <div class="ct"><span class="src {sc}">{src}</span><span class="ctime" data-pubtime="{pub}">🕒 --</span></div>
      <div class="ch"><a href="{url}" class="ch-link" target="_blank" rel="noopener">{title}</a></div>
      {bhtml}
      <div class="card-btns">
        <button class="cbtn origin" onclick="window.open('{url}','_blank')">↗ 원문 보기</button>
        <button class="cbtn hist"   onclick="openHistory('{hist_key}',event)">📂 과거 유사</button>
        <button class="cbtn result" onclick="openResult('{hist_key}',event)">📈 결과 추적</button>
      </div>
    </div>'''

news_html="\n"
for section, items in section_news.items():
    if not items: continue
    color=SECTION_COLORS[section]; cc=CARD_COLORS[section]; hk=HIST_KEYS[section]
    news_html+=f'\n    <div class="sec"><span class="sec-tag" style="background:{color}">{section}</span><div class="sec-line"></div></div>\n'
    for item in items: news_html+=make_news_card(item, cc, hk)
news_html+="\n"

# ── 칼럼 HTML ─────────────────────────────────────────────
col_colors=["navy","red","gold","dk"]
col_html="\n    <div class=\"sec\"><span class=\"sec-tag\" style=\"background:var(--navy)\">오늘의 추천 칼럼</span><div class=\"sec-line\"></div></div>\n"
for i, item in enumerate(columns):
    cc=col_colors[i%len(col_colors)]; title=esc(item["title"]); url=item["url"]
    src=item["source"]; sc=item["src_class"]; pub=item["pubtime"]
    try:
        dt=datetime.fromisoformat(pub); date_str=dt.astimezone(KST).strftime("%Y.%m.%d")
    except: date_str=now_ymd
    summ_lines=item.get("summary_lines",[])
    body_html="<br>".join(esc(l) for l in summ_lines) if summ_lines else "요약 준비 중..."
    col_html+=f'''
    <div class="col-card {cc}">
      <div class="col-top">
        <span class="col-paper src {sc}">{src}</span>
        <span class="col-date">{date_str}</span>
      </div>
      <div class="col-title"><a href="{url}" class="ch-link" target="_blank" rel="noopener">{title}</a></div>
      <div class="col-body">{body_html}</div>
      <div style="text-align:right;margin-top:5px"><a href="{url}" target="_blank" rel="noopener" style="font-size:10px;color:var(--accent)">↗ 원문 보기</a></div>
    </div>'''
col_html+="\n"

# ── 사이드바 HTML ─────────────────────────────────────────
def build_right(data, hl_list):
    nums=data.get("핵심수치",[])
    infos=data.get("인포그래픽",[])
    pts=data.get("관전포인트",[])
    issues=data.get("주요이슈",[])

    # 핵심수치
    stats=""
    for n in nums[:3]:
        clr="r" if n.get("up",True) else "b"
        stats+=f'<div class="mstat"><div class="mnum {clr}">{esc(str(n["value"]))}</div><div class="mlbl">{esc(n["label"])}<br><small style="font-size:9px">{esc(n["desc"])}</small></div></div>'

    # 인포그래픽 바
    bar_colors={"navy":"var(--navy)","gold":"var(--gold)","red":"var(--red)","green":"var(--green)"}
    info_rows=""
    for inf in infos[:3]:
        pct=min(100,max(0,int(inf.get("pct",50))))
        color=bar_colors.get(inf.get("color","navy"),"var(--navy)")
        info_rows+=f'''<div class="info-mini-item">
          <div class="info-mini-label">{esc(inf["label"])}</div>
          <div class="info-mini-bar-wrap"><div class="info-mini-bar" style="width:{pct}%;background:{color}"></div></div>
          <div class="info-mini-val">{esc(str(inf["value"]))}</div>
        </div>'''

    # 헤드라인
    hl_html=""
    for h in hl_list[:6]:
        hl_html+=f'''<div class="hitem">
          <span class="hi-src src {h['cls']}">{esc(h['src'])}</span>
          <div><div class="hi-txt"><a href="{h['url']}" target="_blank" style="color:inherit">{esc(h['title'][:28])}</a></div>
          <div class="hi-date">{today_str} · {now_kst.strftime("%H:%M")}</div></div>
        </div>'''

    # 관전포인트
    nums_icon=['①','②','③','④']
    pts_html=""
    for i,p in enumerate(pts[:4]):
        pts_html+=f'''<div class="hitem">
          <span style="font-size:12px;font-weight:700;color:var(--navy);flex-shrink:0;width:18px;margin-top:1px">{nums_icon[i]}</span>
          <div><div class="hi-txt">{esc(p["title"])}</div><div class="hi-sub">{esc(p["sub"])}</div></div>
        </div>'''

    # 주요이슈
    iss_html="".join(f'<div class="issue-item">{esc(iss)}</div>' for iss in issues[:3])

    return f"""
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--red)"></span>오늘의 핵심 수치</div>
      <div class="mini-stats">{stats}</div>
    </div>
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--navy)"></span>오늘의 인포그래픽</div>
      <div class="info-mini">{info_rows}</div>
    </div>
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--dark)"></span>신문사별 1면 헤드라인</div>
      <div class="hlist">{hl_html}</div>
    </div>
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--gold)"></span>오늘의 관전 포인트</div>
      <div class="hlist">{pts_html}</div>
    </div>
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--dark)"></span>오늘의 주요 이슈</div>
      <div class="issue-list">{iss_html}</div>
    </div>
"""

right_html=build_right(sidebar_data, hl_items)

# 칼럼 우측
논점=esc(sidebar_data.get("칼럼논점",""))
col_right_html=f"""
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--navy)"></span>오늘의 논점</div>
      <div class="issue-list"><div class="issue-item" style="line-height:1.6">{논점}</div></div>
    </div>
"""

# ── 지난뉴스 아카이브 HTML ────────────────────────────────
def build_archive_entry(section_news_data, date_d, date_sub, date_id):
    """오늘 뉴스를 아카이브 형태로 변환"""
    all_titles_today=[]
    cards=""
    for section, items in section_news_data.items():
        color=SECTION_COLORS[section]
        cc=CARD_COLORS[section]
        for item in items[:3]:
            all_titles_today.append(item["title"])
            title=esc(item["title"]); url=item["url"]
            bullets=item.get("bullets") or []
            bhtml=""
            if bullets:
                li="".join(f"<li>{esc(b)}</li>" for b in bullets[:2])
                bhtml=f'<ul class="cpts" style="margin:4px 0">{li}</ul>'
            cards+=f'''<div class="card {cc}" style="margin-top:5px">
              <div class="ct"><span class="sec-tag" style="background:{color};font-size:8px;padding:2px 6px">{section}</span><span class="ctime" style="font-size:10px;margin-left:auto">{now_kst.strftime("%H:%M")}</span></div>
              <div class="ch" style="font-size:13px"><a href="{url}" class="ch-link" target="_blank">{title}</a></div>
              {bhtml}
            </div>'''
    # 상단 요약 제목 (3개 키워드)
    keywords="; ".join(t[:12] for t in all_titles_today[:3])
    total=sum(len(v) for v in section_news_data.values())
    return f"""
  <div>
    <div class="arch-row" onclick="tog('{date_id}')">
      <div class="aday"><div class="adaynum">{date_d}</div><div class="adaysub">{date_sub}</div></div>
      <div class="ainfo">
        <div class="atitle">{keywords}</div>
        <div class="aprev">{today_str} 뉴스 · 오전 7:30 / 오후 5:30 업데이트</div>
      </div>
      <div class="acnt">{total}건 ▾</div>
    </div>
    <div class="arch-detail open" id="{date_id}">{cards}</div>
  </div>"""

archive_entry=build_archive_entry(section_news, today_day, today_sub, f"d{today_day}_{now_kst.strftime('%H')}")
archive_html=f'<div class="arch-list">\n{archive_entry}\n</div>'

# ── index.html 교체 ───────────────────────────────────────
INDEX_PATH="index.html"
if not os.path.exists(INDEX_PATH):
    print("❌ index.html 없음"); sys.exit(1)

with open(INDEX_PATH,"r",encoding="utf-8") as f:
    html=f.read()

meta_new=f'<meta name="last-updated" content="{now_iso}">'
html=re.sub(r'<meta name="last-updated"[^>]*>',meta_new,html)

def replace_block(html,s,e,content):
    if s in html and e in html:
        return re.sub(re.escape(s)+r'.*?'+re.escape(e),f"{s}\n{content}\n{e}",html,flags=re.DOTALL)
    print(f"  ⚠️  마커 없음: {s}")
    return html

html=replace_block(html,'<!-- AUTO_NEWS_START -->',  '<!-- AUTO_NEWS_END -->',  news_html)
html=replace_block(html,'<!-- AUTO_COLUMN_START -->','<!-- AUTO_COLUMN_END -->',col_html)
html=replace_block(html,'<!-- AUTO_RIGHT_START -->', '<!-- AUTO_RIGHT_END -->', right_html)
html=replace_block(html,'<!-- AUTO_COL_RIGHT_START -->','<!-- AUTO_COL_RIGHT_END -->',col_right_html)

# 아카이브: 기존 내용 앞에 오늘 것 추가 (누적)
if '<!-- AUTO_ARCHIVE_START -->' in html and '<!-- AUTO_ARCHIVE_END -->' in html:
    arch_start=html.find('<!-- AUTO_ARCHIVE_START -->')+len('<!-- AUTO_ARCHIVE_START -->')
    arch_end=html.find('<!-- AUTO_ARCHIVE_END -->')
    existing_arch=html[arch_start:arch_end].strip()
    # 오늘 날짜 id로 중복 방지
    today_id=f"d{today_day}_{now_kst.strftime('%H')}"
    if today_id not in existing_arch:
        new_arch=f'<div class="arch-list">\n{archive_entry}\n'
        # 기존 arch-list 내용 붙이기
        existing_inner=re.sub(r'^<div class="arch-list">\s*','',existing_arch,count=1)
        existing_inner=re.sub(r'\s*</div>\s*$','',existing_inner)
        new_arch+=existing_inner+'\n</div>'
        html=replace_block(html,'<!-- AUTO_ARCHIVE_START -->','<!-- AUTO_ARCHIVE_END -->',new_arch)
        print("  ✅ 아카이브 추가")
    else:
        html=replace_block(html,'<!-- AUTO_ARCHIVE_START -->','<!-- AUTO_ARCHIVE_END -->',archive_html)
        print("  ✅ 아카이브 갱신")

with open(INDEX_PATH,"w",encoding="utf-8") as f:
    f.write(html)

print(f"\n💾 저장 완료 [{now_display}] 🎉")
print(f"  뉴스: {sum(len(v) for v in section_news.values())}건 | 칼럼: {len(columns)}건")
