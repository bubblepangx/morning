import os
import json
import requests
import yfinance as yf
from datetime import datetime
import pytz

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FRED_API_KEY = "b7aade0c896f05f64dea3071c81c8e39"

def get_indices():
    tickers = {"S&P 500":"^GSPC","NASDAQ":"^IXIC","Dow Jones":"^DJI","Russell 2000":"^RUT","VIX":"^VIX"}
    result = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker); hist = t.history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]; close = hist["Close"].iloc[-1]; chg = (close-prev)/prev*100
            elif len(hist) == 1:
                close = hist["Close"].iloc[-1]; chg = 0
            else:
                close, chg = 0, 0
            result.append({"name":name,"price":close,"change":chg})
        except:
            result.append({"name":name,"price":0,"change":0})
    return result

def get_forex_commodities():
    items = {"달러인덱스":"DX-Y.NYB","원/달러":"KRW=X","엔/달러":"JPY=X","위안/달러":"CNY=X","금":"GC=F","은":"SI=F","WTI 원유":"CL=F","구리":"HG=F"}
    result = []
    for name, ticker in items.items():
        try:
            t = yf.Ticker(ticker); hist = t.history(period="2d")
            if len(hist) >= 2:
                prev = hist["Close"].iloc[-2]; close = hist["Close"].iloc[-1]; chg = (close-prev)/prev*100
            elif len(hist) == 1:
                close = hist["Close"].iloc[-1]; chg = 0
            else:
                close, chg = 0, 0
            result.append({"name":name,"price":close,"change":chg})
        except:
            result.append({"name":name,"price":0,"change":0})
    return result

def get_fred(series_id, limit=24):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {"series_id":series_id,"api_key":FRED_API_KEY,"file_type":"json","sort_order":"desc","limit":limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        obs = r.json().get("observations",[])
        data = [(o["date"],float(o["value"])) for o in obs if o["value"]!="."]
        data.reverse(); return data
    except:
        return []

def get_crypto():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
            params={"ids":"bitcoin,ethereum,solana","vs_currencies":"usd","include_24hr_change":"true"}, timeout=10)
        d = r.json()
        return [
            {"name":"BTC","price":d["bitcoin"]["usd"],"change":d["bitcoin"]["usd_24h_change"]},
            {"name":"ETH","price":d["ethereum"]["usd"],"change":d["ethereum"]["usd_24h_change"]},
            {"name":"SOL","price":d["solana"]["usd"],"change":d["solana"]["usd_24h_change"]},
        ]
    except:
        return [{"name":"BTC","price":0,"change":0},{"name":"ETH","price":0,"change":0},{"name":"SOL","price":0,"change":0}]

def get_crypto_fear_greed():
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()["data"][0]
        return {"value":int(d["value"]),"label":d["value_classification"]}
    except:
        return {"value":50,"label":"Neutral"}

def get_cnn_fear_greed():
    try:
        r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        d = r.json()["fear_and_greed"]
        return {"value":int(float(d["score"])),"label":d["rating"]}
    except:
        return {"value":50,"label":"Neutral"}

def get_ai_content(indices, forex):
    if not ANTHROPIC_API_KEY:
        return {"headline":"API 키 설정 후 자동 생성됩니다","summary":"ANTHROPIC_API_KEY를 GitHub Secrets에 등록해주세요.","issues":[],"newsletter":""}

    idx_text = "\n".join([f"- {i['name']}: {i['price']:.2f} ({i['change']:+.2f}%)" for i in indices])

    prompt = f"""오늘 날짜: {datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y년 %m월 %d일')}

현재 시장 데이터:
{idx_text}

당신은 월스트리트저널 수석 금융 특파원입니다. 오늘 미국 주식시장 마감 뉴스를 웹에서 철저히 검색한 뒤, 아래 3가지 섹션을 작성해주세요.

===SECTION1===
[데일리 시장 마감 시황]

헤드라인: (따옴표 없이, 핵심을 담은 강렬한 제목 한 줄)

본문: 전날 미국 주식시장 마감 상황을 최소 5~7단락으로 심층 분석해 주세요.
- 첫 단락: 3대 지수 및 주요 지수 마감 수치와 전반적 시장 분위기
- 둘째 단락: 당일 가장 큰 시장 이슈(연준 발언, 경제지표, 지정학 등) 심층 분석
- 셋째 단락: 섹터별 동향 — 어떤 섹터가 강세/약세였는지, 그 이유
- 넷째 단락: 주요 종목 움직임 (실적 발표, 급등락 종목, 이유)
- 다섯째 단락: 채권·달러·원자재 등 매크로 자산 동향
- 여섯째 단락: 투자자 심리 및 다음 날/다음 주 주목할 이벤트
- 마지막: "핵심 한 줄:" 로 시작하는 오늘 시장을 압축하는 한 문장

문체: 월스트리트저널 스타일. 사실에 근거하되 서사가 있고, 숫자와 맥락을 함께 전달. 한국어로 작성.

===SECTION2===
[오늘의 주요 이슈]

아래 형식으로 7~15개 작성:
• 🏦 연준 | 구체적 발언자·수치 포함
• 📈 실적 서프라이즈 | 종목명 EPS/매출 수치 포함
• 📉 실적 쇼크 | 종목명 EPS/매출 수치 포함
• 🚀 급등 종목 | 종목명 등락률·이유
• 💥 급락 종목 | 종목명 등락률·이유
• 🤖 AI·테크 | 구체적 사건
• 🇨🇳 미중 | 무역·정책 이슈
• 💵 달러·금리 | 수치 포함
• 🛢️ 원유·원자재 | 수치 포함
• 🏛️ 정책·규제 | 구체적 내용
• 🌏 국제 | 주요 해외 이슈
해당하는 것만 포함. 각 줄은 "• 이모지 카테고리 | 내용" 형식 필수.

===SECTION3===
[글로벌 매크로 뉴스레터]

오늘 시장에서 가장 중요한 매크로 테마 3~4가지를 골라 각각 애널리스트 리포트 스타일로 작성:

[ 테마 제목 1 ]
- 사건/배경: 무슨 일이 있었는가
- 시장 반응: 어떻게 반영되었는가
- 핵심 수치: 관련 데이터
- 시사점: 투자자가 주목해야 할 포인트
(3~4단락 분량)

[ 테마 제목 2 ]
(동일 형식)

[ 테마 제목 3 ]
(동일 형식)

한국어로 작성. 전문 애널리스트가 기관 투자자에게 보내는 압축 리포트 문체."""

    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
            json={"model":"claude-haiku-4-5-20251001","max_tokens":6000,
                  "tools":[{"type":"web_search_20250305","name":"web_search"}],
                  "messages":[{"role":"user","content":prompt}]}, timeout=90)
        content = r.json()
        text = "".join(b["text"] for b in content.get("content",[]) if b.get("type")=="text")

        s1=s2=s3=""
        if "===SECTION1===" in text:
            rest = text.split("===SECTION1===")[1]
            if "===SECTION2===" in rest:
                s1 = rest.split("===SECTION2===")[0].strip()
                rest2 = rest.split("===SECTION2===")[1]
                if "===SECTION3===" in rest2:
                    s2 = rest2.split("===SECTION3===")[0].strip()
                    s3 = rest2.split("===SECTION3===")[1].strip()
                else:
                    s2 = rest2.strip()
            else:
                s1 = rest.strip()
        else:
            s1 = text

        lines = s1.strip().split("\n")
        headline = ""
        body_lines = []
        for line in lines:
            if line.strip().startswith("헤드라인:"):
                headline = line.replace("헤드라인:","").strip()
            elif line.strip().startswith("본문:"):
                continue
            else:
                body_lines.append(line)
        if not headline and lines:
            headline = lines[0].strip()
            body_lines = lines[1:]
        body = "\n".join(body_lines).strip()

        issues = [l.strip() for l in s2.split("\n") if l.strip().startswith("•") and "|" in l]
        return {"headline":headline,"summary":body,"issues":issues,"newsletter":s3}
    except Exception as e:
        return {"headline":"데이터 로딩 중 오류 발생","summary":str(e),"issues":[],"newsletter":""}

def get_all_fred():
    return {
        "cpi":get_fred("CPIAUCSL"),"core_cpi":get_fred("CPILFESL"),"ppi":get_fred("PPIACO"),
        "unrate":get_fred("UNRATE"),"fedfunds":get_fred("FEDFUNDS"),
        "t2y":get_fred("GS2"),"t10y":get_fred("GS10"),"hyspread":get_fred("BAMLH0A0HYM2"),
    }

def build_html(indices, forex, crypto, crypto_fg, cnn_fg, ai, fred):
    now_kst = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y년 %m월 %d일 %H:%M KST')
    date_kst = datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y년 %m월 %d일')

    def idx_cards(data):
        out=""
        for d in data:
            col="#e53e3e" if d["change"]>=0 else "#3182ce"
            arr="▲" if d["change"]>=0 else "▼"
            out+=f'<div class="card"><div class="card-label">{d["name"]}</div><div class="card-value">{d["price"]:,.2f}</div><div class="card-change" style="color:{col}">{arr} {abs(d["change"]):.2f}%</div></div>'
        return out

    def forex_cards(data, group):
        out=""
        for d in data:
            col="#e53e3e" if d["change"]>=0 else "#3182ce"
            arr="▲" if d["change"]>=0 else "▼"
            price=f'{d["price"]:,.2f}' if group=="forex" else f'${d["price"]:,.2f}'
            out+=f'<div class="card"><div class="card-label">{d["name"]}</div><div class="card-value">{price}</div><div class="card-change" style="color:{col}">{arr} {abs(d["change"]):.2f}%</div></div>'
        return out

    def crypto_cards(data):
        out=""
        for d in data:
            col="#e53e3e" if d["change"]>=0 else "#3182ce"
            arr="▲" if d["change"]>=0 else "▼"
            out+=f'<div class="card"><div class="card-label">{d["name"]}</div><div class="card-value">${d["price"]:,.0f}</div><div class="card-change" style="color:{col}">{arr} {abs(d["change"]):.2f}%</div></div>'
        return out

    def fg_gauge(val, label, title):
        if val<=25: col="#e53e3e"
        elif val<=45: col="#dd6b20"
        elif val<=55: col="#d69e2e"
        elif val<=75: col="#38a169"
        else: col="#2f855a"
        return f"""<div class="gauge-box">
            <div class="gauge-title">{title}</div>
            <div class="gauge-bar-bg"><div class="gauge-bar-fill" style="width:{val}%;background:{col}"></div></div>
            <div class="gauge-info"><span style="color:{col};font-weight:700;font-size:1.5rem">{val}</span><span style="color:#718096;margin-left:10px;font-size:0.9rem">{label}</span></div>
        </div>"""

    def fred_chart(title, datasets):
        traces=[]; colors=["#2563eb","#dc2626","#16a34a","#d97706","#7c3aed"]
        for i,(label,data) in enumerate(datasets):
            if not data: continue
            xs=[d[0] for d in data]; ys=[d[1] for d in data]
            traces.append(f'{{x:{json.dumps(xs)},y:{json.dumps(ys)},name:"{label}",type:"scatter",mode:"lines",line:{{color:"{colors[i%5]}",width:2}}}}')
        if not traces: return f'<div style="padding:20px;color:#999;text-align:center">{title} 데이터 없음</div>'
        sid=title.replace(" ","_").replace("(","").replace(")","").replace("%","pct").replace("&","and")
        return f"""<div class="chart-box"><div class="chart-label">{title}</div>
            <div id="c_{sid}" style="width:100%;height:260px"></div>
            <script>Plotly.newPlot("c_{sid}",[{",".join(traces)}],{{margin:{{t:10,b:40,l:50,r:10}},legend:{{orientation:"h",y:-0.25,font:{{size:11}}}},paper_bgcolor:"transparent",plot_bgcolor:"transparent",xaxis:{{gridcolor:"#f1f5f9",tickfont:{{size:10}}}},yaxis:{{gridcolor:"#f1f5f9",tickfont:{{size:10}}}}}},{{responsive:true,displayModeBar:false}});</script></div>"""

    def tv_widget(symbol, height=1000):
        return f"""<div class="tv-wrap" style="height:{height}px">
            <div class="tradingview-widget-container" style="height:100%;width:100%">
                <div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js" async>
                {{"autosize":true,"symbol":"{symbol}","interval":"D","timezone":"America/New_York","theme":"light","style":"1","locale":"kr","enable_publishing":false,"hide_top_toolbar":false,"hide_legend":false,"save_image":false,"studies":["MASimple@tv-basicstudies","Volume@tv-basicstudies"]}}
                </script>
            </div>
        </div>"""

    def tv_heatmap(height=600):
        return f"""<div class="tv-wrap" style="height:{height}px">
            <div class="tradingview-widget-container" style="height:100%;width:100%">
                <div class="tradingview-widget-container__widget" style="height:100%;width:100%"></div>
                <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" async>
                {{"exchanges":[],"dataSource":"SPX500","grouping":"sector","blockSize":"market_cap_basic","blockColor":"change","locale":"kr","symbolUrl":"","colorTheme":"light","hasTopBar":true,"isDataSetEnabled":false,"isZoomEnabled":true,"hasSymbolTooltip":true,"width":"100%","height":"100%"}}
                </script>
            </div>
        </div>"""

    # 지수 차트
    index_charts=""
    for sym,label in [("AMEX:SPY","S&P 500 — SPY"),("NASDAQ:QQQ","NASDAQ — QQQ"),("AMEX:DIA","Dow Jones — DIA"),("AMEX:IWM","Russell 2000 — IWM")]:
        index_charts+=f'<div class="chart-label" style="margin:28px 0 8px">{label}</div>'+tv_widget(sym,1000)

    # ETF 차트 (VIX 포함, VIXY 제거)
    etf_charts=""
    for sym,label in [("XLE","XLE — 에너지"),("SOXX","SOXX — 반도체"),("ARKK","ARKK — 혁신"),("RSP","RSP — S&P 동일가중"),("TVC:VIX","VIX — 변동성지수")]:
        etf_charts+=f'<div class="chart-label" style="margin:28px 0 8px">{label}</div>'+tv_widget(sym,850)

    # 종목 차트
    stock_charts=""
    for sym in ["AAPL","MSFT","NVDA","GOOGL","AMZN","META","TSLA","MSTR","COIN"]:
        stock_charts+=f'<div class="chart-label" style="margin:28px 0 8px">{sym}</div>'+tv_widget(sym,850)

    # 코인 차트
    crypto_charts=""
    for sym,label in [("BINANCE:BTCUSDT","Bitcoin — BTC/USDT"),("BINANCE:ETHUSDT","Ethereum — ETH/USDT"),("BINANCE:SOLUSDT","Solana — SOL/USDT")]:
        crypto_charts+=f'<div class="chart-label" style="margin:28px 0 8px">{label}</div>'+tv_widget(sym,850)

    # DXY 차트
    dxy_chart = tv_widget("TVC:DXY", 850)

    # 푸엘 멀티플
    puell = """<div class="chart-label" style="margin:0 0 8px">Bitcoin Puell Multiple</div>
    <div style="width:100%;height:550px;border-radius:10px;overflow:hidden;border:1px solid #e2e8f0;margin-bottom:16px">
        <iframe src="https://charts.bitbo.io/puell-multiple/" style="width:100%;height:100%;border:none" title="Puell Multiple"></iframe>
    </div>"""

    # FRED
    fred_html=""
    fred_html+=fred_chart("물가 지표 YoY %",[("CPI",fred["cpi"]),("Core CPI",fred["core_cpi"]),("PPI",fred["ppi"])])
    fred_html+=fred_chart("실업률 & Fed 금리 %",[("실업률",fred["unrate"]),("Fed Funds",fred["fedfunds"])])
    fred_html+=fred_chart("국채 수익률 %",[("2년물",fred["t2y"]),("10년물",fred["t10y"])])
    fred_html+=fred_chart("하이일드 스프레드 %",[("HY Spread",fred["hyspread"])])

    # 이슈
    issues_html="".join(f'<div class="issue-row">{i}</div>' for i in ai.get("issues",[]))

    # 뉴스레터
    newsletter_html=""
    for para in ai.get("newsletter","").split("\n\n"):
        para=para.strip()
        if not para: continue
        if "\n" in para:
            fl=para.split("\n")[0]; rest="\n".join(para.split("\n")[1:])
            if fl.startswith("["):
                newsletter_html+=f'<div class="nl-topic">{fl}</div><p class="nl-body">{rest.replace(chr(10),"<br>")}</p>'
            else:
                newsletter_html+=f'<p class="nl-body">{para.replace(chr(10),"<br>")}</p>'
        else:
            newsletter_html+=(f'<div class="nl-topic">{para}</div>' if para.startswith("[") else f'<p class="nl-body">{para}</p>')

    # 시황 본문 — 핵심 한 줄 하이라이트
    summary_text = ai.get('summary','')
    if '핵심 한 줄:' in summary_text:
        parts = summary_text.split('핵심 한 줄:')
        summary_html = f'<div class="summary-body">{parts[0].strip()}</div><div class="summary-keyline"><strong>핵심 한 줄</strong> {parts[1].strip()}</div>'
    else:
        summary_html = f'<div class="summary-body">{summary_text}</div>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Daily US Market Dashboard</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=Noto+Sans+KR:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Noto Sans KR',sans-serif;background:#f8f9fb;color:#1a1a2e;line-height:1.7}}

  /* ── 헤더 ── */
  .site-header{{background:#fff;border-bottom:1px solid #e8eaed;padding:32px 24px 24px;text-align:center}}
  .site-header h1{{font-family:'DM Serif Display',serif;font-size:2rem;font-weight:400;color:#111;letter-spacing:-0.5px}}
  .site-header .meta{{font-size:0.82rem;color:#9ca3af;margin-top:6px;letter-spacing:0.3px}}
  .site-header .meta span{{color:#374151;font-weight:600}}

  /* ── 컨테이너 ── */
  .wrap{{max-width:900px;margin:0 auto;padding:32px 20px}}

  /* ── 섹션 공통 ── */
  .block{{background:#fff;border-radius:14px;padding:28px 32px;margin-bottom:24px;border:1px solid #e8eaed}}
  .block-title{{font-size:0.72rem;font-weight:700;color:#9ca3af;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:20px;display:flex;align-items:center;gap:8px}}
  .block-title::after{{content:'';flex:1;height:1px;background:#f0f0f0}}

  /* ── 시황 ── */
  .article-headline{{font-family:'DM Serif Display',serif;font-size:1.55rem;font-weight:400;color:#111;line-height:1.4;margin-bottom:20px}}
  .summary-body{{font-size:0.95rem;line-height:2;color:#374151;white-space:pre-wrap}}
  .summary-keyline{{margin-top:20px;padding:14px 18px;background:#fffbeb;border-left:3px solid #f59e0b;border-radius:0 8px 8px 0;font-size:0.9rem;color:#92400e;line-height:1.6}}

  /* ── 이슈 ── */
  .issue-row{{font-size:0.88rem;line-height:1.7;color:#374151;padding:10px 0;border-bottom:1px solid #f3f4f6}}
  .issue-row:last-child{{border-bottom:none}}

  /* ── 지수 카드 ── */
  .cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:10px}}
  .card{{background:#f9fafb;border:1px solid #e8eaed;border-radius:10px;padding:14px;text-align:center}}
  .card-label{{font-size:0.7rem;color:#9ca3af;margin-bottom:5px;font-weight:600;letter-spacing:0.3px}}
  .card-value{{font-size:1.1rem;font-weight:700;color:#111;margin-bottom:3px;font-variant-numeric:tabular-nums}}
  .card-change{{font-size:0.8rem;font-weight:600}}

  /* ── 게이지 ── */
  .gauge-row{{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
  .gauge-box{{padding:4px 0}}
  .gauge-title{{font-size:0.78rem;color:#6b7280;margin-bottom:10px;font-weight:600}}
  .gauge-bar-bg{{background:#f3f4f6;border-radius:99px;height:10px;overflow:hidden}}
  .gauge-bar-fill{{height:100%;border-radius:99px}}
  .gauge-info{{margin-top:8px;display:flex;align-items:baseline;gap:8px}}

  /* ── 차트 ── */
  .chart-label{{font-size:0.78rem;font-weight:700;color:#6b7280;letter-spacing:0.5px;text-transform:uppercase}}
  .chart-box{{margin-bottom:24px}}
  .tv-wrap{{width:100%;margin-bottom:8px;border-radius:10px;overflow:hidden;border:1px solid #e8eaed}}
  .tradingview-widget-container,.tradingview-widget-container__widget{{height:100%!important;width:100%!important}}
  .subsection-label{{font-size:0.72rem;font-weight:700;color:#9ca3af;letter-spacing:1px;text-transform:uppercase;margin:20px 0 12px;padding-bottom:8px;border-bottom:1px solid #f3f4f6}}

  /* ── 뉴스레터 ── */
  .nl-topic{{font-size:0.95rem;font-weight:700;color:#111;margin:22px 0 8px;padding:10px 14px;background:#f0f4ff;border-left:3px solid #3b82f6;border-radius:0 8px 8px 0}}
  .nl-body{{font-size:0.9rem;line-height:1.95;color:#374151;margin-bottom:12px}}

  /* ── 반응형 ── */
  @media(max-width:600px){{
    .cards{{grid-template-columns:repeat(2,1fr)}}
    .gauge-row{{grid-template-columns:1fr}}
    .wrap{{padding:20px 14px}}
    .block{{padding:20px 18px}}
    .article-headline{{font-size:1.25rem}}
    .site-header h1{{font-size:1.5rem}}
  }}
</style>
</head>
<body>

<div class="site-header">
  <h1>Daily US Market Dashboard</h1>
  <div class="meta"><span>{date_kst}</span> &nbsp;|&nbsp; 자동 생성 &nbsp;|&nbsp; 업데이트 {now_kst}</div>
</div>

<div class="wrap">

  <!-- 1. 데일리 시황 -->
  <div class="block">
    <div class="block-title">데일리 시장 마감 시황 <span style="color:#3b82f6;font-weight:500;text-transform:none;letter-spacing:0">Claude AI · web search</span></div>
    <div class="article-headline">{ai.get('headline','')}</div>
    {summary_html}
  </div>

  <!-- 2. 주요 이슈 -->
  <div class="block">
    <div class="block-title">오늘의 주요 이슈 <span style="color:#3b82f6;font-weight:500;text-transform:none;letter-spacing:0">Claude AI</span></div>
    {issues_html if issues_html else '<div style="color:#9ca3af;font-size:0.9rem">이슈 수집 중입니다.</div>'}
  </div>

  <!-- 3. 주요 지수 -->
  <div class="block">
    <div class="block-title">주요 지수 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">yfinance</span></div>
    <div class="cards">{idx_cards(indices)}</div>
  </div>

  <!-- 4. 지수 차트 -->
  <div class="block">
    <div class="block-title">지수 캔들차트 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView · ETF</span></div>
    {index_charts}
  </div>

  <!-- 5. S&P500 히트맵 -->
  <div class="block">
    <div class="block-title">S&amp;P 500 섹터 히트맵 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView</span></div>
    {tv_heatmap(600)}
  </div>

  <!-- 6. 공포탐욕지수 -->
  <div class="block">
    <div class="block-title">공포 &amp; 탐욕 지수 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">CNN · alternative.me</span></div>
    <div class="gauge-row">
      {fg_gauge(cnn_fg['value'], cnn_fg['label'], '📺 CNN 공포탐욕지수 (주식)')}
      {fg_gauge(crypto_fg['value'], crypto_fg['label'], '₿ 크립토 공포탐욕지수')}
    </div>
  </div>

  <!-- 7. 환율·원자재 -->
  <div class="block">
    <div class="block-title">환율 &amp; 원자재 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">yfinance</span></div>
    <div class="subsection-label">환율</div>
    <div class="cards">{forex_cards(forex[:4],'forex')}</div>
    <div class="subsection-label" style="margin-top:20px">원자재</div>
    <div class="cards">{forex_cards(forex[4:],'commodity')}</div>
  </div>

  <!-- 8. DXY 차트 -->
  <div class="block">
    <div class="block-title">달러 인덱스 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView · TVC:DXY</span></div>
    <div class="chart-label">US Dollar Index (DXY)</div>
    {dxy_chart}
  </div>

  <!-- 9. FRED 경제지표 -->
  <div class="block">
    <div class="block-title">경제지표 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">FRED API</span></div>
    {fred_html}
  </div>

  <!-- 10. 코인 가격 -->
  <div class="block">
    <div class="block-title">코인 가격 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">CoinGecko</span></div>
    <div class="cards">{crypto_cards(crypto)}</div>
  </div>

  <!-- 11. 푸엘 멀티플 -->
  <div class="block">
    <div class="block-title">비트코인 온체인 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">bitbo.io</span></div>
    {puell}
  </div>

  <!-- 12. 코인 캔들차트 -->
  <div class="block">
    <div class="block-title">코인 캔들차트 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView · Binance</span></div>
    {crypto_charts}
  </div>

  <!-- 13. 매크로 뉴스레터 -->
  <div class="block">
    <div class="block-title">글로벌 매크로 뉴스레터 <span style="color:#3b82f6;font-weight:500;text-transform:none;letter-spacing:0">Claude AI · 애널리스트 리포트</span></div>
    {newsletter_html if newsletter_html else '<div style="color:#9ca3af;font-size:0.9rem">분석 준비 중입니다.</div>'}
  </div>

  <!-- 14. ETF·VIX 차트 -->
  <div class="block">
    <div class="block-title">주요 ETF &amp; VIX <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView</span></div>
    {etf_charts}
  </div>

  <!-- 15. 빅테크 종목 차트 -->
  <div class="block">
    <div class="block-title">빅테크 &amp; 주요 종목 <span style="color:#9ca3af;font-weight:400;text-transform:none;letter-spacing:0">TradingView</span></div>
    {stock_charts}
  </div>

</div>
</body>
</html>"""
    return html

if __name__ == "__main__":
    print("📡 데이터 수집 중...")
    indices = get_indices()
    forex = get_forex_commodities()
    crypto = get_crypto()
    crypto_fg = get_crypto_fear_greed()
    print("📺 CNN 공포탐욕지수 수집 중...")
    cnn_fg = get_cnn_fear_greed()
    print("🤖 Claude AI 시황 생성 중...")
    ai = get_ai_content(indices, forex)
    print("📊 FRED 경제지표 수집 중...")
    fred = get_all_fred()
    print("🖥️ HTML 생성 중...")
    html = build_html(indices, forex, crypto, crypto_fg, cnn_fg, ai, fred)
    with open("index.html","w",encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html 생성 완료!")
