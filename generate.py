"""
Daily US Market Dashboard — 자동 생성 스크립트
템플릿 파일 없이 완전 독립 동작 / CSS {} 충돌 없음
"""

import os, json, datetime, requests, sys, re
from pathlib import Path
from zoneinfo import ZoneInfo

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FRED_API_KEY      = os.environ.get("FRED_API_KEY", "")
KST               = ZoneInfo("Asia/Seoul")
TODAY             = datetime.datetime.now(KST)
DAY_MAP = {"Mon":"월","Tue":"화","Wed":"수","Thu":"목","Fri":"금","Sat":"토","Sun":"일"}
TODAY_STR = TODAY.strftime("%Y년 %m월 %d일") + f" ({DAY_MAP[TODAY.strftime('%a')]})"
FRED_URL  = "https://api.stlouisfed.org/fred/series/observations"

if not ANTHROPIC_API_KEY:
    print("❌ ANTHROPIC_API_KEY 없음"); sys.exit(1)

import anthropic
import yfinance as yf

claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

def fetch_market_data():
    syms = {
        "SP500":"^GSPC","NASDAQ":"^IXIC","DOW":"^DJI","RUSSELL":"^RUT",
        "VIX":"^VIX","GOLD":"GC=F","SILVER":"SI=F","OIL":"CL=F","COPPER":"HG=F",
        "DXY":"DX-Y.NYB","BTC":"BTC-USD","ETH":"ETH-USD","SOL":"SOL-USD",
        "KRW":"KRW=X","JPY":"JPY=X","CNY":"CNY=X",
    }
    data = {k:{"price":0,"change":0} for k in syms}
    try:
        raw = yf.download(list(syms.values()), period="2d", interval="1d",
                          group_by="ticker", auto_adjust=True, progress=False, timeout=30)
        for name, sym in syms.items():
            try:
                try:    closes = raw[sym]["Close"].dropna()
                except: closes = raw["Close"].dropna()
                if len(closes) >= 2:
                    c,p = float(closes.iloc[-1]), float(closes.iloc[-2])
                    data[name] = {"price":c,"change":(c-p)/p*100}
                elif len(closes)==1:
                    data[name] = {"price":float(closes.iloc[-1]),"change":0.0}
            except: pass
    except Exception as e:
        print(f"  yfinance 실패: {e}")
    return data

def card_html(label, d, pre="", dec=2):
    p,c = d.get("price",0), d.get("change",0)
    ps  = f"{pre}{p:,.{dec}f}" if p else "N/A"
    col = "#e53e3e" if c>=0 else "#3182ce"
    arr = "▲" if c>=0 else "▼"
    return (f'<div class="card"><div class="card-label">{label}</div>'
            f'<div class="card-value">{ps}</div>'
            f'<div class="card-change" style="color:{col}">{arr} {abs(c):.2f}%</div></div>')

def fetch_fred(sid, limit=36):
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
        print(f"  FRED {sid}: {e}"); return {"x":[],"y":[]}

def fred_yoy(sid):
    if not FRED_API_KEY: return {"x":[],"y":[]}
    try:
        r = requests.get(FRED_URL, params={"series_id":sid,"api_key":FRED_API_KEY,
            "file_type":"json","observation_start":"2022-01-01","sort_order":"asc"}, timeout=15)
        d = r.json()
        if "observations" not in d: return {"x":[],"y":[]}
        obs = [o for o in d["observations"] if o["value"]!="."]
        vm  = {o["date"]:float(o["value"]) for o in obs}
        rx,ry = [],[]
        for o in obs:
            dt = o["date"]
            if dt<"2023-01-01": continue
            prev_dt = f"{int(dt[:4])-1}{dt[4:]}"
            cands = [k for k in vm if k<=prev_dt]
            if not cands: continue
            prev = vm[max(cands)]
            if prev: rx.append(dt); ry.append(round((vm[dt]-prev)/prev*100,2))
        return {"x":rx,"y":ry}
    except Exception as e:
        print(f"  FRED YoY {sid}: {e}"); return {"x":[],"y":[]}

def build_fred_script(cpi, core, un, ff, d10, d2):
    def ja(d): return json.dumps(d)
    x0 = cpi["x"][0]  if cpi["x"] else ""
    x1 = cpi["x"][-1] if cpi["x"] else ""
    return (
        "const fredCfg={margin:{t:10,b:40,l:50,r:10},legend:{orientation:'h',y:-0.25,font:{size:11}},"
        "paper_bgcolor:'transparent',plot_bgcolor:'transparent',"
        "xaxis:{gridcolor:'#f1f5f9',tickfont:{size:10}},yaxis:{gridcolor:'#f1f5f9',tickfont:{size:10}}};\n"
        "const fredOpt={responsive:true,displayModeBar:false};\n"
        f"Plotly.newPlot('fred1',["
        f"{{x:{ja(cpi['x'])},y:{ja(cpi['y'])},name:'CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},"
        f"{{x:{ja(core['x'])},y:{ja(core['y'])},name:'Core CPI YoY%',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}"
        f"],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}},"
        f"shapes:[{{type:'line',x0:'{x0}',x1:'{x1}',y0:2,y1:2,line:{{color:'#9ca3af',width:1,dash:'dot'}}}}]}},fredOpt);\n"
        f"Plotly.newPlot('fred2',["
        f"{{x:{ja(un['x'])},y:{ja(un['y'])},name:'실업률',type:'scatter',mode:'lines',line:{{color:'#7c3aed',width:2}}}},"
        f"{{x:{ja(ff['x'])},y:{ja(ff['y'])},name:'Fed Funds',type:'scatter',mode:'lines',line:{{color:'#d97706',width:2}}}}"
        f"],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}}}},fredOpt);\n"
        f"Plotly.newPlot('fred3',["
        f"{{x:{ja(d10['x'])},y:{ja(d10['y'])},name:'10년물',type:'scatter',mode:'lines',line:{{color:'#2563eb',width:2}}}},"
        f"{{x:{ja(d2['x'])},y:{ja(d2['y'])},name:'2년물',type:'scatter',mode:'lines',line:{{color:'#dc2626',width:2}}}}"
        f"],{{...fredCfg,yaxis:{{...fredCfg.yaxis,ticksuffix:'%'}}}},fredOpt);\n"
    )

JOURNALIST = ("당신은 월가와 글로벌 매크로를 20년간 취재한 한국 경제 전문기자입니다. "
              "절제된 기자 문체, 과장 없이 사실 중심, 인사이트 있는 분석을 씁니다.")

def ai(system, prompt, max_tokens=2000):
    try:
        msg = claude.messages.create(
            model="claude-sonnet-4-5-20250929", max_tokens=max_tokens,
            system=system, messages=[{"role":"user","content":prompt}], timeout=60)
        return msg.content[0].text
    except Exception as e:
        print(f"  Claude 실패: {e}"); return ""

def gen_summary(mkt):
    sp=mkt.get("SP500",{}); nq=mkt.get("NASDAQ",{}); dw=mkt.get("DOW",{})
    ru=mkt.get("RUSSELL",{}); vix=mkt.get("VIX",{}); gold=mkt.get("GOLD",{})
    oil=mkt.get("OIL",{}); dxy=mkt.get("DXY",{})
    result = ai(JOURNALIST, f"""오늘: {TODAY_STR}
S&P500 {sp.get('price',0):,.2f} ({sp.get('change',0):+.2f}%) / NASDAQ {nq.get('price',0):,.2f} ({nq.get('change',0):+.2f}%)
다우 {dw.get('price',0):,.2f} ({dw.get('change',0):+.2f}%) / 러셀2000 {ru.get('price',0):,.2f} ({ru.get('change',0):+.2f}%)
VIX {vix.get('price',0):.2f} / 금 ${gold.get('price',0):,.0f} / WTI ${oil.get('price',0):.2f} / DXY {dxy.get('price',0):.2f}

미국 시장 마감 시황 작성:
1. 첫 줄: 헤드라인 (30자 내외)
2. 본문: 7~8문단
3. 마지막 줄: "핵심 한 줄: 요약"
순수 텍스트만.""", max_tokens=2500)
    lines=[l.strip() for l in result.strip().split("\n") if l.strip()]
    headline=lines[0].lstrip("#").strip() if lines else f"{TODAY_STR} 마감"
    keyline, body_lines = "", []
    for l in lines[1:]:
        if "핵심 한 줄" in l: keyline=l.split(":",1)[-1].strip(" :—-*")
        else: body_lines.append(l)
    return headline, "\n\n".join(body_lines), keyline

def gen_issues(mkt):
    sp=mkt.get("SP500",{}); vix=mkt.get("VIX",{})
    result=ai(JOURNALIST,f"""{TODAY_STR} S&P500 {sp.get('change',0):+.2f}% VIX {vix.get('price',0):.2f}
이슈 10개. 형식: "• 🔤 카테고리 | 내용" 순수텍스트.""", max_tokens=1000)
    rows="".join(f'<div class="issue-row">{l.strip()}</div>\n'
                 for l in result.split("\n") if l.strip().startswith("•"))
    return rows or '<div class="issue-row">• 로딩 중...</div>'

def gen_macro(mkt):
    sp=mkt.get("SP500",{}); vix=mkt.get("VIX",{}); gold=mkt.get("GOLD",{}); dxy=mkt.get("DXY",{})
    raw=ai(JOURNALIST,f"""{TODAY_STR}
S&P500 {sp.get('change',0):+.2f}% VIX {vix.get('price',0):.2f} 금 ${gold.get('price',0):,.0f} DXY {dxy.get('price',0):.2f}
매크로 인사이트 3~4개. 각 토픽: [ ① 제목 ]\\n본문 600자\\n시사점: 한줄
구분: ===TOPIC=== 순수텍스트.""", max_tokens=3500)
    topics=[t.strip() for t in raw.split("===TOPIC===") if t.strip()]
    html=""
    for topic in topics[:5]:
        lines=topic.strip().split("\n")
        title=lines[0].strip().lstrip("[").rstrip("]").strip()
        body_parts,simsajeom=[],""
        for l in lines[1:]:
            if l.strip().startswith("시사점"): simsajeom=l.split(":",1)[-1].strip()
            else: body_parts.append(l)
        body="\n".join(body_parts).strip()
        html+=f'<div class="nl-topic">[ {title} ]</div>\n'
        html+=f'<p class="nl-body" style="white-space:pre-line">{body}'
        if simsajeom: html+=f'\n\n<strong>시사점:</strong> {simsajeom}'
        html+='</p>\n'
    return html or '<p class="nl-body">로딩 중...</p>'

def gen_brief(region):
    p=(f"{TODAY_STR} 중국 상하이·홍콩 항셍 동향 5줄. 경제지표·정책·위안화 포함."
       if region=="cn" else f"{TODAY_STR} 일본 닛케이225 동향 5줄. BOJ·엔화·산업 포함.")
    r=ai("경제전문기자. 5줄, '• '로 시작, 순수텍스트.",p,max_tokens=500)
    return r.replace("\n","<br>") if r else "로딩 중..."

def build_html(mkt, headline, summary_body, keyline,
               issues_html, macro_html, cn_brief, jp_brief, fred_script):
    src = Path("templates/dashboard.html")
    if not src.exists():
        print("  ⚠️  templates/dashboard.html 없음"); return "<html><body>템플릿 없음</body></html>"
    html = src.read_text(encoding="utf-8")

    # 날짜
    html = re.sub(r'\d{4}년 \d{2}월 \d{2}일 \([월화수목금토일]\)', TODAY_STR, html)
    # 헤드라인
    html = re.sub(r'<div class="article-headline">[\s\S]*?</div>',
                  f'<div class="article-headline">{headline}</div>', html, count=1)
    # 시황
    html = re.sub(r'<div class="summary-body">[\s\S]*?</div>',
                  f'<div class="summary-body">{summary_body}</div>', html, count=1)
    # 핵심 한 줄
    html = re.sub(r'<div class="summary-keyline">[\s\S]*?</div>',
                  f'<div class="summary-keyline"><strong>핵심 한 줄</strong>&nbsp;{keyline}</div>',
                  html, count=1)
    # 이슈
    html = re.sub(
        r'(<div class="block-title">오늘의 주요 이슈[^<]*<span[^>]*>[^<]*</span></div>\s*)'
        r'((?:<div class="issue-row">[\s\S]*?</div>\s*)*)',
        lambda m: m.group(1)+issues_html, html, count=1)
    # 지수 카드
    idx = (card_html("S&P 500",mkt.get("SP500",{}))+card_html("NASDAQ",mkt.get("NASDAQ",{}))+
           card_html("Dow Jones",mkt.get("DOW",{}))+card_html("Russell 2000",mkt.get("RUSSELL",{}))+
           card_html("VIX",mkt.get("VIX",{})))
    html = re.sub(
        r'(<!-- 3\. 주요 지수 카드[\s\S]*?<div class="cards">)[\s\S]*?(</div>\s*</div>\s*<!-- 4\.)',
        lambda m: m.group(1)+idx+m.group(2), html, count=1)
    # 원자재 카드
    com = (card_html("금 (XAU/USD)",mkt.get("GOLD",{}),"$",0)+
           card_html("은 (XAG/USD)",mkt.get("SILVER",{}),"$",2)+
           card_html("WTI 원유",mkt.get("OIL",{}),"$",2)+
           card_html("구리",mkt.get("COPPER",{}),"$",3))
    html = re.sub(
        r'(원자재 — 가격 스냅샷</div>\s*<div class="cards">)[\s\S]*?(</div>\s*<div class="subsection-label"[^>]*>원자재 — TradingView)',
        lambda m: m.group(1)+com+m.group(2), html, count=1)
    # 환율 카드
    fx = (card_html("달러인덱스",mkt.get("DXY",{}))+card_html("원/달러",mkt.get("KRW",{}))+
          card_html("엔/달러",mkt.get("JPY",{}))+card_html("위안/달러",mkt.get("CNY",{}),dec=3))
    html = re.sub(
        r'(subsection-label">환율</div>\s*<div class="cards">)[\s\S]*?(</div>\s*<div class="subsection-label"[^>]*>원자재)',
        lambda m: m.group(1)+fx+m.group(2), html, count=1)
    # 공포탐욕
    vix_val = mkt.get("VIX",{}).get("price",25)
    cnn_fg  = max(5, min(95, int(100-vix_val*2.5)))
    html = re.sub(r"drawGauge\('gauge-cnn',\s*\d+,", f"drawGauge('gauge-cnn', {cnn_fg},", html)
    # 매크로
    html = re.sub(
        r'(<div class="block-title">글로벌 매크로 뉴스레터[\s\S]*?</div>\s*)[\s\S]*?(<!-- 중국·홍콩)',
        lambda m: m.group(1)+macro_html+"\n  "+m.group(2), html, count=1)
    # 중국·홍콩
    html = re.sub(r'<div id="cn-news-wrap">[\s\S]*?</div>',
                  f'<div id="cn-news-wrap"><p class="nl-body">{cn_brief}</p></div>', html, count=1)
    # 일본
    html = re.sub(r'<div id="jp-news-wrap">[\s\S]*?</div>',
                  f'<div id="jp-news-wrap"><p class="nl-body">{jp_brief}</p></div>', html, count=1)
    # FRED 스크립트
    html = re.sub(r'<script>\s*// ====== FRED 실시간 API[\s\S]+?loadFredData\(\);\s*</script>',
                  f'<script>\n{fred_script}\n</script>', html)
    # API 키
    html = html.replace("'YOUR_API_KEY_HERE'", f"'{ANTHROPIC_API_KEY}'")
    html = html.replace("'abcdefghijklmnopqrstuvwxyz123456'", f"'{FRED_API_KEY}'")
    return html

def main():
    print(f"🚀 {TODAY_STR}")
    try:    mkt=fetch_market_data()
    except Exception as e: print(f"  시장데이터 실패:{e}"); mkt={}
    try:
        cpi=fred_yoy("CPIAUCSL"); core=fred_yoy("CPILFESL")
        un=fetch_fred("UNRATE"); ff=fetch_fred("FEDFUNDS")
        d10=fetch_fred("DGS10"); d2=fetch_fred("DGS2")
        fred_script=build_fred_script(cpi,core,un,ff,d10,d2); print("  ✅ FRED")
    except Exception as e: print(f"  FRED 실패:{e}"); fred_script="// FRED없음"
    try:    hl,sb,kl=gen_summary(mkt); print("  ✅ 시황")
    except Exception as e: print(f"  시황실패:{e}"); hl=f"{TODAY_STR}"; sb="로딩중"; kl="준비중"
    try:    ih=gen_issues(mkt); print("  ✅ 이슈")
    except Exception as e: print(f"  이슈실패:{e}"); ih='<div class="issue-row">• 로딩중</div>'
    try:    mh=gen_macro(mkt); print("  ✅ 매크로")
    except Exception as e: print(f"  매크로실패:{e}"); mh='<p class="nl-body">로딩중</p>'
    try:    cn=gen_brief("cn"); print("  ✅ 중국")
    except Exception as e: print(f"  중국실패:{e}"); cn="로딩중"
    try:    jp=gen_brief("jp"); print("  ✅ 일본")
    except Exception as e: print(f"  일본실패:{e}"); jp="로딩중"
    html=build_html(mkt,hl,sb,kl,ih,mh,cn,jp,fred_script)
    out=Path("docs/index.html"); out.parent.mkdir(exist_ok=True)
    out.write_text(html,encoding="utf-8")
    print(f"  ✅ 완료 {len(html):,}bytes")

if __name__=="__main__":
    main()
