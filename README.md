# FundLens — ETF 分析與資產配置平台

## 目錄結構

```
FundAnalyst/
├── venv/                        # Python 虛擬環境（不進 git）
├── backend/
│   ├── app.py                   # Flask 主程式
│   ├── data_source.py           # 資料來源整合層（MoneyDJ + FinMind）
│   ├── fund_mapper.py           # MoneyDJ 代號 ↔ FinMind 代號對照表
│   ├── fund_mapping.json        # 對照表快取（由 fund_mapper.py 產生）
│   ├── calculators/
│   │   ├── returns.py           # 報酬率計算
│   │   ├── risk.py              # 風險指標（MDD、波動率）
│   │   ├── ratios.py            # Sharpe、Sortino、Calmar
│   │   ├── capm.py              # Alpha、Beta
│   │   ├── scoring.py           # 多準則評分模型（MCDA）
│   │   ├── mvo.py               # 均值變異數最佳化（MVO）
│   │   └── backtest.py          # 回測引擎
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── moneydj.py           # MoneyDJ 爬蟲（基金清單、NAV）
│   │   ├── sitca.py             # RR 評級分類器（依投信投顧公會規則）
│   │   └── cache.py             # 爬蟲結果 JSON 快取
│   └── requirements.txt
└── frontend/
    ├── index.html               # 首頁（ETF 搜尋與列表）
    ├── fund.html                # 單一 ETF 分析頁
    ├── compare.html             # 投資組合比較頁
    ├── score.html               # 多準則評分排名頁
    ├── allocate.html            # 資產配置最佳化 + 回測頁
    ├── css/style.css
    └── js/
        ├── api.js
        └── charts.js
```

---

## 第一次環境建置（只需做一次）

```bash
cd /Users/doris/Developer/FundAnalyst

# 建立虛擬環境
python3 -m venv venv

# 啟動虛擬環境
source venv/bin/activate

# 安裝依賴
pip install -r backend/requirements.txt
```

### 建立 MoneyDJ × FinMind 對照表（只需做一次）

MoneyDJ 使用自己的基金代號（ACFP132），FinMind 使用證交所代號（00892）。
首次使用前需建立對照表：

```bash
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 fund_mapper.py
```

執行完後會產生 `backend/fund_mapping.json`，之後不需要重跑。
若要更新對照表（例如有新 ETF 上市），重新執行一次即可。

---

## 每次開發前：啟動流程

### Terminal 1 — 後端

```bash
cd /Users/doris/Developer/FundAnalyst
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 app.py
```

看到以下訊息代表後端正常：
```
* Running on http://127.0.0.1:5000
```

### Terminal 2 — 前端

```bash
cd /Users/doris/Developer/FundAnalyst/frontend
python3 -m http.server 8080
```

---

## 開瀏覽器

| 網址 | 用途 |
|------|------|
| `http://localhost:8080` | 首頁（ETF 搜尋與列表） |
| `http://localhost:8080/fund.html?id=0050` | 單一 ETF 分析頁 |
| `http://localhost:8080/compare.html` | 投資組合比較頁 |
| `http://localhost:8080/score.html` | 多準則評分排名頁 |
| `http://localhost:8080/allocate.html` | 資產配置最佳化頁 |
| `http://localhost:5000/funds` | 直接測試後端 API |

---

## API 端點一覽

| Method | Path | 說明 |
|--------|------|------|
| GET | `/funds` | ETF 列表（支援 q / type / sort / limit） |
| GET | `/funds/<id>` | 單一 ETF 基本資訊（含 RR 評級、規模） |
| GET | `/funds/<id>/nav?period=3Y` | 歷史收盤價 |
| GET | `/funds/<id>/metrics?period=3Y` | 風險指標（Sharpe、MDD、Beta 等） |
| POST | `/compare` | 多 ETF 比較 |
| POST | `/score` | 多準則評分排名 |
| GET | `/score/defaults` | 預設權重設定 |
| POST | `/optimize` | MVO 資產配置最佳化 |
| POST | `/backtest` | 回測（MVO vs 等權重） |

---

## 資料來源說明

| 資料 | 來源 | 說明 |
|------|------|------|
| ETF 清單、名稱、投信公司 | MoneyDJ 爬蟲 | 每日快取 24 小時 |
| ETF 歷史收盤價 | FinMind `TaiwanStockPrice` | 自動分頁拼接（>1000 筆） |
| 基準指數（0050） | FinMind `TaiwanStockPrice` | — |
| 基金規模（AUM） | FinMind `TaiwanStockMarketValue` | 市值換算億元 |
| RR 風險評級 | 規則式分類器 | 依投信投顧公會分類標準實作 |

### 關於 RR 評級

MoneyDJ 與基金資訊觀測站的 RR 評級均以 JavaScript 動態載入，無法以靜態爬蟲取得。
本系統依投信投顧公會「基金風險報酬等級分類標準」實作規則式分類器，
依基金類型、投資標的與槓桿特性自動判定 RR1–RR5，與官方公告等級具有相同依據。

### FinMind 免費方案限制

- 每日最高 **600 次**請求
- 單次最多 **1000 筆**資料（系統已自動分頁處理）
- 評分排名一次約消耗 12+ 次請求（每檔 ETF 各一次），請避免頻繁觸發

---

## MoneyDJ 爬蟲快取管理

```bash
cd backend
source ../venv/bin/activate

# 清除所有爬蟲快取（強制重新爬取）
python3 -c "from scraper.cache import clear_all; clear_all()"

# 重新建立基金清單快取
python3 -c "from scraper.moneydj import scrape_fund_list; scrape_fund_list(use_cache=False)"
```

---

## 常見問題

**`ModuleNotFoundError: No module named 'flask'`**
→ 虛擬環境沒啟動，執行 `source venv/bin/activate`

**`ModuleNotFoundError: No module named 'scipy'`**
→ 執行 `pip install -r backend/requirements.txt`

**`400 Bad Request` 打 FinMind API**
→ Token 有空白或換行，重新 `export FINMIND_TOKEN="token"` 確認沒有多餘字元

**`fund_mapping.json` 不存在**
→ 執行 `python3 fund_mapper.py` 建立對照表

**前端打開是空白或 API 失敗**
→ 確認後端有跑（Terminal 1 有 Running on 5000）
→ 確認前端用 `http://localhost:8080` 開，不是直接開 HTML 檔案

**評分排名或資產配置很慢（30–60 秒）**
→ 正常現象，需對每檔 ETF 個別打 FinMind API 抓歷史資料

**MoneyDJ 爬蟲回傳空清單**
→ 執行 `python3 -c "from scraper.cache import clear_all; clear_all()"` 清快取後重試
