"""
Daily US Market Dashboard — 자동 생성 스크립트
매일 새벽 GitHub Actions에서 실행
"""

import os
import json
import datetime
import requests
import yfinance as yf
import anthropic
from zoneinfo import ZoneInfo
from pathlib import Path

# ── 설정 ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
FRED_API_KEY      = os.environ["FRED_API_KEY"]
KST               = ZoneInfo("Asia/Seoul")
TODAY             = datetime.datetime.now(KST)
TODAY_STR         = TODAY.strftime("%Y년 %m월 %d일 (%a)").replace(
    "Mon","월").replace("Tue","화").replace("Wed","수").replace(
    "Thu","목").replace("Fri","금").replace("Sat","토").replace("Sun","일")
TODAY_EN          = TODAY.strftime("%Y-%m-%d")

claude  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
FRED    = "https://api.stlouisfed.org/fred/series/observations"

# ── 1. 시장 데이터 수집 (yfinance) ────────────────────
def fetch_market_data():
    tickers = {
        "SP500":   "^GSPC",
        "NASDAQ":  "^IXIC",
        "DOW":     "^DJI",
        "RUSSELL": "^RUT",
        "VIX":     "^VIX",
        "GOLD":    "GC=F",
        "SILVER":  "SI=F",
        "OIL":     "CL=F",
        "COPPER":  "HG=F",
        "DXY":     "DX-Y.NYB",
        "BTC":     "BTC-USD",
        "ETH":     "ETH-USD",
        "SOL":     "SOL-USD",
        "KRW":     "KRW=X",
        "JPY":     "JPY=X",
        "CNY":     "CNY=X",
    }
    data = {}
    for name, sym in tickers.items():
        try:
            t = yf.Ticker(sym)
            h = t.history(period="2d")
            if len(h) >= 2:
                cur  = h["Close"].iloc[-1]
                prev = h["Close"].iloc[-2]
                chg  = (cur - prev) / prev * 100
                data[name] = {"price": cur, "change": chg}
            elif len(h) == 1:
                data[name] = {"price": h["Close"].iloc[-1], "change": 0.0}
        except Exception as e:
            print(f"  ⚠️  {name} fetch 실패: {e}")
            data[name] = {"price": 0, "change": 0}
    return data

def fmt_price(v, prefix="", decimals=2):
    if v == 0: return "N/A"
    return f"{prefix}{v:,.{decimals}f}"

def fmt_change(c):
    if c > 0:
        return f'<span style="color:#e53e3e">▲ {c:.2f}%</span>'
    elif c < 0:
        return f'<span style="color:#3182ce">▼ {abs(c):.2f}%</span>'
    return f'<span style="color:#9ca3af">─ {c:.2f}%</span>'

# ── 2. FRED 경제지표 ───────────────────────────────────
def fetch_fred(series_id, limit=36):
    try:
        r = requests.get(FRED, params={
            "series_id": series_id, "api_key": FRED_API_KEY,
            "file_type": "json", "sort_order": "desc", "limit": limit
        }, timeout=15)
        data = r.json()
        if "observations" not in data:
            print(f"  ⚠️  FRED {series_id} 응답 이상: {list(data.keys())}")
            return {"x": [], "y": []}
        obs = [o for o in data["observations"] if o["value"] != "."]
        obs.reverse()
        return {
            "x": [o["date"] for o in obs],
            "y": [float(o["value"]) for o in obs]
        }
    except Exception as e:
        print(f"  ⚠️  FRED {series_id} 실패: {e}")
        return {"x": [], "y": []}

def fred_yoy(series_id):
    """YoY% 계산용 — 2년치 가져와서 계산"""
    try:
        r = requests.get(FRED, params={
            "series_id": series_id, "api_key": FRED_API_KEY,
            "file_type": "json", "observation_start": "2022-01-01",
            "sort_order": "asc"
        }, timeout=15)
        data = r.json()
        if "observations" not in data:
            print(f"  ⚠️  FRED YoY {series_id} 응답 이상: {list(data.keys())}")
            return {"x": [], "y": []}
        obs = [o for o in data["observations"] if o["value"] != "."]
        result_x, result_y = [], []
        val_map = {o["date"]: float(o["value"]) for o in obs}
        dates = [o["date"] for o in obs if o["date"] >= "2023-01-01"]
        for d in dates:
            cur = val_map.get(d)
            prev_date = f"{int(d[:4])-1}{d[4:]}"
            prev_candidates = [k for k in val_map if k <= prev_date]
            if not prev_candidates: continue
            prev = val_map[max(prev_candidates)]
            if prev and prev != 0:
                result_x.append(d)
                result_y.append(round((cur - prev) / prev * 100, 2))
        return {"x": result_x, "y": result_y}
    except Exception as e:
        print(f"  ⚠️  FRED YoY {series_id} 실패: {e}")
        return {"x": [], "y": []}

# ── 3. Claude API 콘텐츠 생성 ──────────────────────────
def claude_generate(system_prompt, user_prompt, max_tokens=2000):
    msg = claude.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    return msg.content[0].text

JOURNALIST_SYSTEM = """당신은 월가와 글로벌 매크로 시장을 20년간 취재한 한국의 베테랑 경제 전문 기자입니다.
숫자와 데이터를 인간적인 언어로 풀어내고, 시장의 감정과 구조적 흐름을 동시에 읽어냅니다.
공포를 조장하지 않되, 현실을 직시하는 맑은 눈으로 씁니다.
기자 특유의 절제된 문체, 과장 없이 사실 중심, 독자가 '아, 그렇구나' 할 수 있는 인사이트를 담습니다."""

def gen_daily_summary(mkt):
    """데일리 시황 생성"""
    sp  = mkt.get("SP500",  {})
    nq  = mkt.get("NASDAQ", {})
    dw  = mkt.get("DOW",    {})
    ru  = mkt.get("RUSSELL",{})
    vix = mkt.get("VIX",    {})
    gold= mkt.get("GOLD",   {})
    oil = mkt.get("OIL",    {})
    dxy = mkt.get("DXY",    {})

    context = f"""오늘 날짜: {TODAY_STR}
주요 지수 마감:
- S&P 500: {fmt_price(sp.get('price',0), decimals=2)} ({sp.get('change',0):+.2f}%)
- NASDAQ: {fmt_price(nq.get('price',0), decimals=2)} ({nq.get('change',0):+.2f}%)
- 다우존스: {fmt_price(dw.get('price',0), decimals=2)} ({dw.get('change',0):+.2f}%)
- 러셀2000: {fmt_price(ru.get('price',0), decimals=2)} ({ru.get('change',0):+.2f}%)
- VIX: {fmt_price(vix.get('price',0), decimals=2)} ({vix.get('change',0):+.2f}%)
- 금: ${fmt_price(gold.get('price',0))} ({gold.get('change',0):+.2f}%)
- WTI: ${fmt_price(oil.get('price',0))} ({oil.get('change',0):+.2f}%)
- DXY: {fmt_price(dxy.get('price',0), decimals=2)} ({dxy.get('change',0):+.2f}%)"""

    prompt = f"""{context}

위 데이터를 바탕으로 오늘의 미국 시장 마감 시황을 작성해주세요.

형식:
1. 첫 줄: 헤드라인 (신문 제목처럼, 30자 내외)
2. 본문: 7~8문단, 각 문단 3~4문장
   - 지수별 마감 흐름과 주요 등락 원인
   - 섹터별 차별화 흐름
   - 채권·금리 움직임
   - 달러·금·원자재 동향
   - 다음 주 주목 이벤트
3. 마지막: "핵심 한 줄" 요약 (50자 내외)

순수 텍스트로만, HTML 태그 없이."""

    result = claude_generate(JOURNALIST_SYSTEM, prompt, max_tokens=2500)
    lines = result.strip().split("\n")
    headline = lines[0].strip().lstrip("#").strip()
    
    # 핵심 한 줄 분리
    keyline = ""
    body_lines = []
    for line in lines[1:]:
        if "핵심 한 줄" in line or line.startswith("**핵심"):
            keyline = line.replace("**핵심 한 줄**", "").replace("핵심 한 줄:", "").strip(" :—-*")
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return headline, body, keyline

def gen_issues(mkt):
    """주요 이슈 10개 생성"""
    prompt = f"""오늘 날짜: {TODAY_STR}

주요 시장 데이터:
S&P500 {mkt.get('SP500',{}).get('change',0):+.2f}% / NASDAQ {mkt.get('NASDAQ',{}).get('change',0):+.2f}% / VIX {mkt.get('VIX',{}).get('price',0):.2f}
금 ${mkt.get('GOLD',{}).get('price',0):,.0f} ({mkt.get('GOLD',{}).get('change',0):+.2f}%) / WTI ${mkt.get('OIL',{}).get('price',0):.2f} ({mkt.get('OIL',{}).get('change',0):+.2f}%)
BTC ${mkt.get('BTC',{}).get('price',0):,.0f} ({mkt.get('BTC',{}).get('change',0):+.2f}%)

오늘의 주요 시장 이슈 10개를 작성해주세요.
각 줄은 반드시 "• 🔤 카테고리 | 내용" 형식으로.
카테고리: 연준, 실적, 금리, AI, 미중, 달러, 원유, 정책, 코인, 지정학 중 선택.
각 항목 1~2문장, 핵심만.
순수 텍스트, 번호 없이, HTML 태그 없이."""

    return claude_generate(JOURNALIST_SYSTEM, prompt, max_tokens=1000)

def gen_macro_newsletter(mkt):
    """매크로 뉴스레터 3~4개 토픽"""
    prompt = f"""오늘 날짜: {TODAY_STR}

주요 지표:
- S&P500: {mkt.get('SP500',{}).get('change',0):+.2f}% / VIX: {mkt.get('VIX',{}).get('price',0):.2f}
- 금: ${mkt.get('GOLD',{}).get('price',0):,.0f} / DXY: {mkt.get('DXY',{}).get('price',0):.2f}
- BTC: ${mkt.get('BTC',{}).get('price',0):,.0f} ({mkt.get('BTC',{}).get('change',0):+.2f}%)

오늘 시장 상황에 맞게 3~4개의 매크로 인사이트 토픽을 작성해주세요.

각 토픽 형식:
[ ① 토픽 제목 — 부제 ]
본문 (8~10문장, 600~800자, 2~3단락)
시사점: 투자 관점에서 구체적 행동 지침 1~2문장

다룰 소재 (오늘 상황에 맞게 3~4개 선택):
- 연준/파월 의장 금리 정책
- 재무부/베센트 재정·달러 정책  
- 트럼프 행정부 관세·무역
- 공포지수(VIX)·시장 심리
- AI·빅테크 투자 논리
- 금·안전자산 수요
- 채권시장·금리 커브
- 대중의 경기침체 공포 vs 시장 현실
- 이번 주 핫이슈

중립적이고 맑은 시각으로, 공포 조장 없이, 인간적인 매크로 인사이트.
각 토픽은 ===TOPIC=== 으로 구분해주세요."""

    raw = claude_generate(JOURNALIST_SYSTEM, prompt, max_tokens=3500)
    topics = [t.strip() for t in raw.split("===TOPIC===") if t.strip()]
    return topics

def gen_regional_brief(region):
    """중국·홍콩 또는 일본 브리핑"""
    if region == "cn":
        prompt = f"{TODAY_STR} 기준, 중국 상하이종합지수·홍콩 항셍지수 주요 동향 5줄. 경제지표·정책·주요 기업·위안화 포함."
        flag = "🇨🇳 중국 · 홍콩"
    else:
        prompt = f"{TODAY_STR} 기준, 일본 닛케이225 주요 동향 5줄. BOJ 금리·엔화·주요 산업 이슈 포함."
        flag = "🇯🇵 일본"

    system = "한국 경제 전문 기자. 시장 소식 5줄 이내, 각 항목 '• '으로 시작, 절제된 기자 문체, 순수 텍스트만."
    text = claude_generate(system, prompt, max_tokens=600)
    return text

# ── 4. HTML 생성 ───────────────────────────────────────
def build_card(label, price_str, change):
    color = "#e53e3e" if change >= 0 else "#3182ce"
    arrow = "▲" if change >= 0 else "▼"
    return f"""<div class="card">
  <div class="card-label">{label}</div>
  <div class="card-value">{price_str}</div>
  <div class="card-change" style="color:{color}">{arrow} {abs(change):.2f}%</div>
</div>"""

def build_issue_rows(issues_text):
    rows = ""
    for line in issues_text.strip().split("\n"):
        line = line.strip()
        if line.startswith("•"):
            rows += f'<div class="issue-row">{line}</div>\n'
    return rows

def build_macro_topics(topics):
    html = ""
    roman = ["①","②","③","④","⑤"]
    for i, topic in enumerate(topics[:5]):
        lines = topic.strip().split("\n")
        # 첫 줄이 제목
        title_line = lines[0].strip().lstrip("[").rstrip("]").strip()
        # 시사점 분리
        body_parts, simsajeom = [], ""
        for line in lines[1:]:
            if line.strip().startswith("시사점"):
                simsajeom = line.replace("시사점:","").replace("**시사점:**","").strip()
            else:
                body_parts.append(line)
        body = "\n".join(body_parts).strip()
        
        html += f'<div class="nl-topic">[ {title_line} ]</div>\n'
        html += f'<p class="nl-body" style="white-space:pre-line">{body}'
        if simsajeom:
            html += f'\n\n<strong>시사점:</strong> {simsajeom}'
        html += '</p>\n'
    return html

def build_fred_script(cpi, core_cpi, unrate, fedfunds, dgs10, dgs2):
    def js_arr(d): return json.dumps(d)
    return f"""
const fredCfg={{margin:{{t:10,b:40,l:50,r:10}},legend:{{orientation:'h',y:-0.25,font:{{size:11}}}},paper_bgcolor:'transparent',plot_bgcolor:'transparent',xaxis:{{gridcolor:'#f1f5f9',tickfont:{{size:10}}}},yaxis:{{gridcolor:'#f1f5f9',tickfont:{{size:10}}}}}};
const fredOpt={{responsive:true,displayModeBar:false}};
Plotly.newPlot('fred1',[
  {{x:{js_arr(cpi['x'])},y:{js_arr(cpi['y'])},name:'CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},
  {{x:{js_arr(core_cpi['x'])},y:{js_arr(core_cpi['y'])},name:'Core CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}
],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}},shapes:[{{type:'line',x0:'{cpi['x'][0] if cpi['x'] else ''}',x1:'{cpi['x'][-1] if cpi['x'] else ''}',y0:2,y1:2,line:{{color:'#9ca3af',width:1,dash:'dot'}}}}]}},fredOpt);
Plotly.newPlot('fred2',[
  {{x:{js_arr(unrate['x'])},y:{js_arr(unrate['y'])},name:'실업률',type:'scatter',mode:'lines',line:{{color:'#7c3aed',width:2}}}},
  {{x:{js_arr(fedfunds['x'])},y:{js_arr(fedfunds['y'])},name:'Fed Funds',type:'scatter',mode:'lines',line:{{color:'#d97706',width:2}}}}
],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}}}},fredOpt);
Plotly.newPlot('fred3',[
  {{x:{js_arr(dgs10['x'])},y:{js_arr(dgs10['y'])},name:'10년물',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},
  {{x:{js_arr(dgs2['x'])},y:{js_arr(dgs2['y'])},name:'2년물',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}
],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}}}},fredOpt);
"""

# ── 5. 메인 HTML 조립 ──────────────────────────────────
def build_html(mkt, headline, summary_body, keyline,
               issues_html, macro_html, cn_brief, jp_brief,
               fred_script):

    def card(label, sym, prefix="", decimals=2):
        d = mkt.get(sym, {})
        p = d.get("price", 0)
        c = d.get("change", 0)
        ps = f"{prefix}{p:,.{decimals}f}" if p else "N/A"
        color = "#e53e3e" if c >= 0 else "#3182ce"
        arrow = "▲" if c >= 0 else "▼"
        return (f'<div class="card"><div class="card-label">{label}</div>'
                f'<div class="card-value">{ps}</div>'
                f'<div class="card-change" style="color:{color}">{arrow} {abs(c):.2f}%</div></div>')

    # 공포탐욕 — VIX 기반 추정
    vix_val = mkt.get("VIX", {}).get("price", 25)
    cnn_fg = max(5, min(95, int(100 - vix_val * 2.5)))

    # HTML 템플릿 읽기
    with open("templates/dashboard.html", "r") as f:
        html = f.read()

    # ── str.format() 대신 직접 replace() 사용 ──
    # CSS의 {box-sizing} 등 중괄호와 충돌하지 않음

    replacements = {
        "{TODAY_STR}":   TODAY_STR,
        "{HEADLINE}":    headline,
        "{SUMMARY_BODY}": summary_body,
        "{KEYLINE}":     keyline,
        "{ISSUES_HTML}": issues_html,
        "{CARD_SP500}":  card("S&P 500",      "SP500",   decimals=2),
        "{CARD_NASDAQ}": card("NASDAQ",        "NASDAQ",  decimals=2),
        "{CARD_DOW}":    card("Dow Jones",     "DOW",     decimals=2),
        "{CARD_RUSSELL}":card("Russell 2000",  "RUSSELL", decimals=2),
        "{CARD_VIX}":    card("VIX",           "VIX",     decimals=2),
        "{CARD_GOLD}":   card("금 (XAU/USD)",  "GOLD",    "$", decimals=0),
        "{CARD_SILVER}": card("은 (XAG/USD)",  "SILVER",  "$", decimals=2),
        "{CARD_OIL}":    card("WTI 원유",      "OIL",     "$", decimals=2),
        "{CARD_COPPER}": card("구리",          "COPPER",  "$", decimals=3),
        "{CARD_DXY}":    card("달러인덱스",    "DXY",     decimals=2),
        "{CARD_KRW}":    card("원/달러",       "KRW",     decimals=2),
        "{CARD_JPY}":    card("엔/달러",       "JPY",     decimals=2),
        "{CARD_CNY}":    card("위안/달러",     "CNY",     decimals=3),
        "{CARD_BTC}":    card("Bitcoin",       "BTC",     "$", decimals=0),
        "{CARD_ETH}":    card("Ethereum",      "ETH",     "$", decimals=0),
        "{CARD_SOL}":    card("Solana",        "SOL",     "$", decimals=2),
        "{CNN_FG}":      str(cnn_fg),
        "{MACRO_HTML}":  macro_html,
        "{CN_BRIEF}":    cn_brief.replace("\n", "<br>"),
        "{JP_BRIEF}":    jp_brief.replace("\n", "<br>"),
        "{FRED_SCRIPT}": fred_script,
        "{ANTHROPIC_KEY}": ANTHROPIC_API_KEY,
        "{FRED_KEY}":    FRED_API_KEY,
    }

    for placeholder, value in replacements.items():
        html = html.replace(placeholder, str(value))

    return html

# ── 6. 실행 ───────────────────────────────────────────
def main():
    print(f"🚀 대시보드 생성 시작 — {TODAY_STR}")

    print("  📊 시장 데이터 수집 중...")
    try:
        mkt = fetch_market_data()
    except Exception as e:
        print(f"  ⚠️  시장 데이터 실패: {e}")
        mkt = {}

    print("  📈 FRED 경제지표 수집 중...")
    try:
        cpi      = fred_yoy("CPIAUCSL")
        core_cpi = fred_yoy("CPILFESL")
        unrate   = fetch_fred("UNRATE")
        fedfunds = fetch_fred("FEDFUNDS")
        dgs10    = fetch_fred("DGS10")
        dgs2     = fetch_fred("DGS2")
        fred_script = build_fred_script(cpi, core_cpi, unrate, fedfunds, dgs10, dgs2)
        print(f"  ✅ FRED 완료 (CPI:{len(cpi['x'])}개 포인트)")
    except Exception as e:
        print(f"  ⚠️  FRED 전체 실패: {e}")
        fred_script = "// FRED 데이터 없음"

    print("  ✍️  시황 생성 중...")
    try:
        headline, summary_body, keyline = gen_daily_summary(mkt)
    except Exception as e:
        print(f"  ⚠️  시황 생성 실패: {e}")
        headline = f"{TODAY_STR} 시장 마감 시황"
        summary_body = "시황 데이터를 불러오는 중 오류가 발생했습니다."
        keyline = "데이터 로딩 중"

    print("  📰 이슈 생성 중...")
    try:
        issues_text = gen_issues(mkt)
        issues_html = build_issue_rows(issues_text)
    except Exception as e:
        print(f"  ⚠️  이슈 생성 실패: {e}")
        issues_html = '<div class="issue-row">• 이슈 데이터 로딩 중...</div>'

    print("  🌐 매크로 뉴스레터 생성 중...")
    try:
        macro_topics = gen_macro_newsletter(mkt)
        macro_html   = build_macro_topics(macro_topics)
    except Exception as e:
        print(f"  ⚠️  뉴스레터 생성 실패: {e}")
        macro_html = '<p class="nl-body">뉴스레터 데이터 로딩 중...</p>'

    print("  🇨🇳 중국·홍콩 브리핑...")
    try:
        cn_brief = gen_regional_brief("cn")
    except Exception as e:
        print(f"  ⚠️  중국 브리핑 실패: {e}")
        cn_brief = "중국·홍콩 데이터 로딩 중..."

    print("  🇯🇵 일본 브리핑...")
    try:
        jp_brief = gen_regional_brief("jp")
    except Exception as e:
        print(f"  ⚠️  일본 브리핑 실패: {e}")
        jp_brief = "일본 데이터 로딩 중..."

    print("  🔨 HTML 조립 중...")
    html = build_html(mkt, headline, summary_body, keyline,
                      issues_html, macro_html, cn_brief, jp_brief,
                      fred_script)

    out_path = Path("docs/index.html")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"  ✅ 완료! → docs/index.html ({len(html):,}bytes)")

if __name__ == "__main__":
    main()
