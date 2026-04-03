# 基金分析平台（FundLens）

## 目錄結構

```
fund-analysis/
├── backend/
│   ├── app.py                # Flask 入口，所有 API 端點
│   ├── requirements.txt      # Python 依賴
│   ├── calculators/
│   │   ├── __init__.py
│   │   ├── returns.py        # 報酬率、年化報酬、標準化
│   │   ├── risk.py           # 標準差、下行標準差、MDD
│   │   ├── ratios.py         # Sharpe、Sortino、Calmar
│   │   └── capm.py           # Alpha、Beta
│   └── data/
│       ├── README.md         # 資料格式說明
│       ├── funds_info.csv    # （待放入）基金基本資訊
│       ├── nav_history.csv   # （待放入）歷史淨值
│       └── benchmark.csv     # （待放入）基準指數
│
└── frontend/
    ├── index.html            # 首頁（搜尋 + 排行 + 列表）
    ├── fund.html             # 單一基金分析頁
    ├── compare.html          # 投資組合比較頁
    ├── css/
    │   └── style.css         # 全站樣式（色彩變數 + 元件）
    └── js/
        ├── api.js            # 所有後端 API 呼叫 + localStorage
        └── charts.js         # 所有 Chart.js 圖表邏輯
```

## 啟動方式

### 後端

```bash
cd backend
pip install -r requirements.txt
python app.py
# 後端跑在 http://localhost:5000
```

### 前端

直接用瀏覽器開啟 `frontend/index.html`，
或用 VS Code Live Server 啟動。

## API 端點一覽

| Method | Path | 說明 |
|--------|------|------|
| GET | /funds | 基金列表（支援搜尋、篩選、排序） |
| GET | /funds/:id | 單一基金基本資訊 |
| GET | /funds/:id/nav | 歷史 NAV（period=1Y/3Y/5Y）|
| GET | /funds/:id/metrics | 風險指標（period=1Y/3Y/5Y）|
| POST | /compare | 多基金比較（body: fund_ids, period）|

## Week 1 TODO 清單

- [ ] 確認資料來源，整理好 CSV 放入 data/
- [ ] 確認基準指數（台灣加權 or 其他）
- [ ] 確認無風險利率設定
- [ ] `pip install -r requirements.txt` 確認環境跑起來
- [ ] 打 GET /funds 確認後端有回應