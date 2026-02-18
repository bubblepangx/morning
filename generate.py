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

규칙:
- 모든 수치는 반드시 실시간 웹 검색으로 확인
- 출처: Bloomberg, Reuters, CNBC, Yonhap, KRX, Fed, Treasury 등
- 중립·사실 기반, 과장·투기적 표현 금지
- Bloomberg 아침 브리핑 수준의 세련된 문체
- 섹터 간 인과관계와 흐름을 이야기로 연결"""


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

## 1. Lead
[오늘의 핵심 overnight 이벤트 한 줄 압축]

## 2. 3대 지수 종가

| 지수 | 종가 | 등락 | 등락률 |
|---|---|---|---|
| 다우존스 (DJIA) | | | |
| S&P 500 | | | |
| 나스닥 종합 | | | |
| 러셀 2000 | | | |

**선물 현황:** S&P500 선물 ___ / Nasdaq100 선물 ___

## 3. 시장 심리 지표

| 지표 | 수치 | 해석 |
|---|---|---|
| VIX | | |
| CNN 공탐지수 | | |
| DXY | | |
| WTI | | |
| 금 현물 | | |

## 4. 섹터 성과
**▲ 상승:** [섹터명 + 등락률 + 이유]
**▼ 하락:** [섹터명 + 등락률 + 이유]

## 5. 금리·매크로
[10년물·2년물 + Fed 기대 + 핵심 리스크]

## 6. 주요 기업 핫이슈
[5~7개 기업, 종목·등락률·뉴스·투자심리]

## 7. 급등·급락 Top 5

**▲ 급등**
| 종목 | 등락률 | 이유 |
|---|---|---|

**▼ 급락**
| 종목 | 등락률 | 이유 |
|---|---|---|

## 8. 오늘 Outlook
[예정 이벤트 + 방향성 전망]

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

def patch_html(src, mkt, fscript, briefing_html=""):
    """템플릿 HTML에서 동적 부분만 re.sub으로 교체 — format() 절대 사용 안함"""
    h = src

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

    # ④ 템플릿 패치 → docs/index.html (브리핑 + 카드 + 차트)
    tmpl_path = Path("templates/dashboard.html")
    if tmpl_path.exists():
        src = tmpl_path.read_text(encoding="utf-8")
        html = patch_html(src, mkt, fscript, briefing_html)
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
