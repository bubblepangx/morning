"""
Market Sentinel — Daily Briefing Generator
GitHub: https://github.com/bubblepangx/morning
매일 KST 06:50 자동 실행 → output/index.html 발행
"""

import anthropic
import os
import json
import sys
import re
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ───────────────────────────────────────────
# 시간 설정 (KST = UTC+9)
# ───────────────────────────────────────────
KST = timezone(timedelta(hours=9))
now  = datetime.now(KST)

WEEKDAY_KO  = ["월", "화", "수", "목", "금", "토", "일"]
date_ko     = now.strftime("%Y년 %m월 %d일")
weekday_ko  = WEEKDAY_KO[now.weekday()]
datetime_ko = f"{date_ko} ({weekday_ko}) 오전 {now.strftime('%H시 %M분')} KST"
file_date   = now.strftime("%Y%m%d")

# 기존 코드 호환용
TODAY_STR = f"{date_ko} ({weekday_ko})"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


# ───────────────────────────────────────────
# SYSTEM PROMPT
# ───────────────────────────────────────────
SYSTEM_PROMPT = """당신은 Bloomberg와 Financial Times에서 25년 경력을 쌓은 선임 시장 기자이자 분석가 'Market Sentinel'입니다.

[페르소나]
- 독자: 한국 기관투자자(연기금·자산운용사·증권사 리서치팀)와 고액자산가(UHNW)
- 문체: Bloomberg Morning Briefing 수준 — 세련되고 통찰력 있으며 전문적
- 핵심 원칙: 단순 수치 나열이 아닌 '시장 흐름의 이야기(narrative)'를 풀어낸다
- 철저히 중립적·사실 기반. 과장·투기적 표현·루머 절대 사용 금지
- 출처(Bloomberg, Reuters, CNBC, Yonhap, Fed, Treasury 등)는 문장 속에 자연스럽게 녹인다
- 섹션 간 인과관계 연결이 핵심
  예) "Fed 의사록 매파 톤 → 달러 강세 → 원/달러 상승 → 코스피 외국인 수급 변수"

[출력 규칙]
- 언어: 한국어
- 형식: Markdown (헤딩·표·볼드·이모지 허용)
- 모든 수치는 실시간 검색으로 확인된 실제 데이터만 사용
  (불확실 시 "확인 중" 또는 "전일 기준" 명시)
- 전체 분량: 2,000~2,800자"""


# ───────────────────────────────────────────
# USER PROMPT (9개 섹션 구조)
# ───────────────────────────────────────────
USER_PROMPT = f"""지금 시각은 {datetime_ko}입니다.

실시간 웹 검색 도구로 KST 06:50 기준 최신 데이터를 수집한 뒤,
아래 9개 섹션 구조에 맞춰 **Market Sentinel 모닝 브리핑**을 작성하세요.

검색 우선순위:
1. 미국 전일 마감 지수 (Dow·S&P500·Nasdaq·Russell2000 종가·등락률)
2. 현재 시점 미국 선물 (S&P500·Nasdaq100 선물)
3. VIX, CNN 공탐지수, 풋/콜 비율
4. 미 국채 10년물·2년물 수익률
5. WTI·Brent 원유, 금 현물 가격, 달러 인덱스(DXY)
6. 전일 미국 급등·급락 종목 Top5
7. 주요 기업 실적·M&A·규제 뉴스 (After-Hours 포함)
8. 중국 시장·빅테크 최신 소식 (DeepSeek·Alibaba·ByteDance 등)
9. 일본 니케이 마감·엔화·BOJ 동향
10. 오늘 예정 경제지표·실적 발표 일정

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ◆ Market Sentinel 모닝 브리핑
## {datetime_ko}

---

## 1. 📌 오늘의 시장 요약 (Lead)
*3~5줄 이내. 이것만 읽어도 오늘 시장의 핵심을 파악할 수 있어야 함.*
- 전날 미국장 마감 or overnight 최강 이벤트로 첫 문장 시작
- 오늘 아시아·한국 시장에 미칠 파급 효과 압축
- 오늘 하루 핵심 변수 1~2개 예고로 마무리

---

## 2. 🇺🇸 미국장 마감 정리 (Overnight Wrap)

### ① 3대 지수 + 소형주

| 지수 | 종가 | 전일 대비 | 등락률 |
|---|---|---|---|
| 다우존스 (DJIA) | | | |
| S&P 500 | | | |
| 나스닥 종합 | | | |
| 러셀 2000 | | | |

### ② 섹터 흐름
- **▲ 상승 섹터**: 섹터명 + 주도 종목 + 이유
- **▼ 하락 섹터**: 섹터명 + 주도 종목 + 이유
- 특이 패턴·섹터 로테이션 있으면 추가 서술

### ③ 시장 심리·매크로 지표

| 지표 | 수치 | 해석 |
|---|---|---|
| VIX (공포지수) | | 15↓안정 / 20↑경계 / 30↑공포 |
| CNN 공탐지수 | | 0~24극단공포→76~100극단탐욕 |
| 풋/콜 비율 | | 1.0↑하락베팅 / 0.7↓상승베팅 |
| S&P500 선물 (현재) | | |
| 나스닥100 선물 (현재) | | |
| WTI 원유 | | |
| 금 현물 (XAU/USD) | | |
| 달러 인덱스 (DXY) | | |

---

## 3. 💵 금리·매크로 환경

### ① 미 국채 수익률

| 구분 | 수익률 | 전일 대비 | 해석 |
|---|---|---|---|
| 10년물 | | | |
| 2년물 | | | |
| 10-2년 스프레드 | | | |

### ② Fed 금리 경로
- **현재 기준금리 목표범위**:
- **CME 페드워치** — 다음 회의 동결 확률 / 인하 확률:
- **최근 Fed 발언 또는 의사록 요약**:

### ③ 핵심 리스크 2~3가지
*리스크명 / 현황 / 시장 영향 형식으로 서술*

---

## 4. 🔥 주요 기업 핫이슈 (Hot Company Stories)
*After-Hours 포함, 시장을 가장 크게 움직인 미국 대형주 5~7개*

각 기업마다:
**기업명 (티커)** — 주가 변동 (등락률, 종가 or AH 가격)
- 이슈 요약: 실적·가이던스·M&A·규제·CEO 발언 등
- 투자자 심리: 왜 이렇게 반응했는지 인과관계 설명

---

## 5. 📈📉 급등·급락 Top 5

### ▲ 급등 Top 5

| 순위 | 종목 (티커) | 등락률 | 핵심 이유 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

### ▼ 급락 Top 5

| 순위 | 종목 (티커) | 등락률 | 핵심 이유 |
|---|---|---|---|
| 1 | | | |
| 2 | | | |
| 3 | | | |
| 4 | | | |
| 5 | | | |

**흐름 연결 분석** (2~3줄):
급등·급락 종목들이 오늘 시장 전체 내러티브와 어떻게 연결되는지

---

## 6. 🇰🇷 한국 시장 관련 오버나이트 소식
*오늘 코스피·코스닥에 영향 줄 소식 중심*

**IWM (러셀2000 ETF)**: 현재가 / 등락률 / 52주 범위 대비 위치

**반도체**: 삼성전자·SK하이닉스 관련 해외 뉴스 (공급망·수요·규제·HBM 등)

**자동차**: 현대차·기아 관련 (관세·EV 수요·리콜·해외 판매 등)

**조선**: 한화오션·HD현대 등 글로벌 수주·발주 뉴스

**코스피·코스닥 주목 포인트**: 미국 오버나이트 흐름이 한국 어느 섹터에 긍정/부정으로 전이될지 2~3줄

---

## 7. 🇨🇳 중국 시장 오버나이트 소식

**시장 지수**: 상하이종합 / 항셍 전일 마감 수치

**빅테크·AI 신기술**:
- Alibaba·ByteDance·DeepSeek·Tencent·Baidu 최신 소식
- 신규 AI 모델·기술 발표, 규제 변화

**정책·매크로**:
- 정부 경기부양·산업정책·위안화 동향·PBOC 움직임

**시장 관전 포인트**:
- 중국발 변수가 미국·한국 시장(반도체·소재·에너지)에 미칠 파급 가능성

---

## 8. 🇯🇵 일본 시장 오버나이트 소식
*5줄 이내 압축*

- 니케이225 전일 마감: 수치 + 등락률 + 한 줄 요약
- 주도 상승주 / 주도 하락주 (각 1~2개)
- 엔/달러 환율 동향 및 의미
- BOJ 정책·정치 이슈 (있는 경우)
- 오늘 아시아 시장에 던지는 시사점

---

## 9. 📋 오늘 주목할 이벤트 & Outlook

### 오늘({date_ko}) 핵심 일정

| 시간(KST) | 이벤트 | 영향도 |
|---|---|---|
| | | 🔴상/🟡중/🟢하 |

### 내일 예고
내일 예정된 주요 이벤트 1~3개 미리 언급

### 투자자 대응 관점
- **오늘 시장 예상 방향성**: (상승/하락/박스권 + 근거)
- **리스크 시나리오** (if-then 형식):
  예) "만약 ○○ 지표가 예상 하회 시 → △△ 섹터 매도 압력"
- **포지션 전략 팁** (특정 종목 추천 금지, 섹터·전략 수준):

---
*본 브리핑은 Bloomberg, Reuters, CNBC, Yahoo Finance, Nikkei Asia 등
공개 데이터 기반 정보 제공 목적이며 투자 권유가 아닙니다.*
*모든 수치 기준: {datetime_ko}*
"""


# ───────────────────────────────────────────
# HTML 변환 (마크다운 → 뉴스 페이지)
# ───────────────────────────────────────────
def to_html(md: str) -> str:
    """마크다운 브리핑을 완성된 HTML 뉴스 페이지로 변환"""
    try:
        import markdown as md_lib
        body = md_lib.markdown(md, extensions=["tables", "fenced_code", "nl2br"])
    except ImportError:
        # markdown 라이브러리 없을 때 기본 처리
        body = md.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
        body = f"<pre style='white-space:pre-wrap'>{body}</pre>"

    year = now.year
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta property="og:title" content="Market Sentinel — {date_ko}">
  <meta property="og:description" content="Bloomberg/FT 수준 한국어 시장 브리핑 · {date_ko}">
  <meta name="twitter:card" content="summary">
  <title>Market Sentinel — {date_ko}</title>
  <style>
    :root{{
      --bg:#080d18;--surface:#0f1729;--border:#1e2d45;
      --text:#e2e8f0;--muted:#64748b;--accent:#3b82f6;
      --green:#10b981;--red:#ef4444;--gold:#f59e0b;
      --font:'Pretendard','Apple SD Gothic Neo','Noto Sans KR',sans-serif;
    }}
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:var(--bg);color:var(--text);font-family:var(--font);
         font-size:15px;line-height:1.8;padding:0 1rem 3rem}}
    a{{color:var(--accent);text-decoration:none}}

    /* ── 헤더 ── */
    .site-header{{
      max-width:860px;margin:0 auto;
      padding:2rem 0 1.5rem;
      border-bottom:2px solid var(--accent);
      margin-bottom:2.5rem;
    }}
    .site-header .badge{{
      font-size:.7rem;letter-spacing:.18em;text-transform:uppercase;
      color:var(--accent);margin-bottom:.5rem;
    }}
    .site-header h1{{font-size:1.65rem;font-weight:800;color:#fff;margin-bottom:.3rem}}
    .site-header .meta{{font-size:.78rem;color:var(--muted)}}

    /* ── 본문 카드 ── */
    .card{{
      max-width:860px;margin:0 auto;
      background:var(--surface);border:1px solid var(--border);
      border-radius:14px;padding:2.2rem 2.8rem;
    }}

    /* ── 마크다운 요소 ── */
    .card h1{{font-size:1.4rem;color:#fff;margin:2rem 0 .8rem;border-bottom:1px solid var(--border);padding-bottom:.5rem}}
    .card h2{{font-size:1.2rem;color:var(--accent);margin:1.8rem 0 .6rem}}
    .card h3{{font-size:1rem;color:#cbd5e1;margin:1.2rem 0 .4rem}}
    .card p{{margin-bottom:.9rem;color:var(--text)}}
    .card strong{{color:#fff}}
    .card em{{color:var(--muted)}}
    .card ul,.card ol{{padding-left:1.4rem;margin-bottom:.9rem}}
    .card li{{margin-bottom:.35rem}}
    .card hr{{border:none;border-top:1px solid var(--border);margin:1.8rem 0}}
    .card blockquote{{
      border-left:3px solid var(--accent);
      padding:.6rem 1rem;
      background:#0d1826;
      border-radius:0 8px 8px 0;
      margin:.8rem 0;
      color:var(--muted);
    }}
    .card code{{
      background:#1e2d45;padding:.15em .4em;
      border-radius:4px;font-size:.88em;
    }}

    /* ── 표 ── */
    .card table{{width:100%;border-collapse:collapse;margin:1rem 0;font-size:.9rem}}
    .card th{{
      background:#162033;color:var(--accent);
      padding:.55rem .8rem;text-align:left;
      border-bottom:2px solid var(--border);
      font-weight:600;white-space:nowrap;
    }}
    .card td{{
      padding:.5rem .8rem;border-bottom:1px solid var(--border);
      vertical-align:top;
    }}
    .card tr:hover td{{background:#0d1826}}

    /* ── 이모지 섹션 헤딩 색상 ── */
    .card h2:has(span.us){{color:#60a5fa}}
    .card h2:has(span.kr){{color:var(--gold)}}

    /* ── 푸터 ── */
    footer{{
      max-width:860px;margin:1.8rem auto 0;
      text-align:center;font-size:.73rem;color:var(--muted);
    }}
    footer a{{color:var(--muted)}}

    /* ── 반응형 ── */
    @media(max-width:600px){{
      .card{{padding:1.2rem 1rem}}
      .site-header h1{{font-size:1.2rem}}
      .card table{{font-size:.8rem}}
      .card th,.card td{{padding:.4rem .5rem}}
    }}
  </style>
</head>
<body>
  <header class="site-header">
    <div class="badge">▲ Market Sentinel · Daily Briefing</div>
    <h1>{date_ko} ({weekday_ko}) 모닝 브리핑</h1>
    <div class="meta">
      Generated {now.strftime('%Y-%m-%d %H:%M')} KST &nbsp;·&nbsp;
      Powered by Claude AI &nbsp;·&nbsp;
      <a href="https://github.com/bubblepangx/morning" target="_blank">GitHub</a>
    </div>
  </header>

  <main class="card">
    {body}
  </main>

  <footer>
    본 브리핑은 공개 데이터 기반 정보 제공 목적이며 투자 권유가 아닙니다.<br>
    © {year} Market Sentinel &nbsp;·&nbsp;
    <a href="https://github.com/bubblepangx/morning">bubblepangx/morning</a>
  </footer>
</body>
</html>"""


# ───────────────────────────────────────────
# API 호출 (Claude + 웹 검색)
# ───────────────────────────────────────────
def generate() -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY 환경변수가 없습니다.\n"
            "GitHub Actions: Settings → Secrets → ANTHROPIC_API_KEY 등록 필요"
        )

    client = anthropic.Anthropic(api_key=api_key)
    print(f"[{now.strftime('%H:%M')} KST] 브리핑 생성 시작 — {date_ko}")

    msg = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": USER_PROMPT}],
    )

    text = msg.content[0].text
    print(f"[{now.strftime('%H:%M')} KST] 완료 — {msg.usage.output_tokens:,} tokens")
    return text


# ───────────────────────────────────────────
# 저장
# ───────────────────────────────────────────
def save(briefing: str):
    out = Path("output")
    out.mkdir(exist_ok=True)

    # 날짜별 마크다운
    md_path = out / f"{file_date}.md"
    md_path.write_text(briefing, encoding="utf-8")

    # 날짜별 HTML
    html       = to_html(briefing)
    html_path  = out / f"{file_date}.html"
    html_path.write_text(html, encoding="utf-8")

    # 최신본 (GitHub Pages 진입점)
    index_path = out / "index.html"
    index_path.write_text(html, encoding="utf-8")

    # 최신 목록 JSON (아카이브 페이지용)
    meta_path = out / "meta.json"
    history   = []
    if meta_path.exists():
        try:
            history = json.loads(meta_path.read_text())
        except Exception:
            history = []

    entry = {"date": file_date, "label": date_ko, "file": f"{file_date}.html"}
    if not any(e["date"] == file_date for e in history):
        history.insert(0, entry)
    history = history[:60]          # 최근 60일치만 보관
    meta_path.write_text(json.dumps(history, ensure_ascii=False, indent=2))

    print(f"  ✅ {md_path}")
    print(f"  ✅ {html_path}")
    print(f"  ✅ {index_path}  ← GitHub Pages 진입점")
    print(f"  ✅ {meta_path}")


# ───────────────────────────────────────────
# 기존 대시보드 코드 (yfinance + FRED + 템플릿)
# ───────────────────────────────────────────
import yfinance as yf

SYMS = {"SP500":"^GSPC","NASDAQ":"^IXIC","DOW":"^DJI","RUSSELL":"^RUT",
        "VIX":"^VIX","GOLD":"GC=F","SILVER":"SI=F","OIL":"CL=F","COPPER":"HG=F",
        "DXY":"DX-Y.NYB","BTC":"BTC-USD","ETH":"ETH-USD","SOL":"SOL-USD",
        "KRW":"KRW=X","JPY":"JPY=X","CNY":"CNY=X"}

def fetch_market():
    data = {k:{"price":0,"change":0} for k in SYMS}
    try:
        raw = yf.download(list(SYMS.values()), period="2d", interval="1d",
                          group_by="ticker", progress=False, timeout=30)
        for name, sym in SYMS.items():
            try:
                try:
                    cl = raw[sym]["Close"].dropna()
                except (KeyError, TypeError):
                    cl = raw["Close"].dropna()
                if len(cl)>=2:
                    c,p = float(cl.iloc[-1]), float(cl.iloc[-2])
                    data[name] = {"price":c,"change":(c-p)/p*100}
                elif len(cl)==1:
                    data[name] = {"price":float(cl.iloc[-1]),"change":0.0}
            except: pass
    except Exception as e:
        print(f"yfinance error: {e}")
    return data

def card(label, d, pre="", dec=2):
    p,c = d.get("price",0), d.get("change",0)
    ps = f"{pre}{p:,.{dec}f}" if p else "N/A"
    col = "#e53e3e" if c>=0 else "#3182ce"
    arr = "▲" if c>=0 else "▼"
    return (f'<div class="card"><div class="card-label">{label}</div>'
            f'<div class="card-value">{ps}</div>'
            f'<div class="card-change" style="color:{col}">{arr} {abs(c):.2f}%</div></div>')

def fred_get(sid, limit=36):
    if not FRED_API_KEY: return {"x":[],"y":[]}
    try:
        r = requests.get(FRED_URL, params={"series_id":sid,"api_key":FRED_API_KEY,
            "file_type":"json","sort_order":"desc","limit":limit}, timeout=15)
        d = r.json()
        if "observations" not in d: return {"x":[],"y":[]}
        obs = [o for o in d["observations"] if o["value"]!="."]
        obs.reverse()
        return {"x":[o["date"] for o in obs],"y":[float(o["value"]) for o in obs]}
    except Exception as e:
        print(f"FRED {sid}: {e}"); return {"x":[],"y":[]}

def fred_yoy(sid):
    if not FRED_API_KEY: return {"x":[],"y":[]}
    try:
        r = requests.get(FRED_URL, params={"series_id":sid,"api_key":FRED_API_KEY,
            "file_type":"json","observation_start":"2022-01-01","sort_order":"asc"}, timeout=15)
        d = r.json()
        if "observations" not in d: return {"x":[],"y":[]}
        obs = [o for o in d["observations"] if o["value"]!="."]
        vm = {o["date"]:float(o["value"]) for o in obs}
        rx,ry = [],[]
        for o in obs:
            dt=o["date"]
            if dt<"2023-01-01": continue
            prev_dt = f"{int(dt[:4])-1}{dt[4:]}"
            cands = [k for k in vm if k<=prev_dt]
            if not cands: continue
            prev=vm[max(cands)]
            if prev: rx.append(dt); ry.append(round((vm[dt]-prev)/prev*100,2))
        return {"x":rx,"y":ry}
    except Exception as e:
        print(f"FRED yoy {sid}: {e}"); return {"x":[],"y":[]}

def fred_js(cpi, core, un, ff, d10, d2):
    def ja(d): return json.dumps(d)
    x0=cpi["x"][0] if cpi["x"] else ""
    x1=cpi["x"][-1] if cpi["x"] else ""
    lines = [
        "const fredCfg={margin:{t:10,b:40,l:50,r:10},legend:{orientation:'h',y:-0.25,font:{size:11}},paper_bgcolor:'transparent',plot_bgcolor:'transparent',xaxis:{gridcolor:'#f1f5f9',tickfont:{size:10}},yaxis:{gridcolor:'#f1f5f9',tickfont:{size:10}}};",
        "const fredOpt={responsive:true,displayModeBar:false};",
        "Plotly.newPlot('fred1',[",
        f"  {{x:{ja(cpi['x'])},y:{ja(cpi['y'])},name:'CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},",
        f"  {{x:{ja(core['x'])},y:{ja(core['y'])},name:'Core CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}",
        f"],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}},shapes:[{{type:'line',x0:'{x0}',x1:'{x1}',y0:2,y1:2,line:{{color:'#9ca3af',width:1,dash:'dot'}}}}]}},fredOpt);",
        "Plotly.newPlot('fred2',[",
        f"  {{x:{ja(un['x'])},y:{ja(un['y'])},name:'실업률',type:'scatter',mode:'lines',line:{{color:'#7c3aed',width:2}}}},",
        f"  {{x:{ja(ff['x'])},y:{ja(ff['y'])},name:'Fed Funds',type:'scatter',mode:'lines',line:{{color:'#d97706',width:2}}}}",
        "],{...fredCfg,yaxis:{...fredCfg.yaxis,ticksuffix:'%'}},fredOpt);",
        "Plotly.newPlot('fred3',[",
        f"  {{x:{ja(d10['x'])},y:{ja(d10['y'])},name:'10년물',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},",
        f"  {{x:{ja(d2['x'])},y:{ja(d2['y'])},name:'2년물',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}",
        "],{...fredCfg,yaxis:{...fredCfg.yaxis,ticksuffix:'%'}},fredOpt);",
    ]
    return "\n".join(lines)

def patch_html(src, mkt, fscript):
    """템플릿 HTML에서 동적 부분만 re.sub으로 교체 — format() 절대 사용 안함"""
    h = src

    # 날짜
    h = re.sub(r'\d{4}년 \d{2}월 \d{2}일 \([월화수목금토일]\)', TODAY_STR, h)

    # 지수 카드
    idx = (card("S&P 500",mkt.get("SP500",{})) +
           card("NASDAQ",mkt.get("NASDAQ",{})) +
           card("Dow Jones",mkt.get("DOW",{})) +
           card("Russell 2000",mkt.get("RUSSELL",{})) +
           card("VIX",mkt.get("VIX",{})))
    h = re.sub(
        r'(<!-- 3\. 주요 지수 카드[\s\S]*?<div class="cards">)[\s\S]*?(</div>\s*</div>\s*<!-- 4\.)',
        lambda m: m.group(1) + idx + m.group(2), h, count=1)

    # 원자재 카드
    com = (card("금 (XAU/USD)",mkt.get("GOLD",{}),"$",0) +
           card("은 (XAG/USD)",mkt.get("SILVER",{}),"$",2) +
           card("WTI 원유",mkt.get("OIL",{}),"$",2) +
           card("구리",mkt.get("COPPER",{}),"$",3))
    h = re.sub(
        r'(원자재 — 가격 스냅샷</div>\s*<div class="cards">)[\s\S]*?(</div>\s*<div class="subsection-label"[^>]*>원자재 — TradingView)',
        lambda m: m.group(1) + com + m.group(2), h, count=1)

    # 환율 카드
    fx = (card("달러인덱스",mkt.get("DXY",{})) +
          card("원/달러",mkt.get("KRW",{})) +
          card("엔/달러",mkt.get("JPY",{})) +
          card("위안/달러",mkt.get("CNY",{}),dec=3))
    h = re.sub(
        r'(subsection-label">환율</div>\s*<div class="cards">)[\s\S]*?(</div>\s*<div class="subsection-label"[^>]*>원자재)',
        lambda m: m.group(1) + fx + m.group(2), h, count=1)

    # 공포탐욕 게이지
    vix_val = mkt.get("VIX",{}).get("price",25)
    fg = max(5, min(95, int(100 - vix_val * 2.5)))
    h = re.sub(r"drawGauge\('gauge-cnn',\s*\d+,", f"drawGauge('gauge-cnn', {fg},", h)

    # FRED 스크립트 (템플릿 원본 or 이전 생성 결과 모두 매칭)
    h = re.sub(r'<script>\s*// ====== FRED 실시간 API[\s\S]+?loadFredData\(\);\s*</script>',
               '<script>\n' + fscript + '\n</script>', h)
    h = re.sub(r'<script>\s*const fredCfg=\{[\s\S]+?Plotly\.newPlot\(\'fred3\'[\s\S]+?\);\s*</script>',
               '<script>\n' + fscript + '\n</script>', h)

    return h


# ───────────────────────────────────────────
# 엔트리포인트
# ───────────────────────────────────────────
def main():
    print(f"START {TODAY_STR}")

    # ① 새 브리핑 생성 (Claude + 웹 검색) → output/
    try:
        briefing = generate()
        save(briefing)
        print("브리핑 생성 완료")
    except Exception as e:
        print(f"브리핑 생성 오류: {e}")

    # ② 기존 대시보드 업데이트 (yfinance + FRED) → docs/index.html
    try:
        mkt = fetch_market()
    except Exception as e:
        print(f"market err: {e}"); mkt = {}

    try:
        cpi = fred_yoy("CPIAUCSL"); core = fred_yoy("CPILFESL")
        un = fred_get("UNRATE"); ff = fred_get("FEDFUNDS")
        d10 = fred_get("DGS10"); d2 = fred_get("DGS2")
        fscript = fred_js(cpi, core, un, ff, d10, d2)
        print("FRED ok")
    except Exception as e:
        print(f"fred err: {e}"); fscript = "// no fred"

    tmpl_path = Path("templates/dashboard.html")
    if tmpl_path.exists():
        src = tmpl_path.read_text(encoding="utf-8")
        html = patch_html(src, mkt, fscript)
        out = Path("docs/index.html")
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"대시보드 완료 {len(html):,}bytes")
    else:
        print("templates/dashboard.html 없음 — 대시보드 스킵")

    print(f"DONE {TODAY_STR}")


if __name__ == "__main__":
    try:
        main()
    except EnvironmentError as e:
        print(f"\n❌ 환경 오류:\n{e}")
        sys.exit(1)
    except anthropic.AuthenticationError:
        print("\n❌ API 인증 실패 — ANTHROPIC_API_KEY를 확인하세요.")
        sys.exit(1)
    except anthropic.RateLimitError:
        print("\n❌ API 한도 초과 — 잠시 후 재시도하세요.")
        sys.exit(1)
    except anthropic.APIConnectionError:
        print("\n❌ API 연결 오류 — 네트워크를 확인하세요.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 예기치 않은 오류: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
