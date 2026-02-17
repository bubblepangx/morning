import os, json, datetime, requests, sys, re
from pathlib import Path
from zoneinfo import ZoneInfo

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FRED_API_KEY      = os.environ.get("FRED_API_KEY", "")

if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY not set"); sys.exit(1)

import anthropic
import yfinance as yf

KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.datetime.now(KST)
DAY_MAP = {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}
TODAY_STR = TODAY.strftime("%Y년 %m월 %d일") + f" ({DAY_MAP[TODAY.strftime('%a')]})"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=120.0)

SYMS = {"SP500":"^GSPC","NASDAQ":"^IXIC","DOW":"^DJI","RUSSELL":"^RUT",
        "VIX":"^VIX","GOLD":"GC=F","SILVER":"SI=F","OIL":"CL=F","COPPER":"HG=F",
        "DXY":"DX-Y.NYB","BTC":"BTC-USD","ETH":"ETH-USD","SOL":"SOL-USD",
        "KRW":"KRW=X","JPY":"JPY=X","CNY":"CNY=X"}

def fetch_market():
    data = {k:{"price":0,"change":0} for k in SYMS}
    try:
        raw = yf.download(list(SYMS.values()), period="2d", interval="1d",
                          group_by="ticker", auto_adjust=True, progress=False, timeout=30)
        for name, sym in SYMS.items():
            try:
                cl = raw[sym]["Close"].dropna() if sym in raw.columns.get_level_values(0) else raw["Close"].dropna()
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

SYS = ("당신은 월가와 글로벌 매크로를 20년간 취재한 한국 경제 전문기자입니다. "
       "절제된 기자 문체, 사실 중심, 인사이트 있는 분석을 씁니다.")

def ai_call(prompt, max_tokens=2000):
    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=max_tokens,
            system=SYS, messages=[{"role":"user","content":prompt}])
        return msg.content[0].text
    except Exception as e:
        print(f"Claude error: {e}"); return ""

def gen_summary(mkt):
    sp=mkt.get("SP500",{}); nq=mkt.get("NASDAQ",{}); dw=mkt.get("DOW",{})
    ru=mkt.get("RUSSELL",{}); vix=mkt.get("VIX",{}); gold=mkt.get("GOLD",{})
    oil=mkt.get("OIL",{}); dxy=mkt.get("DXY",{})
    t = ai_call(f"""오늘: {TODAY_STR}
S&P500 {sp.get('price',0):,.2f} ({sp.get('change',0):+.2f}%)
NASDAQ {nq.get('price',0):,.2f} ({nq.get('change',0):+.2f}%)
다우 {dw.get('price',0):,.2f} ({dw.get('change',0):+.2f}%)
러셀2000 {ru.get('price',0):,.2f} ({ru.get('change',0):+.2f}%)
VIX {vix.get('price',0):.2f} / 금 ${gold.get('price',0):,.0f} / WTI ${oil.get('price',0):.2f} / DXY {dxy.get('price',0):.2f}

미국 시장 마감 시황 작성:
1. 첫 줄: 헤드라인 (30자 내외)
2. 본문: 7~8문단 (각 3~4문장)
3. 마지막 줄: "핵심 한 줄: 요약"
순수 텍스트만, HTML 없이.""", max_tokens=2500)
    lines = [l.strip() for l in t.strip().split("\n") if l.strip()]
    hl = lines[0].lstrip("#").strip() if lines else TODAY_STR
    kl, bl = "", []
    for l in lines[1:]:
        if "핵심 한 줄" in l: kl = l.split(":",1)[-1].strip(" :—-*")
        else: bl.append(l)
    return hl, "\n\n".join(bl), kl

def gen_issues(mkt):
    sp=mkt.get("SP500",{}); vix=mkt.get("VIX",{})
    t = ai_call(f"""{TODAY_STR} S&P500 {sp.get('change',0):+.2f}% VIX {vix.get('price',0):.2f}
이슈 10개. 형식: "• 카테고리 | 내용" 순수 텍스트.""", max_tokens=1000)
    rows = "".join(f'<div class="issue-row">{l.strip()}</div>\n'
                   for l in t.split("\n") if l.strip().startswith("•"))
    return rows or '<div class="issue-row">• 데이터 로딩 중</div>'

def gen_macro(mkt):
    sp=mkt.get("SP500",{}); vix=mkt.get("VIX",{}); gold=mkt.get("GOLD",{}); dxy=mkt.get("DXY",{})
    t = ai_call(f"""{TODAY_STR}
S&P500 {sp.get('change',0):+.2f}% VIX {vix.get('price',0):.2f} 금 ${gold.get('price',0):,.0f} DXY {dxy.get('price',0):.2f}
매크로 인사이트 3~4개. 각 형식:
[ 번호 제목 ]
본문 600자
시사점: 한줄
구분: ===TOPIC=== 순수 텍스트.""", max_tokens=3500)
    topics = [x.strip() for x in t.split("===TOPIC===") if x.strip()]
    html = ""
    for topic in topics[:5]:
        lines = topic.strip().split("\n")
        title = lines[0].strip().lstrip("[").rstrip("]").strip()
        body_parts, simsajeom = [], ""
        for l in lines[1:]:
            if l.strip().startswith("시사점"): simsajeom = l.split(":",1)[-1].strip()
            else: body_parts.append(l)
        body = "\n".join(body_parts).strip()
        html += f'<div class="nl-topic">[ {title} ]</div>\n'
        html += f'<p class="nl-body" style="white-space:pre-line">{body}'
        if simsajeom: html += f'\n\n<strong>시사점:</strong> {simsajeom}'
        html += '</p>\n'
    return html or '<p class="nl-body">로딩 중...</p>'

def gen_brief(region):
    if region == "cn":
        p = f"{TODAY_STR} 중국 상하이·홍콩 항셍 동향 5줄. 경제지표·정책·위안화 포함."
    else:
        p = f"{TODAY_STR} 일본 닛케이225 동향 5줄. BOJ·엔화·산업 포함."
    t = ai_call(p, max_tokens=500)
    return t.replace("\n","<br>") if t else "로딩 중..."

def patch_html(src, mkt, hl, sb, kl, issues, macro, cn, jp, fscript):
    """템플릿 HTML에서 동적 부분만 re.sub으로 교체 — format() 절대 사용 안함"""
    h = src

    # 날짜
    h = re.sub(r'\d{4}년 \d{2}월 \d{2}일 \([월화수목금토일]\)', TODAY_STR, h)

    # 헤드라인
    h = re.sub(r'<div class="article-headline">[\s\S]*?</div>',
               '<div class="article-headline">' + hl + '</div>', h, count=1)

    # 시황 본문
    h = re.sub(r'<div class="summary-body">[\s\S]*?</div>',
               '<div class="summary-body">' + sb + '</div>', h, count=1)

    # 핵심 한 줄
    h = re.sub(r'<div class="summary-keyline">[\s\S]*?</div>',
               '<div class="summary-keyline"><strong>핵심 한 줄</strong>&nbsp;' + kl + '</div>', h, count=1)

    # 이슈 rows
    h = re.sub(
        r'(<div class="block-title">오늘의 주요 이슈[^<]*<span[^>]*>[^<]*</span></div>\s*)'
        r'((?:<div class="issue-row">[\s\S]*?</div>\s*)*)',
        lambda m: m.group(1) + issues, h, count=1)

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

    # 매크로 뉴스레터
    h = re.sub(
        r'(<div class="block-title">글로벌 매크로 뉴스레터[\s\S]*?</div>\s*)[\s\S]*?(<!-- 중국·홍콩)',
        lambda m: m.group(1) + macro + "\n  " + m.group(2), h, count=1)

    # 중국·홍콩
    h = re.sub(r'<div id="cn-news-wrap">[\s\S]*?</div>',
               '<div id="cn-news-wrap"><p class="nl-body">' + cn + '</p></div>', h, count=1)

    # 일본
    h = re.sub(r'<div id="jp-news-wrap">[\s\S]*?</div>',
               '<div id="jp-news-wrap"><p class="nl-body">' + jp + '</p></div>', h, count=1)

    # FRED 스크립트
    h = re.sub(r'<script>\s*// ====== FRED 실시간 API[\s\S]+?loadFredData\(\);\s*</script>',
               '<script>\n' + fscript + '\n</script>', h)

    return h

def main():
    print(f"START {TODAY_STR}")

    try: mkt = fetch_market()
    except Exception as e: print(f"market err:{e}"); mkt={}

    try:
        cpi=fred_yoy("CPIAUCSL"); core=fred_yoy("CPILFESL")
        un=fred_get("UNRATE"); ff=fred_get("FEDFUNDS")
        d10=fred_get("DGS10"); d2=fred_get("DGS2")
        fscript = fred_js(cpi,core,un,ff,d10,d2)
        print("FRED ok")
    except Exception as e: print(f"fred err:{e}"); fscript="// no fred"

    try: hl,sb,kl=gen_summary(mkt); print("summary ok")
    except Exception as e: print(f"summary err:{e}"); hl=TODAY_STR; sb="준비중"; kl="준비중"

    try: issues=gen_issues(mkt); print("issues ok")
    except Exception as e: print(f"issues err:{e}"); issues='<div class="issue-row">• 준비중</div>'

    try: macro=gen_macro(mkt); print("macro ok")
    except Exception as e: print(f"macro err:{e}"); macro='<p class="nl-body">준비중</p>'

    try: cn=gen_brief("cn"); print("cn ok")
    except Exception as e: print(f"cn err:{e}"); cn="준비중"

    try: jp=gen_brief("jp"); print("jp ok")
    except Exception as e: print(f"jp err:{e}"); jp="준비중"

    tmpl_path = Path("templates/dashboard.html")
    if not tmpl_path.exists():
        print("ERROR: templates/dashboard.html not found"); sys.exit(1)

    src = tmpl_path.read_text(encoding="utf-8")
    html = patch_html(src, mkt, hl, sb, kl, issues, macro, cn, jp, fscript)

    out = Path("docs/index.html")
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"DONE {len(html):,}bytes")

if __name__ == "__main__":
    main()
