#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오늘의 브리핑 자동 업데이트 스크립트 (최종 수정본)
- Gemini 1.5 Flash 사용 (안정성 최우선)
- 안전 필터 해제 (모든 뉴스 요약 가능)
- 호출 간격 조정 (무료 티어 속도 제한 회피)
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
        
        # 모델 설정: 안전 필터를 모두 해제하여 뉴스 요약 중단 방지
        gemini_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"temperature": 0.5},
            safety_settings=[
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
            ]
        )
        print("✅ Gemini API 연결 및 안전 설정 완료 (1.5-flash)")
    except Exception as e:
        print(f"⚠️ Gemini 초기화 실패: {e}")
else:
    print("⚠️ GEMINI_API_KEY가 환경 변수에 없습니다.")

def get_ai_summary(title):
    """뉴스 제목을 바탕으로 AI 요약 생성"""
    if not gemini_model:
        return "요약 서비스를 이용할 수 없습니다."
    
    try:
        # 분당 호출 제한(RPM)을 피하기 위해 기사당 최소 4초 대기
        time.sleep(4) 
        
        prompt = f"너는 뉴스 분석가야. 다음 뉴스 제목을 보고 핵심 내용을 3~5줄로 요약해줘. 각 줄 끝에는 내용에 맞는 이모지를 붙여줘. 전문적인 말투로 작성해.\n\n제목: {title}"
        
        response = gemini_model.generate_content(prompt)
        
        if response and response.text:
            # 줄바꿈을 HTML 태그로 변경
            return response.text.strip().replace("\n", "<br>")
        else:
            return "내용을 분석 중입니다. 원문을 확인해 주세요. 🗞️"
            
    except Exception as e:
        print(f"  ❌ 요약 실패: {e}")
        return "요약을 생성하는 과정에서 오류가 발생했습니다."

# ─────────────────────────────────────────
# 뉴스 수집 설정
# ─────────────────────────────────────────
KST = pytz.timezone("Asia/Seoul")
now_kst = datetime.now(KST)
now_iso = now_kst.strftime("%Y-%m-%dT%H:%M:%S+09:00")

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

# RSS 소스 (원하시는 대로 추가/삭제 가능)
RSS_SOURCES = {
    "경제 · 금융": [
        ("매일경제", "e", "https://www.mk.co.kr/rss/30000001/"),
        ("한국경제", "e", "https://www.hankyung.com/feed/economy")
    ],
    "기 업": [
        ("조선일보", "c", "https://www.chosun.com/arc/outboundfeeds/rss/category/economy/"),
        ("매일경제", "e", "https://www.mk.co.kr/rss/30200030/")
    ],
    "정책 · 사회": [
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/politics.xml"),
        ("경향신문", "p", "https://www.khan.co.kr/rss/rssdata/kh_politics.xml")
    ],
    "국 제": [
        ("연합뉴스", "w", "https://www.yonhapnews.co.kr/rss/international.xml"),
        ("조선일보", "c", "https://www.chosun.com/arc/outboundfeeds/rss/category/international/")
    ]
}

SECTION_COLORS = {"경제 · 금융": "var(--red)", "기 업": "var(--navy)", "정책 · 사회": "var(--gold)", "국 제": "var(--dark)"}
CARD_COLORS = {"경제 · 금융": "red", "기 업": "navy", "정책 · 사회": "gold", "국 제": "dk"}

def fetch_rss(source, src_class, url):
    """RSS 피드에서 기사 수집 및 요약 실행"""
    items = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.content, "lxml-xml")
        # 소스별로 최신 기사 3개씩 가져오기
        for item in soup.find_all("item")[:3]:
            title = item.find("title").get_text(strip=True)
            link = item.find("link").get_text(strip=True)
            
            print(f"  🤖 요약 생성 중: {title[:25]}...")
            summary = get_ai_summary(title)
            
            items.append({
                "source": source, "src_class": src_class, "title": title,
                "url": link, "pubtime": now_iso, "summary": summary
            })
    except Exception as e:
        print(f"  ⚠️ {source} 수집 실패: {e}")
    return items

# ─────────────────────────────────────────
# 메인 실행 로직
# ─────────────────────────────────────────
print(f"🚀 [{now_kst.strftime('%Y-%m-%d %H:%M')}] 브리핑 업데이트 및 요약 시작")

section_news = {}
for section, sources in RSS_SOURCES.items():
    all_items = []
    for src, cls, url in sources:
        all_items.extend(fetch_rss(src, cls, url))
    # 섹션당 최종적으로 보여줄 기사 개수 (최대 5개)
    section_news[section] = all_items[:5]

# HTML 카드 생성
def make_card(item, card_color):
    return f'''
    <div class="card {card_color}">
      <div class="ct">
        <span class="src {item['src_class']}">{item['source']}</span>
        <span class="ctime" data-pubtime="{item['pubtime']}">🕒 방금 전</span>
      </div>
      <div class="ch"><a href="{item['url']}" class="ch-link" target="_blank">{item['title']}</a></div>
      <div class="card-summary" style="font-size:13px; color:#555; background:#f9f9f9; padding:12px; border-radius:8px; margin:10px 0; border-left:4px solid var(--border);">
        {item['summary']}
      </div>
      <div class="card-history-row">
        <a href="{item['url']}" target="_blank" style="font-size:10px;color:var(--navy);text-decoration:none;font-weight:bold;">↗ 기사 원문 읽기</a>
      </div>
    </div>'''

# index.html 파일 읽기
INDEX_PATH = "index.html"
with open(INDEX_PATH, "r", encoding="utf-8") as f:
    html_content = f.read()

# 뉴스 섹션 생성
new_news_html = ""
for section, items in section_news.items():
    new_news_html += f'\n<div class="sec"><span class="sec-tag" style="background:{SECTION_COLORS[section]}">{section}</span><div class="sec-line"></div></div>\n'
    for item in items:
        new_news_html += make_card(item, CARD_COLORS[section])

# 마커 사이 내용 교체
pattern = r'.*?'
replacement = f'{new_news_html}\n'

if re.search(pattern, html_content, flags=re.DOTALL):
    html_content = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # 마지막 업데이트 시간 갱신
    meta_new = f'<meta name="last-updated" content="{now_iso}">'
    html_content = re.sub(r'<meta name="last-updated"[^>]*>', meta_new, html_content)
    
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(html_content)
    print("💾 모든 작업이 완료되었습니다! index.html 저장 완료.")
else:
    print("❌ 오류: index.html에서 마커(AUTO_NEWS_START)를 찾을 수 없습니다.")
