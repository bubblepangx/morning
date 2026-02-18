"""
Market Sentinel - Daily Briefing Generator
GitHub: https://github.com/bubblepangx/morning
"""
import anthropic
import os
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))
now = datetime.now(KST)
WEEKDAY_KO = ["월", "화", "수", "목", "금", "토", "일"]
date_ko = now.strftime("%Y년 %m월 %d일")
weekday_ko = WEEKDAY_KO[now.weekday()]
datetime_ko = f"{date_ko} ({weekday_ko}) 오전 {now.strftime('%H시 %M분')} KST"
file_date = now.strftime("%Y%m%d")

SYSTEM_PROMPT = (
    "당신은 Bloomberg와 Financial Times에서 25년 경력을 쌓은 선임 시장 기자이자 분석가 'Market Sentinel'입니다.\n\n"
    "[페르소나]\n"
    "- 독자: 한국 기관투자자(연기금·자산운용사·증권사 리서치팀)와 고액자산가(UHNW)\n"
    "- 문체: Bloomberg Morning Briefing 수준 — 세련되고 통찰력 있으며 전문적\n"
    "- 핵심 원칙: 단순 수치 나열이 아닌 시장 흐름의 이야기(narrative)를 풀어낸다\n"
    "- 중립·사실 기반. 과장·투기적 표현·루머 절대 사용 금지\n"
    "- 출처(Bloomberg, Reuters, CNBC, Yonhap, Fed, Treasury 등)는 문장 속에 자연스럽게 녹인다\n"
    "- 섹션 간 인과관계 연결이 핵심\n\n"
    "[웹 검색 지시]\n"
    "- web_search 도구를 적극 사용하여 실시간 데이터를 수집하라\n"
    "- 반드시 검색해야 할 항목:\n"
    "  1. US stock market close today Dow S&P Nasdaq final\n"
    "  2. VIX index today CNN fear greed index current\n"
    "  3. US 10 year treasury yield 2 year yield today\n"
    "  4. S&P 500 futures Nasdaq 100 futures premarket now\n"
    "  5. WTI crude oil gold price today current\n"
    "  6. put call ratio today stock market\n"
    "  7. top stock gainers losers US market today\n"
    "  8. Fed rate outlook CME FedWatch latest\n"
    "  9. major earnings results after hours today\n"
    "  10. China market Shanghai Hang Seng Alibaba DeepSeek AI news today\n"
    "  11. Nikkei 225 close yen dollar BOJ today\n"
    "  12. Korea Samsung SK Hynix semiconductor news today\n"
    "- 검색 결과 불충분하면 추가 검색 실시\n"
    "- 검색으로 확인된 수치만 사용. 불확실하면 확인 중 명시\n\n"
    "[출력 규칙]\n"
    "- 언어: 한국어\n"
    "- 형식: Markdown (헤딩·표·볼드·이모지 허용)\n"
    "- 전체 분량: 2,000~2,800자"
)

USER_PROMPT_TEMPLATE = """\
지금 시각은 {datetime_ko}입니다.

web_search 도구로 KST 06:50 기준 최신 데이터를 수집한 뒤, 아래 9개 섹션 구조에 맞춰 Market Sentinel 모닝 브리핑을 작성하세요.

# Market Sentinel 모닝 브리핑
## {datetime_ko}

---

## 1. 오늘의 시장 요약 (Lead)
3~5줄 이내. overnight 최강 이벤트로 첫 문장 시작. 오늘 아시아·한국 시장 파급 효과 압축. 오늘 핵심 변수 1~2개 예고.

---

## 2. 미국장 마감 정리 (Overnight Wrap)

### 3대 지수 + 소형주

| 지수 | 종가 | 전일 대비 | 등락률 |
|---|---|---|---|
| 다우존스 (DJIA) | | | |
| S&P 500 | | | |
| 나스닥 종합 | | | |
| 러셀 2000 | | | |

### 섹터 흐름
- 상승 섹터: 섹터명 + 주도 종목 + 이유
- 하락 섹터: 섹터명 + 주도 종목 + 이유

### 시장 심리 지표

| 지표 | 수치 | 해석 |
|---|---|---|
| VIX (공포지수) | | 15이하안정/20이상경계/30이상공포 |
| CNN 공탐지수 | | 0~24극단공포/45~55중립/76~100극단탐욕 |
| 풋/콜 비율 | | 1.0이상하락베팅/0.7이하상승베팅 |
| S&P500 선물 (현재) | | |
| 나스닥100 선물 (현재) | | |
| WTI 원유 | | |
| 금 현물 (XAU/USD) | | |
| 달러 인덱스 (DXY) | | |

---

## 3. 금리·매크로 환경

### 미 국채 수익률

| 구분 | 수익률 | 전일 대비 | 해석 |
|---|---|---|---|
| 10년물 | | | |
| 2년물 | | | |
| 10-2년 스프레드 | | | |

### Fed 금리 경로
- 현재 기준금리 목표범위:
- CME 페드워치 다음 회의 동결/인하 확률:
- 최근 Fed 발언 or 의사록 요약:

### 핵심 리스크 2~3가지
리스크명 / 현황 / 시장 영향 서술

---

## 4. 주요 기업 핫이슈 (Hot Company Stories)
After-Hours 포함, 시장 가장 크게 움직인 미국 대형주 5~7개.
각 기업마다: 기업명(티커) — 주가변동, 이슈요약, 투자자심리 인과관계

---

## 5. 급등·급락 Top 5

### 급등 Top 5

| 순위 | 종목 (티커) | 등락률 | 핵심 이유 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

### 급락 Top 5

| 순위 | 종목 (티커) | 등락률 | 핵심 이유 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

흐름 연결 분석 (2~3줄)

---

## 6. 한국 시장 관련 오버나이트 소식

IWM(러셀2000 ETF): 현재가 / 등락률 / 52주 범위 대비 위치

반도체: 삼성전자·SK하이닉스 해외 뉴스 (공급망·수요·규제·HBM)

자동차: 현대차·기아 (관세·EV 수요·리콜·해외 판매)

조선: 한화오션·HD현대 글로벌 수주·발주 뉴스

코스피·코스닥 주목 포인트: 미국 오버나이트가 한국 어느 섹터에 어떻게 전이될지 2~3줄

---

## 7. 중국 시장 오버나이트 소식

시장 지수: 상하이종합 / 항셍 전일 마감

빅테크·AI 신기술: Alibaba·ByteDance·DeepSeek·Tencent·Baidu 최신 소식, AI 모델 발표

정책·매크로: 정부 경기부양·산업정책·위안화·PBOC 동향

시장 관전 포인트: 중국발 변수가 미국·한국 시장에 미칠 파급 가능성

---

## 8. 일본 시장 오버나이트 소식 (5줄 이내)

니케이225 전일 마감: 수치 + 등락률 + 한 줄 요약
주도 상승주 / 하락주 (각 1~2개)
엔/달러 환율 동향 및 의미
BOJ 정책·정치 이슈
오늘 아시아 시장 시사점

---

## 9. 오늘 주목할 이벤트 & Outlook

### 오늘({date_ko}) 핵심 일정

| 시간(KST) | 이벤트 | 영향도 |
|---|---|---|
| | | 상중하 |

### 내일 예고
내일 예정 주요 이벤트 1~3개

### 투자자 대응 관점
- 오늘 시장 예상 방향성: 상승/하락/박스권 + 근거
- 리스크 시나리오 (if-then 형식)
- 포지션 전략 팁 (특정 종목 추천 금지, 섹터·전략 수준)

---
본 브리핑은 Bloomberg, Reuters, CNBC, Yahoo Finance, Nikkei Asia 등 공개 데이터 기반 정보 제공 목적이며 투자 권유가 아닙니다.
수치 기준: {datetime_ko}
"""


def to_html(md: str) -> str:
    try:
        import markdown as md_lib
        body = md_lib.markdown(md, extensions=["tables", "fenced_code", "nl2br"])
    except ImportError:
        safe = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        body = f"<pre style='white-space:pre-wrap'>{safe}</pre>"

    year = now.year
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta property="og:title" content="Market Sentinel {date_ko}">
  <meta name="twitter:card" content="summary">
  <title>Market Sentinel {date_ko}</title>
  <style>
    :root{{--bg:#080d18;--surface:#0f1729;--border:#1e2d45;--text:#e2e8f0;--muted:#64748b;--accent:#3b82f6;--font:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;}}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:var(--bg);color:var(--text);font-family:var(--font);font-size:15px;line-height:1.8;padding:0 1rem 3rem}}
    a{{color:var(--accent);text-decoration:none}}
    .hdr{{max-width:860px;margin:0 auto;padding:2rem 0 1.5rem;border-bottom:2px solid var(--accent);margin-bottom:2.5rem}}
    .hdr .badge{{font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;color:var(--accent);margin-bottom:.5rem}}
    .hdr h1{{font-size:1.65rem;font-weight:800;color:#fff;margin-bottom:.3rem}}
    .hdr .meta{{font-size:.78rem;color:var(--muted)}}
    .card{{max-width:860px;margin:0 auto;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:2.2rem 2.8rem}}
    .card h1{{font-size:1.4rem;color:#fff;margin:2rem 0 .8rem;border-bottom:1px solid var(--border);padding-bottom:.5rem}}
    .card h2{{font-size:1.2rem;color:var(--accent);margin:1.8rem 0 .6rem}}
    .card h3{{font-size:1rem;color:#cbd5e1;margin:1.2rem 0 .4rem}}
    .card p{{margin-bottom:.9rem}}
    .card strong{{color:#fff}}
    .card ul,.card ol{{padding-left:1.4rem;margin-bottom:.9rem}}
    .card li{{margin-bottom:.35rem}}
    .card hr{{border:none;border-top:1px solid var(--border);margin:1.8rem 0}}
    .card code{{background:#1e2d45;padding:.15em .4em;border-radius:4px;font-size:.88em}}
    .card table{{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.9rem}}
    .card th{{background:#162033;color:var(--accent);padding:.55rem .8rem;text-align:left;border-bottom:2px solid var(--border);font-weight:600;white-space:nowrap}}
    .card td{{padding:.5rem .8rem;border-bottom:1px solid var(--border);vertical-align:top}}
    .card tr:hover td{{background:#0d1826}}
    footer{{max-width:860px;margin:1.8rem auto 0;text-align:center;font-size:.73rem;color:var(--muted)}}
    @media(max-width:600px){{.card{{padding:1.2rem 1rem}}.hdr h1{{font-size:1.2rem}}.card th,.card td{{padding:.4rem .5rem}}}}
  </style>
</head>
<body>
  <header class="hdr">
    <div class="badge">Market Sentinel Daily Briefing</div>
    <h1>{date_ko} ({weekday_ko}) 모닝 브리핑</h1>
    <div class="meta">Generated {now.strftime('%Y-%m-%d %H:%M')} KST &nbsp;Powered by Claude AI &nbsp;<a href="https://github.com/bubblepangx/morning" target="_blank">GitHub</a></div>
  </header>
  <main class="card">{body}</main>
  <footer>본 브리핑은 공개 데이터 기반 정보 제공 목적이며 투자 권유가 아닙니다.<br>© {year} Market Sentinel &nbsp;<a href="https://github.com/bubblepangx/morning">bubblepangx/morning</a></footer>
</body>
</html>"""


def generate() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY 환경변수가 없습니다.\n"
            "GitHub Actions: Settings > Secrets > ANTHROPIC_API_KEY 등록 필요\n"
            "로컬: export ANTHROPIC_API_KEY='sk-ant-api03-...'"
        )

    client = anthropic.Anthropic(api_key=api_key)
    user_prompt = USER_PROMPT_TEMPLATE.format(
        datetime_ko=datetime_ko,
        date_ko=date_ko
    )
    messages = [{"role": "user", "content": user_prompt}]
    tools = [{"type": "web_search_20250305", "name": "web_search"}]

    print(f"[{now.strftime('%H:%M')} KST] 브리핑 생성 시작 - {date_ko}")
    total_tokens = 0
    iteration = 0
    max_iter = 25

    while iteration < max_iter:
        iteration += 1
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=8192,
            system=SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        )
        total_tokens += response.usage.output_tokens

        if response.stop_reason == "end_turn":
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            print(f"[{now.strftime('%H:%M')} KST] 완료 ({total_tokens:,} tokens, {iteration}회)")
            return text

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if not hasattr(block, "type") or block.type != "tool_use":
                    continue
                query = block.input.get("query", "") if hasattr(block, "input") else ""
                print(f"  검색: {query}")
                result_text = ""
                for b in response.content:
                    if (
                        hasattr(b, "type")
                        and b.type == "tool_result"
                        and getattr(b, "tool_use_id", None) == block.id
                    ):
                        result_text = getattr(b, "content", "")
                        break
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result_text or "검색 완료",
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        print(f"  예상치 못한 stop_reason: {response.stop_reason}")
        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        if text:
            return text
        break

    raise RuntimeError(f"최대 반복({max_iter}회) 초과 - 응답 생성 실패")


def save(briefing: str):
    out = Path("docs")
    out.mkdir(exist_ok=True)

    (out / f"{file_date}.md").write_text(briefing, encoding="utf-8")

    html = to_html(briefing)
    (out / f"{file_date}.html").write_text(html, encoding="utf-8")
    (out / "index.html").write_text(html, encoding="utf-8")

    meta_path = out / "meta.json"
    history = []
    if meta_path.exists():
        try:
            history = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            history = []

    entry = {"date": file_date, "label": date_ko, "file": f"{file_date}.html"}
    if not any(e["date"] == file_date for e in history):
        history.insert(0, entry)
    meta_path.write_text(
        json.dumps(history[:60], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  docs/{file_date}.md")
    print(f"  docs/{file_date}.html")
    print(f"  docs/index.html  <- GitHub Pages 진입점")
    print(f"  docs/meta.json")


if __name__ == "__main__":
    try:
        briefing = generate()
        save(briefing)
        print(f"\n발행 완료 - {datetime_ko}")
    except EnvironmentError as e:
        print(f"\n환경 오류:\n{e}", file=sys.stderr)
        sys.exit(1)
    except anthropic.AuthenticationError:
        print("\nAPI 인증 실패 - ANTHROPIC_API_KEY를 확인하세요.", file=sys.stderr)
        sys.exit(1)
    except anthropic.RateLimitError:
        print("\nAPI 한도 초과 - 잠시 후 재시도하세요.", file=sys.stderr)
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("\nAPI 연결 오류 - 네트워크를 확인하세요.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n실행 오류: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n예기치 않은 오류: {e}", file=sys.stderr)
        raise
