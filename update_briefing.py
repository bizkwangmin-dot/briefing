#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 업데이트 시간: 오전 7:25 KST (UTC 22:25), 오후 5:20 KST (UTC 08:20)
# auto-update.yml cron: "25 22 * * *" and "20 8 * * *"
"""
세줄뉴스 자동 업데이트 v4 (최신 디자인 반영)
- 클릭해서 펼치는 카드 구조
- 좋아요 + 과거 사례(인라인) + 기사 보기
- 칼럼 탭 포함
- 뉴모피즘 간소화 모드 호환
"""

import os, re, sys, time, json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import pytz, requests
from bs4 import BeautifulSoup

# ── Claude API ──────────────────────────────────────────────
CLAUDE_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_URL  = "https://api.anthropic.com/v1/messages"
CLAUDE_HDRS = {
    "x-api-key": CLAUDE_KEY,
    "anthropic-version": "2023-06-01",
    "content-type": "application/json"
}

def claude(prompt, max_tokens=400):
    if not CLAUDE_KEY: return None
    try:
        r = requests.post(CLAUDE_URL, headers=CLAUDE_HDRS, json={
            "model": "claude-haiku-4-5",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        }, timeout=30)
        if r.status_code == 200:
            return r.json()["content"][0]["text"].strip()
        print(f"  ⚠️  Claude {r.status_code}: {r.text[:100]}")
        return None
    except Exception as e:
        print(f"  ⚠️  {e}")
        return None

def claude_json(prompt, max_tokens=700):
    text = claude(prompt, max_tokens)
    if not text: return None
    try:
        clean = re.sub(r'^```json\s*|^```\s*|```\s*$', '', text.strip(), flags=re.MULTILINE)
        return json.loads(clean.strip())
    except Exception as e:
        print(f"  ⚠️  JSON 파싱 오류: {e}")
        return None

# ── 기본 설정 ────────────────────────────────────────────────
KST         = pytz.timezone("Asia/Seoul")
now_kst     = datetime.now(KST)
now_iso     = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")
now_ymd     = now_kst.strftime("%Y.%m.%d")
now_display = now_kst.strftime("%Y.%m.%d %H:%M KST")
today_str   = now_kst.strftime("%-m월 %-d일")
today_day   = now_kst.strftime("%-d")
today_sub   = now_kst.strftime("%-m월 · ") + ['일','월','화','수','목','금','토'][now_kst.weekday()]
weekday_ko  = ['월','화','수','목','금','토','일'][now_kst.weekday()]
header_date = f"{now_kst.strftime('%Y.%-m.%-d')} ({weekday_ko})"

# update_display는 수집 후 최신 기사 발행 시각 기준으로 재계산
def make_update_display(latest_dt):
    """최신 기사 발행 시각 기준 업데이트 표시 문자열"""
    label = "오전" if latest_dt.hour < 12 else "오후"
    return f"기사 기준 {label} {latest_dt.strftime('%-H:%M')}"

print(f"[{now_display}] 세줄뉴스 v4 업데이트 시작")
print(f"Claude 키: {'✅ 있음' if CLAUDE_KEY else '⚠️  없음 (요약 생략)'}")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

# ── RSS 소스 ─────────────────────────────────────────────────
# 전체 신문사 RSS 소스 (섹션별 최적 URL)
ALL_NEWS_SOURCES = {
    "경제 · 금융": [
        ("조선일보","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("중앙일보","c","https://www.joongang.co.kr/sitemap/rss"),
        ("동아일보","c","https://rss.donga.com/total.xml"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("매일경제","e","https://www.mk.co.kr/rss/30000001/"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/economy/"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_economy.xml"),
        ("연합뉴스","w","https://www.yna.co.kr/rss/economy.xml"),
    ],
    "기 업": [
        ("조선일보","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("중앙일보","c","https://www.joongang.co.kr/sitemap/rss"),
        ("동아일보","c","https://rss.donga.com/total.xml"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("매일경제","e","https://www.mk.co.kr/rss/30200030/"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("연합뉴스","w","https://www.yna.co.kr/rss/economy.xml"),
    ],
    "정책 · 사회": [
        ("조선일보","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("중앙일보","c","https://www.joongang.co.kr/sitemap/rss"),
        ("동아일보","c","https://rss.donga.com/politics.xml"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("매일경제","e","https://www.mk.co.kr/rss/30200001/"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
        ("연합뉴스","w","https://www.yna.co.kr/rss/politics.xml"),
    ],
    "국 제": [
        ("조선일보","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
        ("중앙일보","c","https://www.joongang.co.kr/sitemap/rss"),
        ("동아일보","c","https://rss.donga.com/international.xml"),
        ("한국경제","e","https://www.hankyung.com/feed/economy"),
        ("매일경제","e","https://www.mk.co.kr/rss/30300001/"),
        ("한겨레",  "p","https://www.hani.co.kr/rss/international/"),
        ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_world.xml"),
        ("연합뉴스","w","https://www.yna.co.kr/rss/international.xml"),
    ],
}

import random as _random
def build_shuffled_sources(section):
    """섹션별 소스를 랜덤 셔플 — 매 실행마다 신문사 순서 다름"""
    sources = list(ALL_NEWS_SOURCES[section])
    _random.shuffle(sources)
    return sources

NEWS_SOURCES = {sec: ALL_NEWS_SOURCES[sec] for sec in ALL_NEWS_SOURCES}

COLUMN_SOURCES = [
    ("조선일보","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("중앙일보","c","https://www.joongang.co.kr/sitemap/rss"),
    ("동아일보","c","https://rss.donga.com/opinion.xml"),
    ("한국경제","e","https://www.hankyung.com/feed/opinion"),
    ("매일경제","e","https://www.mk.co.kr/rss/30300001/"),
    ("한겨레",  "p","https://www.hani.co.kr/rss/opinion/"),
    ("경향신문","p","https://www.khan.co.kr/rss/rssdata/kh_opinion.xml"),
    ("연합뉴스","w","https://www.yna.co.kr/rss/politics.xml"),
]

# 해외 칼럼/오피니언 소스 (매일 랜덤 2곳 선택)
INTL_COLUMN_SOURCES = [
    ("월스트리트저널","intl","https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"),
    ("뉴욕타임스",   "intl","https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("가디언",       "intl","https://www.theguardian.com/business/rss"),
    ("BBC비즈니스",  "intl","https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("로이터",       "intl","https://feeds.reuters.com/reuters/businessNews"),
]  # 블룸버그/FT는 구독 필요로 제외, 공개 RSS만 유지

HEADLINE_SOURCES = [
    ("조선","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("중앙","c","https://rss.joinsmsn.com/joins_news_list.xml"),
    ("동아","c","https://rss.donga.com/economy.xml"),
    ("매경","e","https://www.mk.co.kr/rss/30000001/"),
    ("한경","e","https://www.hankyung.com/feed/economy"),
    ("한겨레","p","https://www.hani.co.kr/rss/"),
    ("경향","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
    ("연합","w","https://www.yonhapnews.co.kr/rss/economy.xml"),
]

INTL_SOURCES = [
    ("블룸버그",    "intl", "https://feeds.bloomberg.com/markets/news.rss"),
    ("파이낸셜타임스","intl","https://www.ft.com/rss/home"),
    ("월스트리트저널","intl","https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    ("뉴욕타임스",  "intl", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("가디언",      "intl", "https://www.theguardian.com/world/rss"),
]

# 반드시 1개씩 포함해야 할 지역별 소스
INTL_REGION_SOURCES = {
    "일본": [
        ("재팬타임스","intl","https://feeds.japantimes.co.jp/japantimes/business"),
        ("닛케이아시아","intl","https://asia.nikkei.com/rss/feed/nar"),
    ],
    "중국": [
        ("SCMP",      "intl","https://www.scmp.com/rss/91/feed"),
        ("신화통신",  "intl","http://www.xinhuanet.com/english/rss/chineseeconomyrss.xml"),
    ],
    "유럽": [
        ("가디언",    "intl","https://www.theguardian.com/world/rss"),
        ("파이낸셜타임스","intl","https://www.ft.com/rss/home"),
    ],
}
INTL_HIST_KEYS = {
    "블룸버그":     "iran_war",
    "파이낸셜타임스":"us_tariff",
    "월스트리트저널":"samsung_buyback",
    "뉴욕타임스":   "iran_war",
    "니혼게이자이신문":"iran_war",
    "가디언":       "iran_war",
}
SECTION_COLORS = {
    "경제 · 금융": "var(--red)",
    "기 업":       "var(--navy)",
    "정책 · 사회": "var(--gold)",
    "국 제":       "var(--dark)"
}
CARD_COLORS = {
    "경제 · 금융": "red",
    "기 업":       "navy",
    "정책 · 사회": "gold",
    "국 제":       "dk"
}
# 섹션별 과거 사례 키 (CASE_DATA JS 객체 키와 매핑)
HIST_KEYS = {
    "경제 · 금융": "us_tariff",
    "기 업":       "samsung_buyback",
    "정책 · 사회": "kospi_drop",
    "국 제":       "iran_war"
}
HIST_LABELS = {
    "us_tariff":       "미국 관세·무역",
    "samsung_buyback": "삼성·SK 자사주 소각",
    "kospi_drop":      "코스피 급락·증시 변동",
    "iran_war":        "이란 중동 정세"
}

# ── RSS 파싱 ─────────────────────────────────────────────────
def fetch_rss(source, src_class, url, max_items=12, today_only=True):
    """RSS 피드 파싱. today_only=True이면 오늘/어제(KST) 기사만 반환"""
    from datetime import timedelta
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        # lxml-xml 실패 시 html.parser로 폴백
        try:
            soup = BeautifulSoup(r.content, "lxml-xml")
            if not soup.find("item"):
                soup = BeautifulSoup(r.content, "html.parser")
        except Exception:
            soup = BeautifulSoup(r.content, "html.parser")

        items = []
        today_date     = now_kst.date()
        cutoff_date    = today_date - timedelta(days=2)  # 최대 2일 전까지 허용 (RSS 지연 대응)

        rss_items = soup.find_all("item") or soup.find_all("entry")

        for item in rss_items[:max_items]:
            t   = item.find("title")
            lk  = item.find("link")
            pub = (item.find("pubDate") or item.find("pubdate") or
                   item.find("dc:date") or item.find("published") or
                   item.find("updated"))
            if not t:
                continue
            title = t.get_text(strip=True)
            if not title or len(title) < 5 or title.lower() in ("rss","feed",""):
                continue

            # 링크 추출 (Atom의 href 속성도 처리)
            link = "#"
            if lk:
                link = (lk.get("href") or lk.get_text(strip=True) or
                        str(lk.next_sibling or "").strip() or "#")

            pub_iso  = now_iso
            pub_date = today_date  # 날짜 파싱 실패 → 오늘로 간주 (수집 허용)
            date_parsed = False
            if pub:
                pub_str = pub.get_text(strip=True)
                # 여러 포맷 시도
                for parser_fn in [
                    lambda s: parsedate_to_datetime(s),
                    lambda s: datetime.fromisoformat(s.replace("Z", "+00:00")),
                ]:
                    try:
                        pd = parser_fn(pub_str)
                        pub_date    = pd.astimezone(KST).date()
                        pub_iso     = pd.astimezone(KST).strftime("%Y-%m-%dT%H:%M:%S+09:00")
                        date_parsed = True
                        break
                    except Exception:
                        continue

            # 날짜 필터: 파싱 성공한 경우만 엄격하게 적용
            if today_only and date_parsed and pub_date < cutoff_date:
                continue

            items.append({
                "source":    source,
                "src_class": src_class,
                "title":     title,
                "url":       link,
                "pubtime":   pub_iso,
                "pub_date":  pub_date,
            })
        return items
    except Exception as e:
        print(f"  ⚠️  {source} RSS 실패: {e}")
        return []

# ── Claude 요약 ──────────────────────────────────────────────
def get_summary_3(title):
    """뉴스 3줄 요약"""
    text = claude(
        f"뉴스 제목: '{title}'\n"
        "핵심 내용을 반드시 3줄로 요약해줘.\n"
        "규칙: 각 줄 앞에 어떤 기호도 없이 내용만, 한 줄 40자 이내, 수치·사실 중심, 한국어, 딱 3줄만 출력",
        max_tokens=150
    )
    if not text: return None
    lines = [l.strip().lstrip('·-•*①②③1234567890.) ').strip()
             for l in text.split('\n') if l.strip()]
    result = [l for l in lines if len(l) > 4][:3]
    return result if len(result) >= 2 else None

def get_column_summary(title):
    """칼럼 요약 (단락 형식)"""
    text = claude(
        f"칼럼/사설 제목: '{title}'\n"
        "이 칼럼의 핵심 주장과 근거를 3~4문장으로 요약해줘.\n"
        "규칙: 자연스러운 문장으로, 기호 없이, 한국어, 전체 150자 이내",
        max_tokens=200
    )
    if not text: return "요약 준비 중..."
    return text.strip()

def translate_and_summarize(title, source):
    """영문 제목 → 한국어 번역 + 3줄 요약"""
    text = claude(
        f"해외 뉴스 제목: '{title}'\n"
        f"출처: {source}\n"
        "1. 이 제목을 자연스러운 한국어로 번역해줘 (원문 느낌 살려서, 30자 이내)\n"
        "2. 내용을 3줄로 요약해줘 (각 줄 40자 이내, 한국 독자 관점에서)\n"
        "출력 형식 (다른 텍스트 없이):\n"
        "번역: [한국어 제목]\n"
        "요약1: [첫째줄]\n"
        "요약2: [둘째줄]\n"
        "요약3: [셋째줄]",
        max_tokens=200
    )
    if not text:
        return title, None
    lines = text.strip().split('\n')
    ko_title = title
    bullets  = []
    for line in lines:
        line = line.strip()
        if line.startswith('번역:'):
            ko_title = line[3:].strip()
        elif line.startswith('요약'):
            content = re.sub(r'^요약\d+:\s*', '', line).strip()
            if content:
                bullets.append(content)
    return ko_title, bullets if len(bullets) >= 2 else None

# ════════════════════════════════════════════════════════════
# STEP 1: 뉴스 수집 + 3줄 요약
# ════════════════════════════════════════════════════════════
print("\n📡 [1/4] 뉴스 수집 + 3줄 요약...")
section_news   = {}
all_titles     = []
latest_pubtime = now_kst
global_seen    = set()

def dedup_key(title):
    """중복 판단용 키: 특수문자 제거 후 앞 20자"""
    return re.sub(r'[\s\W]+', '', title)[:20]

def update_latest(pubtime_str):
    global latest_pubtime
    try:
        pt = datetime.fromisoformat(pubtime_str)
        if pt.tzinfo is None: pt = pt.replace(tzinfo=KST)
        if pt.astimezone(KST) > latest_pubtime:
            latest_pubtime = pt.astimezone(KST)
    except Exception:
        pass

for section in NEWS_SOURCES:
    seen = set()
    news = []
    sources = list(ALL_NEWS_SOURCES[section])  # 원본 순서 유지 (셔플 없이)
    src_names = [s[0] for s in sources]
    print(f"  [{section}] 소스 {len(sources)}개: {', '.join(src_names)}")

    # ── 단계1: 각 신문사에서 오늘/어제 기사 1개씩 수집 ──────────────
    for src_name, src_cls, src_url in sources:
        got = False
        # 오늘 기사 먼저, 없으면 날짜 무관 최신 기사
        for try_today in [True, False]:
            items = fetch_rss(src_name, src_cls, src_url,
                              max_items=10, today_only=try_today)
            for item in items:
                k = dedup_key(item["title"])
                if k not in seen and k not in global_seen:
                    seen.add(k); global_seen.add(k)
                    print(f"    ✅ [{src_name}] {item['title'][:35]}...")
                    item["bullets"] = get_summary_3(item["title"])
                    news.append(item)
                    all_titles.append(item["title"])
                    update_latest(item["pubtime"])
                    time.sleep(0.25)
                    got = True
                    break
            if got:
                break
        if not got:
            print(f"    ⚠️  [{src_name}] 기사 없음 (RSS 접근 실패 가능)")

    section_news[section] = news
    srcs = ','.join(dict.fromkeys(i['source'] for i in news))
    print(f"  ✅ {section}: {len(news)}건 [{srcs}]")

# ════════════════════════════════════════════════════════════
# STEP 1b: 해외 뉴스 수집 + 한국어 번역 요약
# ════════════════════════════════════════════════════════════
print("\n🌐 [1b] 해외 뉴스 수집 + 번역...")
intl_news  = []
seen_intl  = set()

def add_intl(item):
    """intl_news에 추가 (중복 체크 포함)"""
    key = dedup_key(item["title"])
    if key in seen_intl:
        return False
    seen_intl.add(key)
    ko_title, bullets = translate_and_summarize(item["title"], item["source"])
    item["ko_title"]   = ko_title
    item["orig_title"] = item["title"]
    item["bullets"]    = bullets
    item["hist_key"]   = INTL_HIST_KEYS.get(item["source"], "iran_war")
    intl_news.append(item)
    # 최신 시각 갱신
    global latest_pubtime
    try:
        pt = datetime.fromisoformat(item["pubtime"])
        if pt.tzinfo is None:
            pt = pt.replace(tzinfo=KST)
        pt_kst = pt.astimezone(KST)
        if pt_kst > latest_pubtime:
            latest_pubtime = pt_kst
    except Exception:
        pass
    time.sleep(0.4)
    return True

# 1) 지역 보장: 일본·중국·유럽 각 1개 반드시 포함
for region, region_sources in INTL_REGION_SOURCES.items():
    added = False
    for source, src_class, url in region_sources:
        if added:
            break
        for today_only in [True, False]:   # 오늘 기사 우선, 없으면 최신
            items = fetch_rss(source, src_class, url, max_items=5, today_only=today_only)
            if items:
                item = items[0]
                item["source"]    = source
                item["src_class"] = src_class
                print(f"  🌐 [{region}:{source}] {item['title'][:40]}...")
                if add_intl(item):
                    added = True
                    break
        if added:
            break
    if not added:
        print(f"  ⚠️  {region} 지역 기사 수집 실패")

# 2) 나머지 글로벌 소스로 보충 (최대 7개까지)
for source, src_class, url in INTL_SOURCES:
    if len(intl_news) >= 7:
        break
    for today_only in [True, False]:
        items = fetch_rss(source, src_class, url, max_items=3, today_only=today_only)
        for item in items:
            if len(intl_news) >= 7:
                break
            item["source"]    = source
            item["src_class"] = src_class
            print(f"  🌐 [{source}] {item['title'][:40]}...")
            add_intl(item)
        if len(intl_news) >= 7:
            break

print(f"  ✅ 해외 뉴스 {len(intl_news)}건 (일본·중국·유럽 포함)")

print("\n✍️  [2/4] 칼럼 수집...")
columns = []
seen_col = set()
# 국내 칼럼: 각 신문사에서 반드시 1개씩 수집 (8개 신문사)
for source, src_class, url in COLUMN_SOURCES:
    got = False
    items = fetch_rss(source, src_class, url, max_items=8, today_only=False)
    print(f"  [{source}] RSS {len(items)}건")
    for item in items:
        key = dedup_key(item["title"])
        if key not in seen_col:
            seen_col.add(key)
            print(f"  📝 [{source}] {item['title'][:35]}...")
            item["summary"] = get_column_summary(item["title"])
            item["is_intl"] = False
            columns.append(item)
            time.sleep(0.3)
            got = True
            break
    if not got:
        print(f"  ⚠️  [{source}] 칼럼 없음")

# 해외 칼럼: 랜덤 2곳 번역 후 국내 칼럼 사이에 삽입
intl_col_picks = _random.sample(INTL_COLUMN_SOURCES, min(2, len(INTL_COLUMN_SOURCES)))
intl_cols = []
for source, src_class, url in intl_col_picks:
    items = fetch_rss(source, src_class, url, max_items=8, today_only=False)
    print(f"  🌐 [{source}] RSS {len(items)}건 수신")
    if not items:
        print(f"  ⚠️  [{source}] RSS 실패, 다음 소스 시도...")
        # 실패 시 다른 소스로 대체
        for alt_src, alt_cls, alt_url in INTL_COLUMN_SOURCES:
            if alt_src == source: continue
            items = fetch_rss(alt_src, alt_cls, alt_url, max_items=8, today_only=False)
            if items:
                source, src_class, url = alt_src, alt_cls, alt_url
                print(f"  🔄 [{source}] 대체 성공: {len(items)}건")
                break
    for item in items:
        key = dedup_key(item["title"])
        if key not in seen_col:
            seen_col.add(key)
            print(f"  🌐 [{source}] 번역: {item['title'][:40]}...")
            ko_title, bullets = translate_and_summarize(item["title"], source)
            item["ko_title"]   = ko_title or item["title"]
            item["orig_title"] = item["title"]
            item["title"]      = ko_title if ko_title else item["title"]
            item["summary"]    = "\n".join(bullets) if bullets else "번역 준비 중..."
            item["is_intl"]    = True
            item["src_class"]  = src_class
            item["source"]     = source
            intl_cols.append(item)
            time.sleep(0.5)
            break

# 해외 칼럼을 국내 칼럼 사이에 삽입 (3번째, 6번째 위치)
for i, ic in enumerate(intl_cols):
    pos = min(3 + i*3, len(columns))
    columns.insert(pos, ic)

print(f"  ✅ 칼럼 총 {len(columns)}건 — 국내 {len(columns)-len(intl_cols)}건 + 해외번역 {len(intl_cols)}건")

# ════════════════════════════════════════════════════════════
# STEP 3: 사이드바
# ════════════════════════════════════════════════════════════
print("\n📊 [3/4] 사이드바 생성...")
hl_items = []
for source, src_class, url in HEADLINE_SOURCES:
    items = fetch_rss(source, src_class, url, max_items=1)
    if items:
        hl_items.append({
            "src": source, "cls": src_class,
            "title": items[0]["title"], "url": items[0]["url"]
        })

titles_str = "\n".join(f"- {t}" for t in all_titles[:20])
sidebar_data = claude_json(f"""오늘({today_str}) 뉴스 제목들:
{titles_str}

위 뉴스를 분석해서 JSON만 출력 (다른 텍스트 없이):
{{
  "핵심수치": [
    {{"label":"5자이내 항목명","value":"숫자+단위(예:$82,1438원,5610)","desc":"8자이내 설명","up":true}},
    {{"label":"5자이내 항목명","value":"숫자+단위","desc":"8자이내 설명","up":false}},
    {{"label":"5자이내 항목명","value":"숫자+단위","desc":"8자이내 설명","up":true}},
    {{"label":"5자이내 항목명","value":"숫자+단위","desc":"8자이내 설명","up":false}},
    {{"label":"5자이내 항목명","value":"숫자+단위","desc":"8자이내 설명","up":true}},
    {{"label":"5자이내 항목명","value":"숫자+단위","desc":"8자이내 설명","up":false}}
  ],
  "관전포인트": [
    {{"title":"오늘 뉴스를 어떤 관점으로 볼지 알려주는 질문형 제목 (예: '유가가 다시 오를까?') 20자이내","now":"뉴스 독자가 알아야 할 현재 핵심 상황 30자이내","watch":"핵심 쟁점·대립구도 — 어느 쪽을 주목할지 30자이내","next":"이 흐름이 어디로 향할지, 무엇을 확인해야 할지 30자이내"}},
    {{"title":"두번째 핵심 질문 20자이내","now":"현재 상황 30자이내","watch":"핵심 쟁점 30자이내","next":"전망 30자이내"}},
    {{"title":"세번째 핵심 질문 20자이내","now":"현재 상황 30자이내","watch":"핵심 쟁점 30자이내","next":"전망 30자이내"}},
    {{"title":"네번째 핵심 질문 20자이내","now":"현재 상황 30자이내","watch":"핵심 쟁점 30자이내","next":"전망 30자이내"}}
  ],
  "주요이슈": ["22자이내 이슈1","22자이내 이슈2","22자이내 이슈3"],
  "칼럼논점": "오늘 칼럼들의 핵심 논점 한 문장 40자이내",
  "오늘의용어": [
    {{"word":"오늘 뉴스에 등장한 어려운 경제·금융 용어","en":"영어명(있으면)","desc":"일반인도 이해할 쉬운 설명 50자이내"}},
    {{"word":"두번째 용어","en":"영어명","desc":"쉬운 설명 50자이내"}},
    {{"word":"세번째 용어","en":"영어명","desc":"쉬운 설명 50자이내"}},
    {{"word":"네번째 용어","en":"영어명","desc":"쉬운 설명 50자이내"}}
  ]
}}
중요: 오늘의 용어는 반드시 오늘 뉴스에 실제 등장한 단어여야 하며, 중학생도 이해할 수 있게 쉽게 설명할 것.""", max_tokens=800)

if not sidebar_data:
    sidebar_data = {
        "핵심수치": [{"label":"업데이트","value":"--","desc":"대기중","up":True}]*3,
        "관전포인트": [{"title":"업데이트 대기","now":"","watch":"","next":""}],
        "오늘의용어": [{"word":"업데이트 대기","en":"","desc":"자동 갱신 예정"}],
        "칼럼논점": "업데이트 대기 중"
    }
    print("  ⚠️  기본값 사용")
else:
    print("  ✅ 사이드바 생성 완료")

# ════════════════════════════════════════════════════════════
# STEP 4: HTML 빌드
# ════════════════════════════════════════════════════════════
print("\n🔨 [4/4] HTML 빌드...")

# ── 뉴스 카드 (최신 v4 구조) ─────────────────────────────
def make_news_card(item, card_color, hist_key):
    title   = esc(item["title"])
    url     = item["url"]
    src     = item["source"]
    sc      = item["src_class"]
    pub     = item["pubtime"]
    bullets = item.get("bullets") or []
    hist_label = HIST_LABELS.get(hist_key, hist_key)

    # 3줄 요약 li
    if bullets:
        li_html = "".join(f"<li>{esc(b)}</li>" for b in bullets[:3])
        bullets_html = f'<ul class="cpts">{li_html}</ul>'
    else:
        bullets_html = '<ul class="cpts"><li>요약 로딩 중...</li></ul>'

    return f'''
    <div class="card {card_color}" onclick="toggleCard(this)">
      <div class="ct"><span class="src {sc}">{src}</span><span class="ctime" data-pubtime="{pub}">🕒 --</span><span class="expand-hint">▾</span></div>
      <div class="ch">{title}</div>
      <div class="card-expand">
        {bullets_html}
        <div class="card-btns">
          <button class="btn-like" onclick="toggleLike(this,event)">🤍 좋아요</button>
          <button class="cbtn case-btn" onclick="toggleCase(this,'{hist_key}',event)">📂 과거 사례</button>
          <a class="cbtn read-btn" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗ 기사 보기</a>
        </div>
        <div class="case-panel">
          <div class="case-panel-hd"><span>📂 과거 사례 — {hist_label}</span><span class="case-panel-close" onclick="closeCase(this,event)">✕</span></div>
          <div class="case-panel-body"></div>
        </div>
      </div>
    </div>'''

news_html = "\n"
for section, items in section_news.items():
    if not items: continue
    color = SECTION_COLORS[section]
    cc    = CARD_COLORS[section]
    hk    = HIST_KEYS[section]
    news_html += f'\n    <div class="sec sec-collapsed" onclick="toggleSection(this)"><span class="sec-tag" style="background:{color}">{section}</span><div class="sec-line"></div><span class="sec-toggle">▾</span></div>\n    <div class="sec-body collapsed">\n'
    for item in items:
        news_html += make_news_card(item, cc, hk)
    news_html += '    </div>\n'
news_html += "\n"

# ── 해외 시각 카드 ────────────────────────────────────────
def make_intl_card(item):
    ko_title   = esc(item.get("ko_title", item["title"]))
    orig_title = esc(item.get("orig_title", ""))
    url        = item["url"]
    src        = item["source"]
    pub        = item["pubtime"]
    bullets    = item.get("bullets") or []
    hist_key   = item.get("hist_key", "iran_war")
    hist_label = HIST_LABELS.get(hist_key, hist_key)

    if bullets:
        li_html = "".join(f"<li>{esc(b)}</li>" for b in bullets[:3])
        bullets_html = f'<ul class="cpts">{li_html}</ul>'
    else:
        bullets_html = '<ul class="cpts"><li>번역 로딩 중...</li></ul>'

    orig_html = f'<div class="ch-orig">{orig_title}</div>' if orig_title else ''

    return f'''
    <div class="card dk" onclick="toggleCard(this)">
      <div class="ct"><span class="src intl">{src}</span><span class="ctime" data-pubtime="{pub}">🕒 --</span><span class="expand-hint">▾</span></div>
      <div class="ch">{ko_title}</div>
      <div class="card-expand">
        {orig_html}
        {bullets_html}
        <div class="card-btns">
          <button class="btn-like" onclick="toggleLike(this,event)">🤍 좋아요</button>
          <button class="cbtn case-btn" onclick="toggleCase(this,'{hist_key}',event)">📂 과거 사례</button>
          <a class="cbtn read-btn" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗ 기사 보기</a>
        </div>
        <div class="case-panel">
          <div class="case-panel-hd"><span>📂 과거 사례 — {hist_label}</span><span class="case-panel-close" onclick="closeCase(this,event)">✕</span></div>
          <div class="case-panel-body"></div>
        </div>
      </div>
    </div>'''

intl_html = '\n    <div class="sec sec-collapsed" onclick="toggleSection(this)"><span class="sec-tag intl">해 외 시 각</span><div class="sec-line"></div><span class="sec-toggle">▾</span></div>\n    <div class="sec-body collapsed">\n'
for item in intl_news:
    intl_html += make_intl_card(item)
intl_html += "    </div>\n"
col_colors = ["navy", "red", "gold", "dk"]

col_html = '\n    <div class="sec"><span class="sec-tag" style="background:var(--navy)">오늘의 추천 칼럼</span><div class="sec-line"></div></div>\n'
for i, item in enumerate(columns):
    cc    = col_colors[i % len(col_colors)]
    title = esc(item["title"])
    url   = item["url"]
    src   = item["source"]
    sc    = item["src_class"]
    pub   = item["pubtime"]
    is_intl = item.get("is_intl", False)
    try:
        dt = datetime.fromisoformat(pub)
        date_str = dt.astimezone(KST).strftime("%Y.%m.%d")
    except:
        date_str = now_ymd
    summary = esc(item.get("summary", "요약 준비 중..."))
    orig_html = f'<div class="ch-orig">{esc(item["orig_title"])}</div>' if is_intl and item.get("orig_title") else ''
    col_html += f'''
    <div class="col-card {cc}">
      <div class="col-top">
        <span class="col-paper src {sc}">{src}</span>
        {'<span style="font-size:9px;background:#3d2e5e;color:#fff;padding:1px 5px;border-radius:2px;margin-left:4px">해외</span>' if is_intl else ''}
        <span class="col-date">{date_str}</span>
      </div>
      <div class="col-title"><a href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="color:inherit">{title}</a></div>
      {orig_html}
      <div class="col-body">{summary}</div>
    </div>'''
col_html += "\n"

# ── 사이드바 HTML ─────────────────────────────────────────
def build_right(data, hl_list):
    nums   = data.get("핵심수치", [])
    pts    = data.get("관전포인트", [])
    issues = data.get("주요이슈", [])

    # 핵심수치 (최대 6개, 2열 배치)
    stats = ""
    for n in nums[:6]:
        clr = "r" if n.get("up", True) else "b"
        stats += f'<div class="mstat"><div class="mnum {clr}">{esc(str(n["value"]))}</div><div class="mlbl">{esc(n["label"])}<br><small style="font-size:9px">{esc(n["desc"])}</small></div></div>'

    # 관전포인트 — 현황/쟁점/향후 3단 구조
    icons = ['①','②','③','④']
    pts_html = ""
    for i, p in enumerate(pts[:4]):
        now_txt   = esc(p.get("now",   p.get("sub", "")))
        watch_txt = esc(p.get("watch", ""))
        next_txt  = esc(p.get("next",  ""))
        pts_html += f'''<div class="pt-card">
          <div class="pt-hd"><span class="pt-num">{icons[i]}</span><span class="pt-title">{esc(p["title"])}</span></div>
          <div class="pt-body">
            {f'<div class="pt-row"><span class="pt-label now">현황</span><span class="pt-text">{now_txt}</span></div>' if now_txt else ""}
            {f'<div class="pt-row"><span class="pt-label watch">쟁점</span><span class="pt-text">{watch_txt}</span></div>' if watch_txt else ""}
            {f'<div class="pt-row"><span class="pt-label next">전망</span><span class="pt-text">{next_txt}</span></div>' if next_txt else ""}
          </div>
        </div>'''

    # 오늘의 용어
    terms = data.get("오늘의용어", [])
    term_html = ""
    for t in terms[:4]:
        en = f'<span class="term-en">{esc(t.get("en",""))}</span>' if t.get("en") else ""
        term_html += f'''<div class="term-item">
          <div class="term-word">{esc(t["word"])} {en}</div>
          <div class="term-desc">{esc(t["desc"])}</div>
        </div>'''

    return f"""
    <div class="sbox sbox-toggle" onclick="toggleSbox(this)">
      <div class="sbox-hd"><span class="dot" style="background:var(--red)"></span>오늘의 핵심 수치<span class="sbox-arr">▾</span></div>
      <div class="sbox-body"><div class="mini-stats">{stats}</div></div>
    </div>
    <div class="sbox sbox-toggle" onclick="toggleSbox(this)">
      <div class="sbox-hd"><span class="dot" style="background:var(--gold)"></span>오늘의 관전 포인트<span class="sbox-arr">▾</span></div>
      <div class="sbox-body"><div class="pt-wrap">{pts_html}</div></div>
    </div>
    <div class="sbox sbox-toggle" onclick="toggleSbox(this)">
      <div class="sbox-hd"><span class="dot" style="background:var(--accent)"></span>오늘의 용어<span class="sbox-arr">▾</span></div>
      <div class="sbox-body"><div class="term-list">{term_html if term_html else '<div class="term-item"><div class="term-desc">업데이트 준비 중</div></div>'}</div></div>
    </div>
"""

right_html = build_right(sidebar_data, hl_items)

# 칼럼 우측
논점 = esc(sidebar_data.get("칼럼논점", ""))
col_right_html = f"""
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--navy)"></span>오늘의 논점</div>
      <div class="issue-list"><div class="issue-item" style="line-height:1.6">{논점}</div></div>
    </div>
"""

# ── 칼럼 아카이브 사이드바 ─────────────────────────────────
def build_col_archive(prev_columns_by_date):
    if not prev_columns_by_date:
        return '<div style="padding:10px 12px;font-size:11px;color:var(--ink3)">칼럼이 쌓이면 날짜별로 표시됩니다</div>'
    html_out = '<div class="col-archive-list">'
    arr = "\u25be"
    for date_str, items in sorted(prev_columns_by_date.items(), reverse=True)[:7]:
        try:
            dt = datetime.fromisoformat(date_str)
            d_num = dt.day
            d_sub = dt.strftime("%m월 ") + ['일','월','화','수','목','금','토'][dt.weekday()]
        except:
            d_num = date_str[-2:]
            d_sub = date_str
        date_id = f"cola_{date_str.replace('-','')}"
        html_out += (
            f'<div class="col-archive-date" onclick="toggleColArchive(this)">' +
            f'<span class="col-archive-datenum">{d_num}</span>' +
            f'<span class="col-archive-datesub">{d_sub}</span>' +
            f'<span class="col-archive-cnt">{arr} {len(items)}건</span>' +
            f'</div><div class="col-archive-items" id="{date_id}">'
        )
        for col in items:
            src = esc(col.get('source',''))
            sc  = col.get('src_class','')
            ttl = esc(col.get('title',''))
            url = col.get('url','#')
            html_out += (
                f'<div class="col-archive-item">' +
                f'<a href="{url}" target="_blank" rel="noopener">' +
                f'<span class="src {sc}" style="font-size:9px">{src}</span>{ttl}</a></div>'
            )
        html_out += '</div>'
    html_out += '</div>'
    return html_out

# ── 지난뉴스 아카이브 ─────────────────────────────────────
def build_archive_entry(section_news_data, date_d, date_sub, date_id):
    all_titles_today = []
    cards = ""
    for section, items in section_news_data.items():
        color = SECTION_COLORS[section]
        cc    = CARD_COLORS[section]
        hk    = HIST_KEYS[section]
        for item in items[:3]:
            all_titles_today.append(item["title"])
            title    = esc(item["title"])
            url      = item["url"]
            src_name = item.get("source", "")
            src_cls  = item.get("src_class", "")
            bhtml   = ""
            if bullets:
                # 아카이브: 헤드라인 + 신문사만, 요약 없음
            cards += f'''<div class="card {cc}" style="margin-top:4px;cursor:default">
              <div class="ct"><span class="src" style="background:{color};font-size:8px;padding:2px 6px;color:#fff;border-radius:2px">{section}</span><span class="src {src_cls}" style="margin-left:4px">{src_name}</span></div>
              <div class="ch" style="font-size:12.5px"><a href="{url}" class="ch-link" target="_blank" style="color:inherit">{title}</a></div>
            </div>'''
    keywords = "; ".join(t[:12] for t in all_titles_today[:3])
    total = sum(len(v) for v in section_news_data.values())
    return f"""
  <div>
    <div class="arch-row" onclick="tog('{date_id}')">
      <div class="aday"><div class="adaynum">{date_d}</div><div class="adaysub">{date_sub}</div></div>
      <div class="acnt">▾ {total}건</div>
    </div>
    <div class="arch-detail open" id="{date_id}">{cards}</div>
  </div>"""

archive_entry = build_archive_entry(
    section_news, today_day, today_sub,
    f"d{today_day}_{now_kst.strftime('%H')}"
)
archive_html = f'<div class="arch-list">\n{archive_entry}\n</div>'

# ════════════════════════════════════════════════════════════
# index.html 교체
# ════════════════════════════════════════════════════════════
# 최신 기사 발행 시각 기준 업데이트 표시 문자열 계산
update_display = make_update_display(latest_pubtime)
print(f"  📅 최신 기사 시각: {latest_pubtime.strftime('%H:%M')} → 표시: {update_display}")

INDEX_PATH = "index.html"
if not os.path.exists(INDEX_PATH):
    print("❌ index.html 없음")
    sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

# 메타 업데이트 시각
html = re.sub(r'<meta name="last-updated"[^>]*>',
              f'<meta name="last-updated" content="{now_iso}">', html)

# hdr-update span에 최신 기사 기준 시각 주입
html = re.sub(
    r'(<span[^>]+id="hdr-update"[^>]*>)[^<]*(</span>)',
    rf'\g<1>{update_display}\g<2>',
    html
)

# 헤더 날짜/업데이트 표시 (id 기반으로 JS가 처리하므로 그대로)
def replace_block(html, s, e, content):
    if s in html and e in html:
        return re.sub(
            re.escape(s) + r'.*?' + re.escape(e),
            f"{s}\n{content}\n{e}",
            html, flags=re.DOTALL
        )
    print(f"  ⚠️  마커 없음: {s[:40]}")
    return html

html = replace_block(html, '<!-- AUTO_NEWS_START -->',     '<!-- AUTO_NEWS_END -->',     news_html)
html = replace_block(html, '<!-- AUTO_INTL_START -->',     '<!-- AUTO_INTL_END -->',     intl_html)
html = replace_block(html, '<!-- AUTO_COLUMN_START -->',   '<!-- AUTO_COLUMN_END -->',   col_html)
html = replace_block(html, '<!-- AUTO_RIGHT_START -->',    '<!-- AUTO_RIGHT_END -->',    right_html)
html = replace_block(html, '<!-- AUTO_COL_RIGHT_START -->', '<!-- AUTO_COL_RIGHT_END -->', col_right_html)

# 칼럼 아카이브 사이드바 업데이트
if '<!-- AUTO_COL_ARCHIVE_START -->' in html:
    # 기존 아카이브에서 날짜별 칼럼 데이터 추출 (간단히 오늘 칼럼만 추가)
    col_archive_html = build_col_archive({})  # 첫 실행 시 빈 값
    # 오늘 칼럼을 아카이브에 추가하는 누적 로직은 뉴스 아카이브와 동일하게 처리
    html = replace_block(html, '<!-- AUTO_COL_ARCHIVE_START -->', '<!-- AUTO_COL_ARCHIVE_END -->', '\n' + col_archive_html + '\n')

# 아카이브 누적 (오늘 데이터 맨 앞에 추가)
if '<!-- AUTO_ARCHIVE_START -->' in html and '<!-- AUTO_ARCHIVE_END -->' in html:
    arch_start = html.find('<!-- AUTO_ARCHIVE_START -->') + len('<!-- AUTO_ARCHIVE_START -->')
    arch_end   = html.find('<!-- AUTO_ARCHIVE_END -->')
    existing   = html[arch_start:arch_end].strip()
    today_id   = f"d{today_day}_{now_kst.strftime('%H')}"
    if today_id not in existing:
        inner = re.sub(r'^<div class="arch-list">\s*', '', existing, count=1)
        inner = re.sub(r'\s*</div>\s*$', '', inner)
        new_arch = f'<div class="arch-list">\n{archive_entry}\n{inner}\n</div>'
        html = replace_block(html, '<!-- AUTO_ARCHIVE_START -->', '<!-- AUTO_ARCHIVE_END -->', new_arch)
        print("  ✅ 아카이브 항목 추가")
    else:
        html = replace_block(html, '<!-- AUTO_ARCHIVE_START -->', '<!-- AUTO_ARCHIVE_END -->', archive_html)
        print("  ✅ 아카이브 갱신")

with open(INDEX_PATH, "w", encoding="utf-8") as f:
    f.write(html)

print(f"\n💾 완료! [{now_display}]")
print(f"  뉴스 {sum(len(v) for v in section_news.values())}건 | 칼럼 {len(columns)}건")
