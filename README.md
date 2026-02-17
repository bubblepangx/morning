# 📊 Daily US Market Dashboard

매일 07:00 KST 자동 생성되는 미국 시장 대시보드.

## 포함 내용
- 데일리 시황 (Claude AI 생성)
- 주요 이슈 10개
- 주요 지수·원자재·환율·코인 실시간 카드
- TradingView 차트 (지수 ETF, 원자재, 코인, ETF, 빅테크)
- S&P500 히트맵 / 코인 히트맵
- 공포탐욕지수 게이지
- MOVE 지수 & 풋콜비율 차트
- FRED 실시간 경제지표 (CPI, 금리, 국채수익률)
- Truflation 실시간 인플레이션
- 글로벌 매크로 뉴스레터 (Claude AI)
- 중국·홍콩·일본 증시 브리핑 (Claude AI)

---

## 🚀 세팅 방법 (5단계)

### 1. 레포 Fork 또는 Clone
```bash
git clone https://github.com/YOUR_USERNAME/dashboard-auto.git
cd dashboard-auto
```

### 2. GitHub Pages 활성화
- 레포 → Settings → Pages
- Source: **Deploy from a branch**
- Branch: `main` / Folder: `/docs`
- Save → 몇 분 후 `https://YOUR_USERNAME.github.io/dashboard-auto` 접속 가능

### 3. Secrets 등록 (API 키)
레포 → Settings → Secrets and variables → Actions → **New repository secret**

| Secret 이름 | 값 |
|---|---|
| `ANTHROPIC_API_KEY` | sk-ant-api03-... |
| `FRED_API_KEY` | (FRED에서 발급한 키) |

### 4. 첫 실행 테스트
- Actions 탭 → **Daily Dashboard Generator** → **Run workflow**
- 약 2~3분 후 `docs/index.html` 생성 확인

### 5. 자동 실행 확인
- 매일 06:50 KST에 자동 실행
- Actions 탭에서 실행 로그 확인 가능

---

## 📁 파일 구조
```
dashboard-auto/
├── generate.py              # 메인 생성 스크립트
├── requirements.txt         # Python 패키지
├── templates/
│   └── dashboard.html       # HTML 템플릿
├── docs/
│   └── index.html           # 생성된 결과물 (GitHub Pages 배포)
└── .github/
    └── workflows/
        └── daily.yml        # GitHub Actions 설정
```

## 💰 월 예상 비용
| 항목 | 비용 |
|---|---|
| GitHub Actions | 무료 |
| GitHub Pages | 무료 |
| Claude API | ~$3~6/월 |
| FRED API | 무료 |
| **합계** | **~$3~6/월** |
