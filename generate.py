"""
Market Sentinel — Daily Briefing Generator
GitHub: https://github.com/bubblepangx/morning
매일 KST 06:50 자동 실행 → docs/index.html 발행
  ① Claude API + web_search → 브리핑 마크다운 생성
  ② yfinance → 시장 데이터 카드
  ③ FRED API → 경제지표 차트
  ④ 템플릿에 ①②③ 합쳐서 docs/index.html 출력
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

TODAY_STR = f"{date_ko} ({weekday_ko})"
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


# ═══════════════════════════════════════════
# PART A — Claude API 브리핑 (setup.sh 기반)
# ═══════════════════════════════════════════

SYSTEM_PROMPT = """당신은 Bloomberg·FT 25년 경력 선임 시장 기자 'Market Sentinel'입니다.
한국 기관투자자를 위한 매일 아침 7시 고급 시장 브리핑 전문가입니다.

[미국 시장 문체 원칙]
- 숫자는 반드시 포함하되, 숫자가 "왜 나왔는지"를 문장 안에서 반드시 설명한다
- "투자자들이 어떤 심리로 움직였는지", "이 움직임이 앞으로 어떤 의미인지"까지 해석한다
- 단락은 자연스럽게 흘러야 한다. 앞 단락의 결론이 다음 단락의 배경이 되도록 연결한다
- Bloomberg 어조 예시:
    "시장 참여자들은 ~에 주목했다"
    "이 움직임은 ~을 시사한다"
    "투자 심리가 ~로 기울었다"
    "~라는 분석이다" / "~라는 평가다"
    "~로 하락하며 ~을 뒷받침했다"
- 독자가 읽고 나서 "아, 그래서 시장이 이렇게 움직였구나" 하고 느껴야 한다
- 문장은 유려하고 읽기 부담이 없어야 한다. 과도한 수식어·나열 금지

[미국 시장 형식 원칙]
- 지수 종가 표 하나만 허용, 나머지는 전부 서술형 문단
- 각 문단은 3~5문장. 섹션 제목 아래 바로 본문 시작 (소제목 남발 금지)
- 마지막은 반드시 블록쿼트로 마무리:
  > **핵심 한 줄** [오늘 브리핑 전체를 관통하는 단 한 문장]

[한국·중국·일본 파트]
- 기존 방식 유지 (표 + 항목별 서술)

[사실 원칙]
- 모든 수치는 실시간 웹 검색으로 확인. 추측 수치 절대 금지
- 출처: Bloomberg, Reuters, CNBC, Yonhap, KRX, Fed, Treasury"""


def build_prompt() -> str:
    days = ["월", "화", "수", "목", "금", "토", "일"]
    d = now.strftime('%Y년 %m월 %d일')
    w = days[now.weekday()]
    t = now.strftime('%H:%M')
    return f"""오늘: {d} ({w}) {t} KST

웹 검색으로 최신 데이터를 수집한 후 아래 구조로 한국어 브리핑을 작성하세요.

반드시 검색:
- 미국 3대 지수 종가 (Dow, S&P500, Nasdaq, 러셀2000)
- S&P500·Nasdaq100 선물 현재가
- VIX, CNN Fear & Greed Index
- 10년물·2년물 미국 국채 수익률
- S&P500 11개 섹터 등락
- DXY, WTI 유가, 금 현물
- Fed 최신 발언·CME FedWatch 금리 확률
- 미국 시장 급등·급락 주요 종목
- 한국 KOSPI·KOSDAQ, 삼성전자·SK하이닉스·현대차·조선
- 중국 항셍·상하이·CSI300, 빅테크, AI 신기술
- 일본 닛케이225·TOPIX, BoJ·엔화 동향

출력 형식:

---
# ◆ Market Sentinel 모닝 브리핑
## {d} ({w}) 오전 7:00 KST

---

# 🇺🇸 PART 1 — 미국 시장

## 오늘의 시장

[지수 종가 — 표는 이것만]
| 지수 | 종가 | 등락 | 등락률 |
|---|---|---|---|
| S&P 500 | | | |
| 나스닥 종합 | | | |
| 다우존스 (DJIA) | | | |
| 러셀 2000 | | | |

**선물 현황 ({t} KST):** S&P500 선물 ___ / Nasdaq100 선물 ___

[표 아래부터 전부 서술형 문단으로 작성]

문단 1 — 장 전체 흐름: 어제 미국 시장의 전체적인 흐름을 서술. 어떤 이벤트가 시장을 이끌었는지, 투자자 심리가 어땠는지 3~5문장.

문단 2 — 섹터 분화: S&P500 11개 섹터 중 가장 강했던/약했던 섹터, 이유, 대표 종목 언급. 서술형 3~5문장.

문단 3 — 변동성·심리: VIX 수치와 CNN 공포탐욕지수를 문장 안에 녹여서 현재 시장 심리 해석. 풋/콜 비율이나 신용 스프레드 등 추가 심리 지표가 있다면 포함. 3~5문장.

문단 4 — 금·달러·유가: 금 현물, DXY(달러 인덱스), WTI 유가의 가격과 등락을 서술형으로. 왜 움직였는지 해석 포함. 3~5문장.

문단 5 — 금리·Fed: 10년물·2년물 수익률, 스프레드 변화, CME FedWatch 금리 확률, Fed 인사 발언을 서술형으로. 3~5문장.

문단 6 — 핵심 종목 이슈: 어제 가장 주목받은 5~7개 종목. 각 종목의 등락률·뉴스·투자 시사점을 서술형으로. 5~8문장.

---

## 섹터 성과 — 올라간 곳 vs 내려간 곳

[실시간 검색으로 오늘 실제 데이터 확인 후 아래 형식으로 작성]

**▲ 상승 섹터**
각 섹터마다 아래 형식으로 서술:
* 섹터명(영문) — 등락률 + 왜 올랐는지 1~2문장. 단순 수치 나열 금지.
  이유는 "~에 안도", "~ 리스크 프리미엄이 ~을 지지", "~ 수혜로 반등" 등 인과 중심으로.
  (예: 금융(Financials) — FOMC 의사록 이후 금리 동결 기조 확인에 안도, 대출 스프레드 환경 유리)
  (예: 에너지(Energy) — 이란·베네수엘라 리스크 프리미엄이 유가를 지지하며 YTD 기준 S&P500 내 상위권 유지)

**▼ 하락 섹터**
각 섹터마다 아래 형식으로 서술:
* 섹터명(영문) — 등락률 + 왜 밀렸는지 1~2문장. 인과 중심.
  (예: 기술(Information Technology) — AI 대체 공포가 이 섹터를 집중 압박 중이다)
  (예: 소비재(Consumer Discretionary) — 대형 기업 가이던스 충격으로 소비자 피로 우려 확산)

---

## 급등·급락 Top 5

**▲ 급등**
| 종목 | 등락률 | 이유 |
|---|---|---|
| (종목명) | +X% | EPS 컨센서스 상회 / M&A 수혜 / 투자의견 상향 등 한 줄 |

**▼ 급락**
| 종목 | 등락률 | 이유 |
|---|---|---|
| (종목명) | -X% | 어닝 쇼크 / 가이던스 하향 / M&A 희석 우려 등 한 줄 |

[작성 기준]
- 등락률 기준 상위 5개씩, 실제 오늘 데이터만 사용
- 이유는 투자자 심리와 연결: "EPS 컨센서스 40% 상회 + 가이던스 호조", "어닝 쇼크 + 분사 발표 이중 충격" 등
- 핀테크·미디어·방산 등 테마 흐름이 보이면 이유 칸에 테마 맥락도 포함

---

문단 7 — 내일 전망: 오늘 예정된 경제지표, 실적 발표, 이벤트. 시장 방향성 전망. 3~5문장.

> **핵심 한 줄:** [오늘 브리핑의 가장 중요한 메시지를 한 문장으로]

---

# 🇰🇷 PART 2 — 한국 시장

## 지수 현황
[KOSPI·KOSDAQ 또는 휴장 여부]

## 핵심 섹터
### 🔬 반도체 (삼성전자·SK하이닉스)
### 🚗 자동차 (현대차·기아)
### 🚢 조선·방산

## 오늘 시나리오
[개장 방향성 + 주목 포인트]

---

# 🇨🇳 PART 3 — 중국 시장

## 지수 현황
[항셍·상하이·CSI300]

## 빅테크 & 핫이슈
[알리바바·텐센트·바이두 + 정책 + AI]

## 매크로 & 리스크
[경제지표, 미중 관계, 위안화]

---

# 🇯🇵 PART 4 — 일본 시장

## 지수 현황
[닛케이225·TOPIX]

## 핵심 이슈
[BoJ·엔화·주요 기업]

---

## 📅 오늘의 글로벌 주요 일정

| 시간(KST) | 이벤트 | 중요도 |
|---|---|---|

---
*본 브리핑은 정보 제공 목적이며 투자 권유가 아닙니다.*
---"""


def generate() -> str:
    """Claude API + web_search 자동 반복 → 브리핑 마크다운 반환"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY 환경변수가 없습니다.\n"
            "GitHub Actions: Settings → Secrets → ANTHROPIC_API_KEY 등록 필요"
        )

    client = anthropic.Anthropic(api_key=api_key)
    print(f"  🤖 Claude API 호출 ({now.strftime('%H:%M:%S')} KST)")
    print("  🔍 웹 검색 자동 수행 중:")

    messages = [{"role": "user", "content": build_prompt()}]
    full_text = ""
    search_count = 0

    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        tool_uses = []
        for block in response.content:
            if block.type == "tool_use":
                tool_uses.append(block)
                search_count += 1
                print(f"     [{search_count:02d}] {block.input.get('query', '')}")
            elif block.type == "text" and block.text.strip():
                full_text = block.text

        if response.stop_reason == "end_turn" or not tool_uses:
            break

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tu.id, "content": ""}
                for tu in tool_uses
            ],
        })

    print(f"  ✅ 브리핑 완료 (검색 {search_count}회, {len(full_text)}자)")
    return full_text


def briefing_to_html(md_text: str) -> str:
    """마크다운 브리핑 → HTML 변환 (대시보드 삽입용)"""
    try:
        import markdown as md_lib
        return md_lib.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])
    except ImportError:
        safe = md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f"<pre style='white-space:pre-wrap'>{safe}</pre>"


# ═══════════════════════════════════════════
# PART B — 대시보드 데이터 (yfinance + FRED)
# ═══════════════════════════════════════════

import yfinance as yf

# ───────────────────────────────────────────
# 실시간 지표 fetch — 공포탐욕 / MOVE / Put·Call
# ───────────────────────────────────────────

def fetch_fear_greed():
    """CNN Fear & Greed + Crypto Fear & Greed (alternative.me)"""
    result = {"cnn": 50, "cnn_label": "Neutral",
              "cnn_prev": 50, "cnn_week": 50, "cnn_month": 50,
              "crypto": 50, "crypto_label": "Neutral",
              "crypto_prev": 50, "crypto_week": 50, "crypto_month": 50,
              "pcc_now": 0, "pcc_rating": ""}
    # CNN Fear & Greed
    try:
        r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                                  "Accept": "application/json"}, timeout=10)
        if r.status_code == 200 and r.text:
            d = r.json()
            fg = d.get("fear_and_greed", {})
            result["cnn"] = int(fg.get("score", 50))
            result["cnn_label"] = fg.get("rating", "Neutral").replace("_", " ").title()
            result["cnn_prev"] = int(fg.get("previous_close", result["cnn"]))
            result["cnn_week"] = int(fg.get("previous_1_week", result["cnn"]))
            result["cnn_month"] = int(fg.get("previous_1_month", result["cnn"]))
            # Put/Call Ratio (CNN API에 포함)
            pco = d.get("put_call_options", {})
            if "data" in pco and isinstance(pco["data"], list) and pco["data"]:
                result["pcc_now"] = round(pco["data"][-1].get("y", 0), 2)
                result["pcc_rating"] = pco["data"][-1].get("rating", "")
    except Exception as e:
        print(f"  ⚠️ CNN F&G err: {e}")

    # Crypto Fear & Greed (alternative.me — 무료 공개 API)
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=31", timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", [])
            if len(data) >= 1:
                result["crypto"] = int(data[0]["value"])
                result["crypto_label"] = data[0]["value_classification"]
            if len(data) >= 2:
                result["crypto_prev"] = int(data[1]["value"])
            if len(data) >= 7:
                result["crypto_week"] = int(data[7]["value"])
            if len(data) >= 30:
                result["crypto_month"] = int(data[30]["value"])
    except Exception as e:
        print(f"  ⚠️ Crypto F&G err: {e}")
    return result


def fetch_move_pcc():
    """MOVE Index (^MOVE via yfinance) & Put/Call Ratio (CNN API fallback)"""
    import yfinance as yf
    result = {"move_vals": [], "move_dates": [], "move_now": 0, "move_chg": 0,
              "pcc_vals": [], "pcc_dates": [], "pcc_now": 0, "pcc_chg": 0}
    try:
        # MOVE Index — 일봉 1년치 → 월별 마지막값 집계
        mv = yf.download("^MOVE", period="1y", interval="1d", progress=False, timeout=15)
        if len(mv) >= 2:
            cl = mv["Close"].dropna()
            from collections import OrderedDict as _OD
            monthly = _OD()
            for idx in range(len(cl)):
                key = str(cl.index[idx])[:7]
                monthly[key] = round(float(cl.iloc[idx]), 1)
            items = list(monthly.items())[-14:]
            result["move_dates"] = [k for k, v in items]
            result["move_vals"] = [v for k, v in items]
            if len(result["move_vals"]) >= 2:
                result["move_now"] = result["move_vals"][-1]
                result["move_chg"] = round(result["move_vals"][-1] - result["move_vals"][-2], 1)
    except Exception as e:
        print(f"  ⚠️ MOVE err: {e}")

    # Put/Call Ratio — CNN API에서 최근 14개월치 추출
    try:
        r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                         headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                                  "Accept": "application/json"}, timeout=10)
        if r.status_code == 200 and r.text:
            d = r.json()
            pco = d.get("put_call_options", {}).get("data", [])
            if pco:
                # 월별 마지막 값만 추출 (최근 14개)
                from collections import OrderedDict
                monthly = OrderedDict()
                for pt in pco:
                    ts = pt.get("x", 0) / 1000
                    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    key = dt.strftime("%Y-%m")
                    monthly[key] = round(pt.get("y", 0), 2)
                items = list(monthly.items())[-14:]
                result["pcc_dates"] = [k for k, v in items]
                result["pcc_vals"] = [v for k, v in items]
                if len(result["pcc_vals"]) >= 2:
                    result["pcc_now"] = result["pcc_vals"][-1]
                    result["pcc_chg"] = round(result["pcc_vals"][-1] - result["pcc_vals"][-2], 2)
    except Exception as e:
        print(f"  ⚠️ PCC err: {e}")
    return result



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


# ═══════════════════════════════════════════
# PART C — HTML 템플릿 패치 (브리핑 + 데이터 → 최종 HTML)
# ═══════════════════════════════════════════

def patch_html(src, mkt, fscript, briefing_html="", fg=None, move_pcc=None):
    """템플릿 HTML에서 동적 부분만 re.sub으로 교체 — format() 절대 사용 안함"""
    h = src
    if fg is None: fg = {}
    if move_pcc is None: move_pcc = {}

    # 날짜
    h = re.sub(r'\d{4}년 \d{2}월 \d{2}일 \([월화수목금토일]\)', TODAY_STR, h)

    # 브리핑 삽입 (briefing-content div 내부 교체)
    if briefing_html:
        h = re.sub(
            r'(<div id="briefing-content">)[\s\S]*?(</div>\s*</div>\s*<!-- 3\.)',
            lambda m: m.group(1) + briefing_html + m.group(2),
            h, count=1)

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

    # ── 공포탐욕 게이지 (실시간) ──
    cnn_val = fg.get("cnn", 50)
    cnn_label = fg.get("cnn_label", "Neutral")
    cnn_prev = fg.get("cnn_prev", cnn_val)
    cnn_week = fg.get("cnn_week", cnn_val)
    cnn_month = fg.get("cnn_month", cnn_val)
    crypto_val = fg.get("crypto", 50)
    crypto_label = fg.get("crypto_label", "Neutral")
    crypto_prev = fg.get("crypto_prev", crypto_val)
    crypto_week = fg.get("crypto_week", crypto_val)
    crypto_month = fg.get("crypto_month", crypto_val)

    # CNN 게이지 값 + 라벨
    h = re.sub(r"drawGauge\('gauge-cnn',\s*\d+,\s*'[^']*'\)",
               f"drawGauge('gauge-cnn', {cnn_val}, '{cnn_label}')", h)
    # Crypto 게이지 값 + 라벨
    h = re.sub(r"drawGauge\('gauge-crypto',\s*\d+,\s*'[^']*'\)",
               f"drawGauge('gauge-crypto', {crypto_val}, '{crypto_label}')", h)

    # CNN 히스토리 (어제/지난주/지난달)
    h = re.sub(
        r'(📺 CNN 공포탐욕지수.*?fg-history[^>]*>)\s*<span>어제.*?</span>\s*<span>지난주.*?</span>\s*<span>지난달.*?</span>',
        lambda m: m.group(1) +
        f'\n        <span>어제 <strong style="color:#374151">{cnn_prev}</strong></span>'
        f'\n        <span>지난주 <strong style="color:#374151">{cnn_week}</strong></span>'
        f'\n        <span>지난달 <strong style="color:#374151">{cnn_month}</strong></span>',
        h, flags=re.DOTALL)

    # Crypto 히스토리 (어제/지난주/지난달)
    h = re.sub(
        r'(₿ 크립토 공포탐욕지수.*?fg-history[^>]*>)\s*<span>어제.*?</span>\s*<span>지난주.*?</span>\s*<span>지난달.*?</span>',
        lambda m: m.group(1) +
        f'\n        <span>어제 <strong style="color:#374151">{crypto_prev}</strong></span>'
        f'\n        <span>지난주 <strong style="color:#374151">{crypto_week}</strong></span>'
        f'\n        <span>지난달 <strong style="color:#374151">{crypto_month}</strong></span>',
        h, flags=re.DOTALL)

    # ── MOVE Index & Put/Call Ratio (실시간) ──
    mv_dates = move_pcc.get("move_dates", [])
    mv_vals = move_pcc.get("move_vals", [])
    mv_now = move_pcc.get("move_now", 0)
    mv_chg = move_pcc.get("move_chg", 0)
    pcc_dates = move_pcc.get("pcc_dates", [])
    pcc_vals = move_pcc.get("pcc_vals", [])
    pcc_now = move_pcc.get("pcc_now", 0)
    pcc_chg = move_pcc.get("pcc_chg", 0)

    # MOVE 현재값 텍스트
    if mv_now:
        mv_arrow = "▲" if mv_chg >= 0 else "▼"
        h = re.sub(
            r'(ICE BofAML MOVE Index.*?현재 <strong[^>]*>)[\d.]+</strong>\s*[^|]*\|',
            f'\\g<1>{mv_now}</strong> &nbsp;{mv_arrow} {mv_chg:+.1f} 전일比 &nbsp;|',
            h)
    # Put/Call 현재값 텍스트
    if pcc_now:
        pcc_arrow = "▲" if pcc_chg >= 0 else "▼"
        h = re.sub(
            r'(현재 <strong[^>]*>)[\d.]+</strong>\s*[^|]*\|\s*1\.0 이상',
            f'\\g<1>{pcc_now}</strong> &nbsp;{pcc_arrow} {pcc_chg:+.2f} &nbsp;| 1.0 이상',
            h)

    # MOVE & PCC 차트 데이터 (JS 배열 교체)
    if mv_dates and mv_vals:
        mv_d_js = json.dumps(mv_dates)
        mv_v_js = json.dumps(mv_vals)
        h = re.sub(r"const xm=\[.*?\];\s*const mv=\[.*?\];\s*const pcc=\[.*?\];",
                   f"const xm={mv_d_js};\nconst mv={mv_v_js};\nconst pcc={json.dumps(pcc_vals if pcc_vals else [0]*len(mv_vals))};",
                   h)

    # FRED 스크립트 (템플릿 원본 or 이전 생성 결과 모두 매칭)
    h = re.sub(r'<script>\s*// ====== FRED 실시간 API[\s\S]+?loadFredData\(\);\s*</script>',
               '<script>\n' + fscript + '\n</script>', h)
    h = re.sub(r'<script>\s*const fredCfg=\{[\s\S]+?Plotly\.newPlot\(\'fred3\'[\s\S]+?\);\s*</script>',
               '<script>\n' + fscript + '\n</script>', h)

    return h


# ═══════════════════════════════════════════
# 엔트리포인트
# ═══════════════════════════════════════════

def main():
    print(f"START {TODAY_STR}")

    # ① Claude API 브리핑 생성
    briefing_html = ""
    try:
        briefing_md = generate()
        briefing_html = briefing_to_html(briefing_md)
        print("  📝 브리핑 HTML 변환 완료")
    except Exception as e:
        print(f"  ⚠️ 브리핑 생성 오류: {e}")
        briefing_html = f'<p style="color:#ef4444">브리핑 생성 실패: {e}</p>'

    # ② yfinance 시장 데이터
    try:
        mkt = fetch_market()
        print("  📊 yfinance ok")
    except Exception as e:
        print(f"  ⚠️ market err: {e}"); mkt = {}

    # ③ FRED 경제지표
    try:
        cpi = fred_yoy("CPIAUCSL"); core = fred_yoy("CPILFESL")
        un = fred_get("UNRATE"); ff = fred_get("FEDFUNDS")
        d10 = fred_get("DGS10"); d2 = fred_get("DGS2")
        fscript = fred_js(cpi, core, un, ff, d10, d2)
        print("  📈 FRED ok")
    except Exception as e:
        print(f"  ⚠️ fred err: {e}"); fscript = "// no fred"

    # ④ 실시간 지표: 공포탐욕 / MOVE·Put/Call
    try:
        fg_data = fetch_fear_greed()
        print(f"  😱 공포탐욕 ok — CNN:{fg_data['cnn']} Crypto:{fg_data['crypto']}")
    except Exception as e:
        print(f"  ⚠️ 공포탐욕 err: {e}"); fg_data = {}

    try:
        move_pcc_data = fetch_move_pcc()
        print(f"  📉 MOVE:{move_pcc_data.get('move_now',0)} PCC:{move_pcc_data.get('pcc_now',0)}")
    except Exception as e:
        print(f"  ⚠️ MOVE/PCC err: {e}"); move_pcc_data = {}

    # ⑤ 템플릿 패치 → docs/index.html (브리핑 + 카드 + 차트 + 실시간지표)
    tmpl_path = Path("templates/dashboard.html")
    if tmpl_path.exists():
        src = tmpl_path.read_text(encoding="utf-8")
        html = patch_html(src, mkt, fscript, briefing_html,
                          fg=fg_data, move_pcc=move_pcc_data)
        out = Path("docs/index.html")
        out.parent.mkdir(exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"  ✅ 대시보드 완료 {len(html):,} bytes → {out}")
    else:
        print("  ❌ templates/dashboard.html 없음 — 대시보드 스킵")

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
