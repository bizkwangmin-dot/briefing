"""
GitHub Issue → Claude API → 파일 수정 자동화
이슈 제목: [수정] 하고 싶은 내용
이슈 본문: 구체적인 수정 지시
"""
import os
import anthropic

ISSUE_TITLE = os.environ.get("ISSUE_TITLE", "")
ISSUE_BODY  = os.environ.get("ISSUE_BODY", "")

# 수정 대상 파일 읽기
files = {}
for fname in ["index.html", "update_briefing.py"]:
    if os.path.exists(fname):
        with open(fname, "r", encoding="utf-8") as f:
            files[fname] = f.read()

client = anthropic.Anthropic()

prompt = f"""당신은 세줄뉴스 웹사이트(https://bizkwangmin-dot.github.io/briefing/)의 코드를 수정하는 어시스턴트입니다.

수정 요청:
제목: {ISSUE_TITLE}
내용: {ISSUE_BODY}

현재 파일들:
=== index.html (앞 3000자) ===
{files.get('index.html','')[:3000]}

=== update_briefing.py (앞 3000자) ===
{files.get('update_briefing.py','')[:3000]}

위 수정 요청을 반영하여 파일을 수정하세요.
수정이 필요한 파일만, 아래 형식으로 출력하세요:

===FILE: 파일명===
[전체 수정된 파일 내용]
===END===

중요: 수정하지 않는 파일은 출력하지 마세요. 설명 없이 바로 파일 내용만 출력하세요."""

print(f"📋 이슈: {ISSUE_TITLE}")
print(f"📝 내용: {ISSUE_BODY[:200]}")
print("🤖 Claude가 수정 중...")

# 파일이 크므로 streaming으로 받기
full_response = ""
with client.messages.stream(
    model="claude-sonnet-4-5",
    max_tokens=8000,
    messages=[{"role": "user", "content": prompt}]
) as stream:
    for text in stream.text_stream:
        full_response += text
        print(text, end="", flush=True)

print("\n\n✅ Claude 응답 완료")

# 파일 파싱 및 저장
import re
pattern = r'===FILE:\s*(.+?)===\n(.*?)===END==='
matches = re.findall(pattern, full_response, re.DOTALL)

if not matches:
    print("⚠️  수정할 파일을 찾지 못했습니다. 이슈 내용을 더 구체적으로 작성해주세요.")
    exit(0)

for fname, content in matches:
    fname = fname.strip()
    content = content.strip()
    if fname in ["index.html", "update_briefing.py"]:
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ {fname} 저장 완료 ({len(content):,}자)")
    else:
        print(f"⚠️  알 수 없는 파일: {fname} (무시)")

print("🚀 파일 수정 완료 — 커밋 진행 중...")
