#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
세줄뉴스 자동 업데이트 v5
- 섹션별 전용 RSS로 경제/기업/정책/국제 분리
- AI 섹션 재분류 + 부적절 기사 필터링
- 전체 중복 제거 (섹션간 같은 뉴스 절대 안 나옴)
- 해외뉴스 신문사별 1개씩 필수
- 칼럼 opinion RSS 전용 (뉴스기사 유입 차단)
- 국가 배지 (🇺🇸 미국, 🇬🇧 영국, 🇫🇷 프랑스 등)
"""

import os, re, sys, time, json, random as _random
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

def make_update_display(latest_dt):
    label = "오전" if latest_dt.hour < 12 else "오후"
    return f"기사 기준 {label} {latest_dt.strftime('%-H:%M')}"

print(f"[{now_display}] 세줄뉴스 v5 업데이트 시작")
print(f"Claude 키: {'✅ 있음' if CLAUDE_KEY else '⚠️  없음 (요약 생략)'}")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def esc(s):
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

# ════════════════════════════════════════════════════════════
# RSS 소스 정의
# ════════════════════════════════════════════════════════════

# ── 섹션별 전용 RSS (1순위) ──────────────────────────────────
# 각 섹션에 맞는 전용 카테고리 RSS를 먼저 시도
SECTION_RSS = {
    "경제 · 금융": {
        "조선일보": ["https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml",
                     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"],
        "중앙일보": ["https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
                     "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko"],
        "동아일보": ["https://rss.donga.com/economy.xml",
                     "https://rss.donga.com/total.xml"],
        "한국경제": ["https://www.hankyung.com/feed/economy"],
        "매일경제": ["https://www.mk.co.kr/rss/30000001/"],
        "한겨레":   ["https://www.hani.co.kr/rss/economy/",
                     "https://www.hani.co.kr/rss/economy/finance/"],
        "경향신문": ["https://www.khan.co.kr/rss/rssdata/kh_economy.xml"],
        "연합뉴스": ["https://www.yna.co.kr/rss/economy.xml"],
    },
    "기 업": {
        "조선일보": ["https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml",
                     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"],
        "중앙일보": ["https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
                     "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko"],
        "동아일보": ["https://rss.donga.com/economy.xml",
                     "https://rss.donga.com/total.xml"],
        "한국경제": ["https://www.hankyung.com/feed/economy"],
        "매일경제": ["https://www.mk.co.kr/rss/30200030/",
                     "https://www.mk.co.kr/rss/30000001/"],
        "한겨레":   ["https://www.hani.co.kr/rss/economy/"],
        "경향신문": ["https://www.khan.co.kr/rss/rssdata/kh_economy.xml"],
        "연합뉴스": ["https://www.yna.co.kr/rss/economy.xml"],
    },
    "정책 · 사회": {
        "조선일보": ["https://www.chosun.com/arc/outboundfeeds/rss/category/politics/?outputType=xml",
                     "https://www.chosun.com/arc/outboundfeeds/rss/category/national/?outputType=xml",
                     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"],
        "중앙일보": ["https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
                     "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko"],
        "동아일보": ["https://rss.donga.com/politics.xml",
                     "https://rss.donga.com/national.xml",
                     "https://rss.donga.com/total.xml"],
        "한국경제": ["https://www.hankyung.com/feed/politics",
                     "https://www.hankyung.com/feed/economy"],
        "매일경제": ["https://www.mk.co.kr/rss/30200001/",
                     "https://www.mk.co.kr/rss/30000001/"],
        "한겨레":   ["https://www.hani.co.kr/rss/politics/",
                     "https://www.hani.co.kr/rss/society/"],
        "경향신문": ["https://www.khan.co.kr/rss/rssdata/kh_politics.xml"],
        "연합뉴스": ["https://www.yna.co.kr/rss/politics.xml"],
    },
    "국 제": {
        "조선일보": ["https://www.chosun.com/arc/outboundfeeds/rss/category/international/?outputType=xml",
                     "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"],
        "중앙일보": ["https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
                     "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko"],
        "동아일보": ["https://rss.donga.com/international.xml",
                     "https://rss.donga.com/total.xml"],
        "한국경제": ["https://www.hankyung.com/feed/international",
                     "https://www.hankyung.com/feed/economy"],
        "매일경제": ["https://www.mk.co.kr/rss/30300001/",
                     "https://www.mk.co.kr/rss/30000001/"],
        "한겨레":   ["https://www.hani.co.kr/rss/international/"],
        "경향신문": ["https://www.khan.co.kr/rss/rssdata/kh_world.xml"],
        "연합뉴스": ["https://www.yna.co.kr/rss/international.xml"],
    },
}

# ── 신문사별 폴백 RSS ────────────────────────────────────────
RSS_FALLBACKS = {
    "조선일보": ("c", [
        "https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml",
        "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/?outputType=xml",
    ]),
    "중앙일보": ("c", [
        "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/search?q=site:joongang.co.kr&hl=ko&gl=KR&ceid=KR:ko",
    ]),
    "동아일보": ("c", [
        "https://rss.donga.com/total.xml",
        "https://rss.donga.com/economy.xml",
    ]),
    "한국경제": ("e", [
        "https://www.hankyung.com/feed/economy",
        "https://www.hankyung.com/feed/all",
    ]),
    "매일경제": ("e", [
        "https://www.mk.co.kr/rss/30000001/",
        "https://www.mk.co.kr/rss/40300001/",
    ]),
    "한겨레": ("p", [
        "https://www.hani.co.kr/rss/economy/",
        "https://www.hani.co.kr/rss/",
    ]),
    "경향신문": ("p", [
        "https://www.khan.co.kr/rss/rssdata/kh_economy.xml",
        "https://www.khan.co.kr/rss/rssdata/total_news.xml",
    ]),
    "연합뉴스": ("w", [
        "https://www.yna.co.kr/rss/economy.xml",
        "https://www.yna.co.kr/rss/news.xml",
    ]),
}
ALL_SOURCE_NAMES = ["조선일보","중앙일보","동아일보","한국경제","매일경제","한겨레","경향신문","연합뉴스"]
NEWS_SECTIONS    = ["경제 · 금융", "기 업", "정책 · 사회", "국 제"]

# ── 칼럼 전용 RSS (opinion만, 전체RSS 폴백 금지) ───────────────
COLUMN_SOURCES_DEF = [
    ("조선일보", "c", [
        "https://www.chosun.com/arc/outboundfeeds/rss/category/opinion/?outputType=xml",
    ]),
    ("중앙일보", "c", [
        "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
        "https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko",
    ]),
    ("동아일보", "c", [
        "https://rss.donga.com/opinion.xml",
    ]),
    ("한국경제", "e", [
        "https://www.hankyung.com/feed/opinion",
    ]),
    ("매일경제", "e", [
        "https://www.mk.co.kr/rss/30300001/",
    ]),
    ("한겨레", "p", [
        "https://www.hani.co.kr/rss/opinion/",
    ]),
    ("경향신문", "p", [
        "https://www.khan.co.kr/rss/rssdata/kh_opinion.xml",
    ]),
    # 연합뉴스 제외 (칼럼/사설 없는 통신사)
]

# ── 해외뉴스 소스 ─────────────────────────────────────────────
INTL_SOURCES = [
    ("블룸버그",      "intl", "https://feeds.bloomberg.com/markets/news.rss"),
    ("파이낸셜타임스","intl", "https://www.ft.com/rss/home"),
    ("월스트리트저널","intl", "https://feeds.a.dj.com/rss/RSSWorldNews.xml"),
    ("뉴욕타임스",   "intl",  "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("가디언",       "intl",  "https://www.theguardian.com/world/rss"),
    ("BBC비즈니스",  "intl",  "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("로이터",       "intl",  "https://feeds.reuters.com/reuters/businessNews"),
]

INTL_REGION_SOURCES = {
    "일본": [
        ("재팬타임스","intl","https://feeds.japantimes.co.jp/japantimes/business"),
        ("닛케이아시아","intl","https://asia.nikkei.com/rss/feed/nar"),
    ],
    "중국": [
        ("SCMP",     "intl","https://www.scmp.com/rss/91/feed"),
        ("신화통신", "intl","http://www.xinhuanet.com/english/rss/chineseeconomyrss.xml"),
    ],
    "유럽": [
        ("가디언",          "intl","https://www.theguardian.com/world/rss"),        # 영국
        ("파이낸셜타임스",  "intl","https://www.ft.com/rss/home"),                  # 영국
        ("르몽드",          "intl","https://www.lemonde.fr/economie/rss_full.xml"), # 프랑스
    ],
}

# ── 해외 칼럼 소스 ────────────────────────────────────────────
INTL_COLUMN_SOURCES = [
    ("월스트리트저널","intl","https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml"),
    ("뉴욕타임스",   "intl","https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("가디언",       "intl","https://www.theguardian.com/business/rss"),      # 영국
    ("BBC비즈니스",  "intl","https://feeds.bbci.co.uk/news/business/rss.xml"), # 영국
    ("로이터",       "intl","https://feeds.reuters.com/reuters/businessNews"),
    ("르몽드",       "intl","https://www.lemonde.fr/economie/rss_full.xml"),  # 프랑스
]

# ── 신문사→국가 매핑 ─────────────────────────────────────────
INTL_COUNTRY = {
    "블룸버그":       "미국",
    "파이낸셜타임스": "영국",
    "월스트리트저널": "미국",
    "뉴욕타임스":     "미국",
    "가디언":         "영국",
    "BBC비즈니스":    "영국",
    "로이터":         "영국",
    "재팬타임스":     "일본",
    "닛케이아시아":   "일본",
    "SCMP":           "홍콩",
    "신화통신":       "중국",
    "르몽드":         "프랑스",
    "니혼게이자이신문": "일본",
}

# ── 헤드라인 소스 (사이드바용) ────────────────────────────────
HEADLINE_SOURCES = [
    ("조선","c","https://www.chosun.com/arc/outboundfeeds/rss/?outputType=xml"),
    ("중앙","c","https://news.google.com/rss/publications/CAAqBwgKMLe3nQswsvKfAw?hl=ko&gl=KR&ceid=KR:ko"),
    ("동아","c","https://rss.donga.com/total.xml"),
    ("매경","e","https://www.mk.co.kr/rss/30000001/"),
    ("한경","e","https://www.hankyung.com/feed/economy"),
    ("한겨레","p","https://www.hani.co.kr/rss/"),
    ("경향","p","https://www.khan.co.kr/rss/rssdata/kh_politics.xml"),
    ("연합","w","https://www.yna.co.kr/rss/economy.xml"),
]

INTL_HIST_KEYS = {
    "블룸버그":       "iran_war",
    "파이낸셜타임스": "us_tariff",
    "월스트리트저널": "samsung_buyback",
    "뉴욕타임스":     "iran_war",
    "가디언":         "iran_war",
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

# ── 섹션 키워드 (AI 분류 보조) ────────────────────────────────
SECTION_KEYWORDS = {
    "경제 · 금융": [
        "금리","환율","코스피","코스닥","주가","증시","원달러","달러","유가","금값",
        "CPI","물가","GDP","경기","수출","수입","무역수지","경상수지","인플레","디플레",
        "기준금리","채권","ETF","펀드","부동산","대출","금융","은행","증권","보험",
        "한국은행","기재부","금통위","FOMC","Fed","연준"
    ],
    "기 업": [
        "삼성","SK","현대","LG","롯데","포스코","카카오","네이버","쿠팡","배민",
        "기업","회사","실적","매출","영업이익","당기순이익","주주","배당","자사주",
        "인수합병","M&A","IPO","상장","스타트업","CEO","대표이사","임원",
        "반도체","배터리","전기차","바이오","AI칩","HBM","파운드리"
    ],
    "정책 · 사회": [
        "정부","정책","국회","법안","규제","세금","복지","노동","임금","최저임금",
        "대통령","장관","국무회의","공정위","금융위","기재부 발표",
        "사회","교육","의료","건강보험","연금","인구","저출산","고령화",
        "부동산정책","재건축","재개발","청약","LTV","DSR"
    ],
    "국 제": [
        "미국","중국","일본","유럽","EU","독일","영국","프랑스",
        "트럼프","바이든","시진핑","관세","무역전쟁","제재","외교",
        "전쟁","분쟁","OPEC","국제유가","글로벌","해외","국제","외국",
        "G7","G20","IMF","세계은행","WTO","나토","UN"
    ],
}

# ── 절대 제외 키워드 ──────────────────────────────────────────
HARD_EXCLUDE = [
    # 연예/오락 (복합어로만 — 단어 하나씩은 경제기사에 나올 수 있음)
    "아이돌 컴백","가수 데뷔","팬미팅","뮤직비디오 공개","연예인 열애",
    "배우 열애","연예인 결혼","드라마 시청률","예능 프로그램","MC딩동","고영욱",
    # 날씨 (복합어)
    "오늘의 날씨","내일 날씨","주말 날씨","기상 특보","황사 예보",
    "태풍 예보","호우 경보","대설 경보","폭염 특보","한파 특보",
    # 스포츠 결과 (경기결과성)
    "경기 결과","골프 스코어","야구 순위","축구 순위","프로야구",
    "프로축구","프로농구","NBA 경기","EPL 경기","리그 우승",
    # 기타
    "오늘의 운세","오늘 운세","별자리 운세","로또 당첨번호","복권 당첨",
]

def is_hard_excluded(title):
    """확실하게 제외할 기사 — 복합어 키워드 매칭"""
    for kw in HARD_EXCLUDE:
        if kw in title:
            return True
    return False

# ── 섹션 관련성 점수 ──────────────────────────────────────────
def section_score(title, section):
    """제목이 해당 섹션과 얼마나 관련있는지 키워드 점수"""
    score = 0
    for kw in SECTION_KEYWORDS.get(section, []):
        if kw in title:
            score += 1
    return score

# ════════════════════════════════════════════════════════════
# RSS 파싱
# ════════════════════════════════════════════════════════════
def fetch_rss(source, src_class, url, max_items=15, today_only=True):
    """RSS 피드 파싱 — 소스별 헤더·인코딩·파서 완전 대응"""
    try:
        extra = {}
        if "chosun.com" in url:
            extra["Referer"] = "https://www.chosun.com/"
            extra["Accept"]  = "application/rss+xml, application/xml, */*"
        elif "yna.co.kr" in url:
            extra["Accept"]  = "application/rss+xml, application/xml, text/xml, */*"
        elif "donga.com" in url:
            extra["Referer"] = "https://www.donga.com/"
            extra["Accept"]  = "application/rss+xml, application/xml, */*"
        elif "news.google.com" in url:
            extra["Accept"]  = "application/rss+xml, application/xml, */*"
            extra["Referer"] = "https://news.google.com/"
        req_headers = {**HEADERS, **extra}

        r = requests.get(url, headers=req_headers, timeout=15)
        r.raise_for_status()

        # EUC-KR 자동 변환 (연합뉴스)
        content = r.content
        enc = (r.apparent_encoding or "").lower().replace("-","").replace("_","")
        if enc in ("euckr","cp949","johab"):
            content = r.content.decode("euc-kr", errors="replace").encode("utf-8")

        # 파서 폴백
        soup = None
        for parser in ["lxml-xml", "xml", "lxml", "html.parser"]:
            try:
                s = BeautifulSoup(content, parser)
                if s.find("item") or s.find("entry"):
                    soup = s; break
            except Exception:
                continue
        if soup is None:
            soup = BeautifulSoup(content, "html.parser")

        items = []
        today_date  = now_kst.date()
        cutoff_date = today_date - timedelta(days=2)

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

            link = "#"
            if lk:
                href = lk.get("href", "")
                if href and href.startswith("http"):
                    link = href
                else:
                    txt = lk.get_text(strip=True)
                    if not txt:
                        sib = lk.next_sibling
                        txt = str(sib).strip() if sib else ""
                    if txt and txt.startswith("http"):
                        link = txt
            # href/text 모두 없으면 guid 시도 (조선·동아 일부 피드)
            if link == "#":
                guid = item.find("guid")
                if guid:
                    g = guid.get_text(strip=True)
                    if g.startswith("http"):
                        link = g

            pub_iso  = now_iso
            pub_date = today_date
            date_parsed = False
            if pub:
                pub_str = pub.get_text(strip=True)
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

            if today_only and date_parsed and pub_date < cutoff_date:
                continue

            # Google News: <source> 태그에서 실제 신문사명 추출
            actual_source = source
            if "news.google.com" in url:
                src_tag = item.find("source")
                if src_tag:
                    gs = src_tag.get_text(strip=True)
                    if gs: actual_source = gs

            items.append({
                "source":    actual_source,
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

# ── Claude 요약 함수 ─────────────────────────────────────────
def get_summary_3(title):
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
    text = claude(
        f"칼럼/사설 제목: '{title}'\n"
        "독자의 사고를 자극하는 방식으로 요약해줘.\n"
        "① 핵심 주장 (한 문장, 40자이내)\n"
        "② 주요 근거나 사례 (1~2문장, 80자이내)\n"
        "③ 이 칼럼이 던지는 질문 (~지 않을까? 형태, 40자이내)\n"
        "규칙: ①②③ 번호로 시작, 한국어, 전체 300~400자",
        max_tokens=500
    )
    if not text: return "요약 준비 중..."
    return text.strip()

def translate_and_summarize(title, source):
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

# ════════════════════════════════════════════════════════════
# STEP 1: 뉴스 수집
# ════════════════════════════════════════════════════════════
# 방식: 섹션별로 신문사 8개 × 섹션 전용 RSS → 1개씩 필수 수집
#       전체 중복은 global_title_seen으로 차단
#       섹션 RSS 실패 시 폴백(전체RSS) 사용
# ════════════════════════════════════════════════════════════
print("\n📡 [1/4] 뉴스 수집...")

latest_pubtime    = now_kst
all_titles        = []
global_title_seen = set()   # 섹션 간 완전 중복 방지
section_news      = {s: [] for s in NEWS_SECTIONS}

def collect_one(src_name, src_cls, url_list):
    """url_list 순서로 시도해 기사 1개 반환. 실패 시 None"""
    for url in url_list:
        for today_only in [True, False]:
            items = fetch_rss(src_name, src_cls, url, max_items=30, today_only=today_only)
            for item in items:
                k = dedup_key(item["title"])
                if k in global_title_seen:
                    continue
                if is_hard_excluded(item["title"]):
                    continue
                global_title_seen.add(k)   # 즉시 등록 → 신문사 독점 차단
                return item
    return None

# ── 1단계: 신문사별 수집 ──────────────────────────────────────
print("  [1단계] 신문사별 수집...")
raw_pool = []
for src_name in ALL_SOURCE_NAMES:
    src_cls = RSS_FALLBACKS[src_name][0]
    fb_urls = RSS_FALLBACKS[src_name][1]
    all_urls = list(dict.fromkeys(
        [u for sv in SECTION_RSS.values() for u in sv.get(src_name,[])] + fb_urls
    ))
    item = collect_one(src_name, src_cls, all_urls)
    if item:
        raw_pool.append(item)
        print(f"    ✅ [{src_name}] {item['title'][:35]}...")
    else:
        print(f"    ⚠️  [{src_name}] 실패")

# ── 2단계: Claude AI 섹션 분류 ─────────────────────────────────
print("  [2단계] AI 섹션 분류...")
def ai_classify(title):
    r = claude(
        f"뉴스 제목: '{title}'\n"
        "아래 기준으로 섹션 하나만 정확히 출력:\n"
        "경제 · 금융 = 금리·환율·주가·부동산·세금·은행·물가·GDP·무역\n"
        "기 업 = 기업실적·신제품·CEO·반도체·자동차·IT·스타트업·상장·M&A\n"
        "정책 · 사회 = 정부정책·법안·선거·정치·복지·교육·의료·범죄·사고·BTS·공연·문화\n"
        "국 제 = 미국·중국·일본·유럽·전쟁·외교·국제기구·해외",
        max_tokens=15
    )
    if not r: return "경제 · 금융"
    r = r.strip().replace(" ","")
    for s in NEWS_SECTIONS:
        if s.replace(" ","") in r: return s
    return "경제 · 금융"

for item in raw_pool:
    sec = ai_classify(item["title"])
    item["bullets"] = get_summary_3(item["title"])
    section_news[sec].append(item)
    all_titles.append(item["title"])
    update_latest(item["pubtime"])
    print(f"    → [{sec}] {item['source']}: {item['title'][:30]}")
    time.sleep(0.15)

for section in NEWS_SECTIONS:
    srcs = ", ".join(dict.fromkeys(i["source"] for i in section_news[section]))
    print(f"  ✅ {section}: {len(section_news[section])}건 [{srcs}]")

# ════════════════════════════════════════════════════════════
# STEP 1b: 해외 뉴스 수집 — 신문사별 1개씩 필수
# ════════════════════════════════════════════════════════════
print("\n🌐 [1b] 해외 뉴스 수집 + 번역...")
intl_news  = []
seen_intl  = set()

def add_intl(item):
    key = dedup_key(item["title"])
    if key in seen_intl:
        return False
    seen_intl.add(key)
    ko_title, bullets = translate_and_summarize(item["title"], item["source"])
    item["ko_title"]   = ko_title
    item["orig_title"] = item["title"]
    item["bullets"]    = bullets
    item["hist_key"]   = INTL_HIST_KEYS.get(item["source"], "iran_war")
    # 국가 정보
    item["country_name"] = INTL_COUNTRY.get(item["source"], "해외")
    intl_news.append(item)
    update_latest(item["pubtime"])
    time.sleep(0.4)
    return True

# 1) 지역 보장: 일본·중국·유럽 각 1개
for region, region_sources in INTL_REGION_SOURCES.items():
    added = False
    for source, src_class, url in region_sources:
        if added: break
        for today_only in [True, False]:
            items = fetch_rss(source, src_class, url, max_items=5, today_only=today_only)
            if items:
                item = items[0]
                item["source"]    = source
                item["src_class"] = src_class
                print(f"  🌐 [{region}:{source}] {item['title'][:40]}...")
                if add_intl(item):
                    added = True
                    break
        if added: break
    if not added:
        print(f"  ⚠️  {region} 지역 수집 실패")

# 2) 글로벌 소스 — 신문사별 1개씩 필수
for source, src_class, url in INTL_SOURCES:
    got_this = False
    for today_only in [True, False]:
        if got_this: break
        items = fetch_rss(source, src_class, url, max_items=5, today_only=today_only)
        for item in items:
            item["source"]    = source
            item["src_class"] = src_class
            print(f"  🌐 [{source}] {item['title'][:40]}...")
            if add_intl(item):
                got_this = True
                break
    if not got_this:
        print(f"  ⚠️  [{source}] 수집 실패")

print(f"  ✅ 해외 뉴스 {len(intl_news)}건")

# ════════════════════════════════════════════════════════════
# STEP 2: 칼럼 수집 — opinion RSS 전용 + 뉴스기사 필터링
# ════════════════════════════════════════════════════════════
print("\n✍️  [2/4] 칼럼 수집...")
columns  = []
seen_col = set()

# 칼럼 판별 필터
COL_REJECT_KW = [
    "아이돌 컴백","가수 데뷔","팬미팅","뮤직비디오","연예인 열애","배우 열애",
    "오늘의 날씨","내일 날씨","기상 특보","황사 예보",
    "경기 결과","야구 순위","축구 순위","프로야구","프로축구","프로농구",
    "【속보】","[속보]","【단독】","[단독]",
]
# 중앙일보처럼 opinion RSS가 없을 때 칼럼 마커 필요
COL_ACCEPT_MARKERS = ["칼럼","사설","논설","기고","시론","시평","기자수첩","데스크","에세이","논평"]

def is_valid_column(title, src_name):
    for kw in COL_REJECT_KW:
        if kw in title:
            return False
    if len(title.strip()) < 8:
        return False
    # 중앙일보: opinion RSS 불안정 → 마커 없으면 거부
    if src_name == "중앙일보":
        if not any(m in title for m in COL_ACCEPT_MARKERS):
            return False
    return True

# 국내 칼럼
for src_name, src_cls, url_list in COLUMN_SOURCES_DEF:
    got = False
    for url in url_list:
        items = fetch_rss(src_name, src_cls, url, max_items=20, today_only=False)
        print(f"  [{src_name}] {url.split('/')[-1]} → {len(items)}건")
        for item in items:
            key = dedup_key(item["title"])
            if key in seen_col:
                continue
            if not is_valid_column(item["title"], src_name):
                print(f"  🚫 [{src_name}] 차단: {item['title'][:30]}")
                continue
            seen_col.add(key)
            print(f"  📝 [{src_name}] {item['title'][:40]}...")
            item["summary"]  = get_column_summary(item["title"])
            item["is_intl"]  = False
            item["src_class"] = src_cls
            item["country_name"] = ""
            columns.append(item)
            time.sleep(0.3)
            got = True
            break
        if got: break
    if not got:
        print(f"  ⚠️  [{src_name}] 칼럼 수집 불가")

# 해외 칼럼 — 전체 소스 순차 (랜덤 제거)
intl_cols = []
for source, src_class, url in INTL_COLUMN_SOURCES:
    items = fetch_rss(source, src_class, url, max_items=8, today_only=False)
    print(f"  🌐 [{source}] {len(items)}건 수신")
    if not items:
        print(f"  ⚠️  [{source}] 수집 실패")
        continue
    for item in items:
        key = dedup_key(item["title"])
        if key in seen_col:
            continue
        seen_col.add(key)
        print(f"  🌐 [{source}] 번역: {item['title'][:40]}...")
        ko_title, bullets = translate_and_summarize(item["title"], source)
        item["ko_title"]     = ko_title or item["title"]
        item["orig_title"]   = item["title"]
        item["title"]        = ko_title if ko_title else item["title"]
        item["summary"]      = "\n".join(bullets) if bullets else "번역 준비 중..."
        item["is_intl"]      = True
        item["src_class"]    = src_class
        item["source"]       = source
        item["country_name"] = INTL_COUNTRY.get(source, "해외")
        intl_cols.append(item)
        time.sleep(0.5)
        break

# 해외 칼럼 국내 칼럼 사이에 삽입 (3번째, 6번째 위치)
for i, ic in enumerate(intl_cols):
    pos = min(3 + i*3, len(columns))
    columns.insert(pos, ic)

print(f"  ✅ 칼럼 총 {len(columns)}건 — 국내 {len(columns)-len(intl_cols)}건 + 해외 {len(intl_cols)}건")

# ════════════════════════════════════════════════════════════
# STEP 3: 사이드바 생성
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
    {{"title":"오늘 뉴스의 핵심 질문 형태로 작성, 20자이내 (예: '이란전쟁, 정말 곧 끝날까?')"}},
    {{"title":"두번째 핵심 질문 20자이내"}},
    {{"title":"세번째 핵심 질문 20자이내"}},
    {{"title":"네번째 핵심 질문 20자이내"}}
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
중요: 오늘의 용어는 오늘 뉴스에 실제 등장한 단어, 중학생도 이해하게 쉽게.""", max_tokens=800)

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
# 파급 체인 HTML — 수혜/역발상/리스크 3체인
# ════════════════════════════════════════════════════════════
print("\n🔗 파급 체인 빌드...")
is_morning = now_kst.hour < 12

HIGH_IMPACT_KW = ["전쟁","제재","금리","관세","봉쇄","폭락","급등","위기","협상","붕괴",
                  "파산","인상","인하","충격","급락","폭등","긴축","기준금리","FOMC","Fed"]
def impact_score(t):
    return sum(1 for kw in HIGH_IMPACT_KW if kw in t)

# 오전=국내→KR / 오후=해외→US
if is_morning:
    chain_pool = [it for sl in section_news.values() for it in sl]
    chain_mkt = "KR"
else:
    chain_pool = list(intl_news) if intl_news else [it for sl in section_news.values() for it in sl]
    chain_mkt = "US"
chain_pool.sort(key=lambda x: impact_score(x.get("ko_title", x.get("title",""))), reverse=True)
chain_seeds = chain_pool[:3]  # 임팩트 상위 3개 뉴스

arr = "&#8595;"
chain_cfg = {
    "chain_main":    {"lb":"var(--red)",  "ncs":["n1","n2","n3"], "bc":"var(--red)"},
    "chain_reverse": {"lb":"var(--navy)", "ncs":["n3","n3","n4"], "bc":"var(--navy)"},
    "chain_risk":    {"lb":"var(--gold)", "ncs":["n2","n2","n4"], "bc":"var(--gold)"},
}

def _make_one_chain(news_title, label, tag1, tag2, tag3, mkt):
    return claude_json(
        f"핵심뉴스: '{news_title}'\n[{label}] 3단계 연쇄분석.\n"
        f"종목: {mkt}시장 중소형주. 삼성전자·현대차·SK하이닉스·NVDA·TSLA·AAPL 제외.\n"
        "probability: 85이상=연쇄근거+수치+모멘텀 모두 충족. 85미만=name 빈칸.\n"
        "JSON만 출력:"
        "{"
        f'"label":"{label}",'
        '"steps":['
        f'{{"tag":"{tag1}","text":"20자","sub":"수치사실"}},'
        f'{{"tag":"{tag2}","text":"20자","sub":"연결이유"}},'
        f'{{"tag":"{tag3}","text":"20자","sub":"핵심포인트"}}'
        '],'
        f'"stock":{{"name":"{mkt}중소형","market":"{mkt}","logic":"A→B→C 40자","upside":"수치포함 25자","probability":85}}'
        "} probability 85미만이면 반드시 name 빈문자열.",
        max_tokens=450
    )

chain_html = "\n"
if chain_seeds:
    for seed_idx, seed in enumerate(chain_seeds):
        s_title = seed.get("ko_title", seed["title"])
        s_src   = seed["source"]
        s_url   = seed["url"]
        s_sc    = seed["src_class"]
        s_pub   = seed["pubtime"]

        try: t_str = datetime.fromisoformat(s_pub).astimezone(KST).strftime("%H:%M")
        except: t_str = ""
        tlbl = f'{"오전" if is_morning else "오후"} {t_str}' if t_str else ("오전" if is_morning else "오후")

        chain_html += (
            f'\n<div class="chain-header-card" style="margin-top:{"0" if seed_idx==0 else "20px"}">\n'
            f'  <div class="chain-time-badge">{tlbl} 핵심 뉴스 {seed_idx+1}</div>\n'
            f'  <div class="chain-seed-title"><a href="{s_url}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none">{s_title}</a></div>\n'
            f'  <div class="chain-seed-meta"><span class="src {s_sc}" style="font-size:9px">{esc(s_src)}</span></div>\n'
            f'</div>\n'
        )

        cd_main = _make_one_chain(s_title, "수혜 체인",   "직접 영향","산업 파급","수혜 종목", chain_mkt)
        cd_rev  = _make_one_chain(s_title, "역발상 체인", "통념",     "역발상",   "역발상 수혜", chain_mkt)
        cd_risk = _make_one_chain(s_title, "리스크 체인", "리스크",   "피해 산업","회피 전략", chain_mkt)

        for cd in [d for d in [cd_main, cd_rev, cd_risk] if d]:
            lbl  = esc(cd.get("label",""))
            stps = cd.get("steps",[])
            stk  = cd.get("stock",{})
            if "수혜" in lbl and "역" not in lbl: cfg_key = "chain_main"
            elif "역발상" in lbl: cfg_key = "chain_reverse"
            else: cfg_key = "chain_risk"
            cfg = chain_cfg[cfg_key]
            _lb = cfg["lb"]; _bc = cfg["bc"]

            inner = '  <div class="chain-steps">\n'
            for si2, sd in enumerate(stps[:3]):
                tag=esc(sd.get("tag","")); txt=esc(sd.get("text","")); sub=esc(sd.get("sub",""))
                nc=cfg["ncs"][si2] if si2<len(cfg["ncs"]) else "n4"
                sub_h=f'<span class="chain-step-sub">{sub}</span>' if sub else ""
                if si2>0: inner+=f'    <div class="chain-arrow-sm">{arr}</div>\n'
                inner+=(f'    <div class="chain-step"><div class="chain-step-num {nc}">{si2+1}</div>'
                        f'<div class="chain-step-body"><span class="chain-step-tag">{tag}</span> '
                        f'<span class="chain-step-text">{txt}</span>{sub_h}</div></div>\n')
            inner+='  </div>\n'

            stock_html=""
            if stk and stk.get("name"):
                nm=esc(stk["name"]); mk=stk.get("market",chain_mkt)
                logic=esc(stk.get("logic","")); up=esc(stk.get("upside",""))
                try: prob=min(max(int(stk.get("probability",0)),0),100)
                except: prob=0
                if prob>=85:
                    up_h=f'<div class="chain-upside-text">&#9650; {up}</div>' if up else ""
                    stock_html=(
                        f'  <div class="chain-stock-row"><div class="chain-stock-card">'
                        f'<div class="chain-stock-left"><span class="chain-stock-name">{nm}</span>'
                        f'<span class="chain-stock-market {mk.lower()}">{mk}</span></div>'
                        f'<div class="chain-stock-right"><div class="chain-logic-text">&#128270; {logic}</div>{up_h}'
                        f'<div class="chain-prob-row"><div class="chain-prob-bar-wrap">'
                        f'<div class="chain-prob-bar" style="width:{prob}%;background:var(--green)"></div></div>'
                        f'<span class="chain-prob-pct" style="color:var(--green)">{prob}%</span>'
                        f'</div></div></div></div>\n'
                    )

            chain_html+=(
                f'\n<div class="sec sec-collapsed" onclick="toggleSection(this)">'
                f'<span class="sec-tag" style="background:{_lb}">{lbl}</span>'
                f'<div class="sec-line"></div><span class="sec-toggle">▾</span></div>\n'
                f'<div class="sec-body collapsed">\n'
                f'<div class="chain-block" style="border-left-color:{_bc};background:var(--tagbg);border-radius:8px;padding:12px 14px;margin:4px 0">\n'
                f'{inner}{stock_html}</div>\n</div>\n'
            )

        print(f"  ✅ 뉴스{seed_idx+1}: {s_title[:25]}... 완료")

    chain_html += '<div class="chain-disclaimer">&#9888;&#65039; AI 분석 참고 정보 — 투자는 전문가 상담 후 본인 판단으로</div>\n'
else:
    chain_html = '<div class="chain-intro"><div class="chain-intro-title">&#128279; 파급 체인</div><div class="chain-intro-sub">뉴스 수집 후 채워집니다</div></div>\n'


# ════════════════════════════════════════════════════════════
# 뉴스 피드 HTML 정적 생성 (CORS 우회 — Actions에서 직접 수집)
# ════════════════════════════════════════════════════════════
print("\n📰 뉴스 피드 빌드...")

feed_items = []
seen_feed = set()

# 섹션별 뉴스 + 해외뉴스를 시간순 정렬
FEED_COLORS = {
    "경제 · 금융": "#1a3050",
    "기 업":       "#7a1f1f",
    "정책 · 사회": "#1a4a2e",
    "국 제":       "#7a5800",
    "해 외":       "#4a3070",
}
for sec in NEWS_SECTIONS:
    for it in section_news.get(sec, []):
        dk = dedup_key(it.get("title",""))
        if dk in seen_feed: continue
        seen_feed.add(dk)
        feed_items.append({
            "title": it.get("title",""),
            "url":   it.get("url","#"),
            "time":  it.get("pubtime",""),
            "color": FEED_COLORS.get(sec, "#888"),
        })
for it in intl_news:
    dk = dedup_key(it.get("ko_title", it.get("title","")))
    if dk in seen_feed: continue
    seen_feed.add(dk)
    feed_items.append({
        "title": it.get("ko_title", it.get("title","")),
        "url":   it.get("url","#"),
        "time":  it.get("pubtime",""),
        "color": FEED_COLORS["해 외"],
    })

# 시간 역순 정렬
def _sort_time(x):
    try: return datetime.fromisoformat(x["time"])
    except: return datetime.min.replace(tzinfo=KST)
feed_items.sort(key=_sort_time, reverse=True)

feed_rows = ""
for fi in feed_items:
    try:
        dt = datetime.fromisoformat(fi["time"]).astimezone(KST)
        t_str = dt.strftime("%H:%M")
    except:
        t_str = "--:--"
    title = esc(fi["title"])
    url   = fi["url"]
    color = fi["color"]
    feed_rows += (
        f'<div class="feed-item" onclick="window.open(\'{url}\',\'_blank\')">'
        f'<span class="feed-time">{t_str}</span>'
        f'<span class="feed-dot" style="background:{color}"></span>'
        f'<a class="feed-title" href="{url}" target="_blank" rel="noopener" '
        f'onclick="event.stopPropagation()">{title}</a>'
        f'</div>\n'
    )

feed_html = f"""
<div class="feed-status">
  <span class="feed-live-dot"></span>
  <span>오늘의 뉴스 피드 · {len(feed_items)}건</span>
  <span class="feed-last-update">{now_kst.strftime('%H:%M')} 업데이트</span>
</div>
<div class="feed-list">
{feed_rows}
</div>
"""
print(f"  ✅ 피드 {len(feed_items)}건 생성")

# ════════════════════════════════════════════════════════════
# STEP 4: HTML 빌드
# ════════════════════════════════════════════════════════════
print("\n🔨 [4/4] HTML 빌드...")

def make_news_card(item, card_color, hist_key):
    title      = esc(item["title"])
    url        = item["url"]
    src        = item["source"]
    sc         = item["src_class"]
    pub        = item["pubtime"]
    bullets    = item.get("bullets") or []
    hist_label = HIST_LABELS.get(hist_key, hist_key)

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
for section in NEWS_SECTIONS:
    items = section_news[section]
    if not items: continue
    color = SECTION_COLORS[section]
    cc    = CARD_COLORS[section]
    hk    = HIST_KEYS[section]
    news_html += f'\n    <div class="sec sec-collapsed" onclick="toggleSection(this)"><span class="sec-tag" style="background:{color}">{section}</span><div class="sec-line"></div><span class="sec-toggle">▾</span></div>\n    <div class="sec-body collapsed">\n'
    for item in items:
        news_html += make_news_card(item, cc, hk)
    news_html += '    </div>\n'
news_html += "\n"

# ── 주요 뉴스 섹션: 각 섹션 첫 번째 기사 1개씩 묶기 ─────────
headline_html = "\n"
headline_html += (
    '\n    <div class="sec sec-collapsed" onclick="toggleSection(this)">'
    '<span class="sec-tag" style="background:var(--accent)">주 요 뉴 스</span>'
    '<div class="sec-line"></div><span class="sec-toggle">▾</span></div>\n'
    '    <div class="sec-body collapsed">\n'
)
_hl_used = set()
def _pick_hl(items):
    for it in items:
        if it["source"] not in _hl_used:
            return it
    return items[0] if items else None

for section in NEWS_SECTIONS:
    items = section_news.get(section, [])
    if not items:
        continue
    item = _pick_hl(items)
    if not item: continue
    _hl_used.add(item["source"])
    color = SECTION_COLORS[section]
    cc    = CARD_COLORS[section]
    hk    = HIST_KEYS[section]
    title      = esc(item["title"])
    url        = item["url"]
    src        = esc(item["source"])
    sc         = item["src_class"]
    pub        = item["pubtime"]
    bullets    = item.get("bullets") or []
    hist_label = HIST_LABELS.get(hk, hk)
    li_html      = "".join(f"<li>{esc(b)}</li>" for b in bullets[:3]) if bullets else "<li>요약 로딩 중...</li>"
    bullets_html = f'<ul class="cpts">{li_html}</ul>'
    headline_html += f"""
    <div class="card {cc}" onclick="toggleCard(this)">
      <div class="ct">
        <span class="hl-sec-tag" style="background:{color}">{section}</span>
        <span class="src {sc}">{src}</span>
        <span class="ctime" data-pubtime="{pub}">🕒 --</span>
        <span class="expand-hint">▾</span>
      </div>
      <div class="ch">{title}</div>
      <div class="card-expand">
        {bullets_html}
        <div class="card-btns">
          <button class="cbtn case-btn" onclick="toggleCase(this,'{hk}',event)">📂 {hist_label}</button>
          <a class="cbtn read-btn" href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()">↗ 기사 보기</a>
        </div>
        <div class="case-panel">
          <div class="case-panel-hd"><span>📂 과거 사례 — {hist_label}</span><span class="case-panel-close" onclick="closeCase(this,event)">✕</span></div>
          <div class="case-panel-body"></div>
        </div>
      </div>
    </div>"""
headline_html += "    </div>\n"


def make_intl_card(item):
    ko_title   = esc(item.get("ko_title", item["title"]))
    orig_title = esc(item.get("orig_title", ""))
    url        = item["url"]
    src        = item["source"]
    pub        = item["pubtime"]
    bullets    = item.get("bullets") or []
    hist_key   = item.get("hist_key", "iran_war")
    hist_label = HIST_LABELS.get(hist_key, hist_key)
    country    = item.get("country_name", "해외")

    if bullets:
        li_html = "".join(f"<li>{esc(b)}</li>" for b in bullets[:3])
        bullets_html = f'<ul class="cpts">{li_html}</ul>'
    else:
        bullets_html = '<ul class="cpts"><li>번역 로딩 중...</li></ul>'

    orig_html = f'<div class="ch-orig">{orig_title}</div>' if orig_title else ''

    return f'''
    <div class="card dk" onclick="toggleCard(this)">
      <div class="ct"><span class="src intl">{src}</span><span class="country-badge" data-c="{country}">{country}</span><span class="ctime" data-pubtime="{pub}">🕒 --</span><span class="expand-hint">▾</span></div>
      <div class="ch">{ko_title}</div>
      <div class="card-expand">
        {orig_html}
        {bullets_html}
        <div class="card-btns">
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
    cc      = col_colors[i % len(col_colors)]
    title   = esc(item["title"])
    url     = item["url"]
    src     = item["source"]
    sc      = item["src_class"]
    pub     = item["pubtime"]
    is_intl = item.get("is_intl", False)
    country = item.get("country_name", "")
    try:
        dt = datetime.fromisoformat(pub)
        date_str = dt.astimezone(KST).strftime("%Y.%m.%d")
    except:
        date_str = now_ymd
    summary   = esc(item.get("summary", "요약 준비 중..."))
    orig_html = f'<div class="ch-orig">{esc(item["orig_title"])}</div>' if is_intl and item.get("orig_title") else ''
    country_badge = f'<span class="country-badge" data-c="{country}">{country}</span>' if is_intl and country else ''
    col_html += f'''
    <div class="col-card {cc}">
      <div class="col-top">
        <span class="col-paper src {sc}">{src}</span>
        {country_badge}
        <span class="col-date">{date_str}</span>
      </div>
      <div class="col-title"><a href="{url}" target="_blank" rel="noopener" onclick="event.stopPropagation()" style="color:inherit">{title}</a></div>
      {orig_html}
      <div class="col-body">{summary}</div>
    </div>'''
col_html += "\n"

def build_right(data, hl_list):
    nums = data.get("핵심수치", [])
    pts  = data.get("관전포인트", [])

    stats = ""
    for n in nums[:6]:
        clr = "r" if n.get("up", True) else "b"
        _val  = str(n.get("value", n.get("수치", "--")))
        _lbl  = str(n.get("label", n.get("항목", "")))
        _desc = str(n.get("desc",  n.get("설명", "")))
        stats += f'<div class="mstat"><div class="mnum {clr}">{esc(_val)}</div><div class="mlbl">{esc(_lbl)}<br><small style="font-size:9px">{esc(_desc)}</small></div></div>'

    icons = ['①','②','③','④']
    pts_html = ""
    for i, p in enumerate(pts[:4]):
        pts_html += f'<div class="pt-item"><span class="pt-num">{icons[i]}</span><span class="pt-title">{esc(p["title"])}</span></div>'

    terms = data.get("오늘의용어", [])
    term_html = ""
    for t in terms[:4]:
        en = f'<span class="term-en">{esc(t.get("en",""))}</span>' if t.get("en") else ""
        term_html += f'''<div class="term-item">
          <div class="term-word">{esc(t["word"])} {en}</div>
          <div class="term-desc">{esc(t["desc"])}</div>
        </div>'''

    return f"""
    <div class="sbox sbox-toggle" onclick="toggleSbox(this, event)">
      <div class="sbox-hd"><span class="dot" style="background:var(--red)"></span>오늘의 핵심 수치<span class="sbox-arr">▾</span></div>
      <div class="sbox-body"><div class="mini-stats">{stats}</div></div>
    </div>
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--gold)"></span>오늘의 관전 포인트</div>
      <div class="pt-list">{pts_html}</div>
    </div>
    <div class="sbox sbox-toggle" onclick="toggleSbox(this, event)">
      <div class="sbox-hd"><span class="dot" style="background:var(--accent)"></span>오늘의 용어<span class="sbox-arr">▾</span></div>
      <div class="sbox-body"><div class="term-list">{term_html if term_html else '<div class="term-item"><div class="term-desc">업데이트 준비 중</div></div>'}</div></div>
    </div>
"""

right_html = build_right(sidebar_data, hl_items)

논점 = esc(sidebar_data.get("칼럼논점", ""))
col_right_html = f"""
    <div class="sbox">
      <div class="sbox-hd"><span class="dot" style="background:var(--navy)"></span>오늘의 논점</div>
      <div class="issue-list"><div class="issue-item" style="line-height:1.6">{논점}</div></div>
    </div>
"""

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

def build_archive_entry(section_news_data, date_d, date_sub, date_id):
    all_titles_today = []
    cards = ""
    for section, items in section_news_data.items():
        color = SECTION_COLORS[section]
        cc    = CARD_COLORS[section]
        for item in items[:3]:
            all_titles_today.append(item["title"])
            title    = esc(item["title"])
            url      = item["url"]
            src_name = item.get("source", "")
            src_cls  = item.get("src_class", "")
            cards += f'''<div class="card {cc}" style="margin-top:4px">
              <div class="ct"><span class="src" style="background:{color};font-size:8px;padding:2px 6px;color:#fff;border-radius:2px">{section}</span><span class="src {src_cls}" style="margin-left:4px">{src_name}</span></div>
              <div class="ch" style="font-size:12.5px"><a href="{url}" class="ch-link" target="_blank" style="color:inherit">{title}</a></div>
            </div>'''
    total = sum(len(v) for v in section_news_data.values())
    return f"""
  <div>
    <div class="arch-row" onclick="tog('{date_id}')">
      <div class="aday"><div class="adaynum">{date_d}</div><div class="adaysub">{date_sub}</div></div>
      <div class="acnt">▾ {total}건</div>
    </div>
    <div class="arch-detail" id="{date_id}">{cards}</div>
  </div>"""

archive_entry = build_archive_entry(
    section_news, today_day, today_sub,
    f"d{today_day}_{now_kst.strftime('%H')}"
)
archive_html = f'<div class="arch-list">\n{archive_entry}\n</div>'

# ════════════════════════════════════════════════════════════
# index.html 교체
# ════════════════════════════════════════════════════════════
update_display = make_update_display(latest_pubtime)
print(f"  📅 최신 기사: {latest_pubtime.strftime('%H:%M')} → {update_display}")

INDEX_PATH = "index.html"
if not os.path.exists(INDEX_PATH):
    print("❌ index.html 없음")
    sys.exit(1)

with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html = f.read()

html = re.sub(r'<meta name="last-updated"[^>]*>',
              f'<meta name="last-updated" content="{now_iso}">', html)
html = re.sub(
    r'(<span[^>]+id="hdr-update"[^>]*>)[^<]*(</span>)',
    rf'\g<1>{update_display}\g<2>', html
)

def replace_block(html, s, e, content):
    if s in html and e in html:
        return re.sub(
            re.escape(s) + r'.*?' + re.escape(e),
            f"{s}\n{content}\n{e}",
            html, flags=re.DOTALL
        )
    print(f"  ⚠️  마커 없음: {s[:40]}")
    return html

html = replace_block(html, '<!-- AUTO_FEED_START -->', '<!-- AUTO_FEED_END -->', feed_html)
html = replace_block(html, '<!-- AUTO_CHAIN_RIGHT_START -->', '<!-- AUTO_CHAIN_RIGHT_END -->', '')
html = replace_block(html, '<!-- AUTO_CHAIN_START -->', '<!-- AUTO_CHAIN_END -->', chain_html)
html = replace_block(html, '<!-- AUTO_HEADLINE_START -->', '<!-- AUTO_HEADLINE_END -->', headline_html)
html = replace_block(html, '<!-- AUTO_NEWS_START -->',      '<!-- AUTO_NEWS_END -->',      news_html)
html = replace_block(html, '<!-- AUTO_INTL_START -->',      '<!-- AUTO_INTL_END -->',      intl_html)
html = replace_block(html, '<!-- AUTO_COLUMN_START -->',    '<!-- AUTO_COLUMN_END -->',    col_html)
html = replace_block(html, '<!-- AUTO_RIGHT_START -->',     '<!-- AUTO_RIGHT_END -->',     right_html)
html = replace_block(html, '<!-- AUTO_COL_RIGHT_START -->', '<!-- AUTO_COL_RIGHT_END -->', col_right_html)

if '<!-- AUTO_COL_ARCHIVE_START -->' in html:
    col_archive_html = build_col_archive({})
    html = replace_block(html, '<!-- AUTO_COL_ARCHIVE_START -->', '<!-- AUTO_COL_ARCHIVE_END -->', '\n' + col_archive_html + '\n')

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
print(f"  뉴스 {sum(len(v) for v in section_news.values())}건 | 해외 {len(intl_news)}건 | 칼럼 {len(columns)}건")
print(f"  섹션별: " + " | ".join(f"{s} {len(section_news[s])}건" for s in NEWS_SECTIONS))
