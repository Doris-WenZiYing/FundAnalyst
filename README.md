# FundLens — ETF 分析與成分股篩選平台

本專案分兩個階段開發：

| 階段 | 時間 | 內容 |
|------|------|------|
| 第一階段 | 2026 上學期 | ETF 分析平台：ETF 搜尋、單檔分析、組合比較、多準則評分、MVO 資產配置與回測 |
| 第二階段 | 2026 下學期（進行中，預計 2026/12 中結案） | ETF 成分股篩選：以 ETF 成分股為母體，依財務指標篩選、依報酬率排序選股，與 ETF 本身比較 |

第二階段沿用第一階段的架構（Flask 後端、原生 HTML/JS 前端、FinMind 資料），新功能集中在「成分股篩選」頁。

---

## 目錄結構

```
FundAnalyst/
├── venv/                         # Python 虛擬環境（不進 git）
├── requirements.txt              # Python 套件
├── README.md
├── backend/
│   ├── app.py                    # Flask 主程式（第一、二階段 API）
│   ├── data_source.py            # 第一階段資料層（MoneyDJ 清單 + 價格）
│   ├── fund_mapper.py            # MoneyDJ 代號 ↔ FinMind 代號對照
│   ├── fund_mapping.json         # 對照表快取
│   ├── stock_data.py             # 【第二階段】成分股名單、股價（還原股價優先）
│   ├── financials.py             # 【第二階段】財報：年度 ROE、EPS、毛利率
│   ├── calculators/
│   │   ├── returns.py            # 報酬率
│   │   ├── risk.py               # MDD、波動率
│   │   ├── ratios.py             # Sharpe、Sortino、Calmar
│   │   ├── capm.py               # Alpha、Beta
│   │   ├── scoring.py            # 多準則評分（MCDA）
│   │   ├── mvo.py                # 均值變異數最佳化
│   │   ├── backtest.py           # 回測
│   │   └── stock_selection.py    # 【第二階段】成分股績效、財務篩選、排序、等權重組合
│   ├── data/
│   │   ├── etf_constituents.json # 【第二階段】ETF 成分股名單（需用 git add -f）
│   │   └── index_changes_0050.json # 【第二階段】臺灣50指數歷次審核異動（反推年初名單用）
│   ├── tools/
│   │   ├── import_constituents.py  # 匯入成分股 CSV
│   │   ├── build_start_list.py     # 由期末名單反推研究開始日名單
│   │   └── verify_data.py          # 印出股價、財報數字供人工比對
│   ├── tests/
│   │   └── test_screen.py        # 第二階段測試（不需網路）
│   └── scraper/
│       ├── moneydj.py            # MoneyDJ 爬蟲
│       ├── sitca.py              # RR 評級分類器
│       ├── cache.py              # JSON 快取
│       └── cache/                # 快取檔（price_*、fin_* 不進 git）
└── frontend/
    ├── index.html                # 首頁（ETF 搜尋與列表）
    ├── screen.html               # 【第二階段】ETF 成分股篩選
    ├── fund.html                 # 單一 ETF 分析
    ├── compare.html              # 組合比較
    ├── score.html                # 多準則評分排名
    ├── allocate.html             # 資產配置 + 回測
    ├── css/style.css
    └── js/
        ├── api.js
        └── charts.js
```

---

## 環境建置（只需做一次）

```bash
cd ~/Developer/FundAnalyst
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` 需包含 `yfinance`（第二階段還原股價使用）。

### 建立 MoneyDJ × FinMind 對照表（第一階段功能需要）

MoneyDJ 使用自己的基金代號（ACFP132），FinMind 使用證交所代號（00892）。

```bash
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 fund_mapper.py
```

會產生 `backend/fund_mapping.json`，有新 ETF 上市時再重跑即可。

### 匯入成分股名單（第二階段功能需要）

見下方〈第二階段 → 更新成分股名單〉。

---

## 啟動

### Terminal 1 — 後端

```bash
cd ~/Developer/FundAnalyst
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 app.py
```

看到 `Running on http://127.0.0.1:5000` 代表後端正常。

### Terminal 2 — 前端

```bash
cd ~/Developer/FundAnalyst/frontend
python3 -m http.server 8080
```

> 不要用 VS Code Live Server 開前端：後端抓資料時會一直寫快取檔，Live Server 偵測到檔案變動就會不斷重新整理頁面。

### 瀏覽器

| 網址 | 用途 |
|------|------|
| `http://localhost:8080` | 首頁（ETF 搜尋與列表） |
| `http://localhost:8080/screen.html` | 【第二階段】ETF 成分股篩選 |
| `http://localhost:8080/fund.html?id=0050` | 單一 ETF 分析 |
| `http://localhost:8080/compare.html` | 組合比較 |
| `http://localhost:8080/score.html` | 多準則評分排名 |
| `http://localhost:8080/allocate.html` | 資產配置最佳化 |

---

## 第一階段：ETF 分析平台

### API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/funds` | ETF 列表（q / type / sort / limit） |
| GET | `/funds/<id>` | 單一 ETF 基本資訊（RR 評級、規模） |
| GET | `/funds/<id>/nav?period=3Y` | 歷史價格 |
| GET | `/funds/<id>/metrics?period=3Y` | 風險指標（Sharpe、MDD、Beta 等） |
| POST | `/compare` | 多 ETF 比較 |
| POST | `/score` | 多準則評分排名 |
| GET | `/score/defaults` | 預設權重 |
| POST | `/optimize` | MVO 資產配置 |
| POST | `/backtest` | 回測（MVO vs 等權重） |

### 資料來源

| 資料 | 來源 | 說明 |
|------|------|------|
| ETF 清單、名稱、投信 | MoneyDJ 爬蟲 | 快取 24 小時 |
| ETF 歷史價格 | 還原股價優先（同第二階段，見下方） | 2026/10 起改用，含配息 |
| 基準（0050） | 同上 | — |
| 基金規模（AUM） | FinMind `TaiwanStockMarketValue` | 市值換算億元 |
| RR 風險評級 | 規則式分類器 | 依投信投顧公會分類標準 |

### 關於 RR 評級

MoneyDJ 與基金資訊觀測站的 RR 評級以 JavaScript 動態載入，無法以靜態爬蟲取得。
本系統依投信投顧公會「基金風險報酬等級分類標準」實作規則式分類器，依基金類型、投資標的與槓桿特性判定 RR1–RR5。

### 2026/10 修正（影響第一階段所有頁面的數字）

1. **年化計算錯誤**：舊版把股價補成每日（含週末、假日，一年約 365 筆），但年化公式以一年 252 個交易日計算，導致年化報酬率偏低、波動率偏低約 17%，Sharpe、Sortino、Alpha、MVO 也跟著偏掉。現已改為只用實際交易日。
2. **改用還原股價**：舊版用未還原收盤價，報酬率不含配息，與股票網站的含息報酬有落差（高股息 ETF 差最多）。

修正後的數字與上學期報告中的數字會不同，以修正後為準。

---

## 第二階段：ETF 成分股篩選

### 研究方法（對應參考論文）

1. **母體**：ETF 成分股。採**固定成分股**，使用**研究開始日**的名單，期間內不隨 ETF 換股（論文 3.5.1）。
   - 不使用期末名單：期末名單會包含期間內才被加入的股票（通常是漲多的），報酬會被高估。
2. **財務篩選**（論文 3.3.1，門檻可在頁面調整）：
   - ROE 五年平均 > 10%
   - EPS 連續五年皆為正
   - 毛利率五年平均 > 15%
   - 財報年度預設為開始日期前一年往回 5 年（開始日 2026/1/1 → 2021～2025）
   - 金融股沒有毛利率，目前直接排除（待教授確認）
   - 任一年度缺資料視為未通過（論文要求「連續五年」）
3. **排序選股**：通過篩選的股票依指標排序（預設期間報酬率），取前 1／2／3 名
4. **組合**：前 N 名等權重、買入持有，與 ETF 本身同期間報酬比較

### 指標定義

| 指標 | 計算方式 |
|------|----------|
| 期間報酬率 | 期末價 / 期初價 − 1（還原股價，含配息） |
| 年化報酬率 | (1 + 期間報酬) ^ (252 / 交易日報酬筆數) − 1 |
| 年化波動率 | 日報酬標準差 × √252 |
| 夏普值 | 年化報酬 / 年化波動（無風險利率假設 0，同論文） |
| 最大回檔 | 期間內 (價格 / 前高 − 1) 的最小值 |
| ROE | 年度歸屬母公司淨利 / 平均母公司業主權益（上年底與本年底平均）× 100 |
| EPS | 四季 EPS 加總 |
| 毛利率 | 年度毛利 / 年度營收 × 100；無毛利欄位時以「營收 − 營業成本」計算（例：和泰車） |

> 同一段期間內，期間報酬率與年化報酬率的排序結果相同。期間未滿一年時，年化報酬率僅供參考。

### 資料來源

| 資料 | 來源 | 快取 |
|------|------|------|
| 成分股名單 | 玩股網 / 投信官網，手動匯入 | `data/etf_constituents.json` |
| 指數審核異動 | 臺灣50指數定期審核新聞公告 | `data/index_changes_0050.json` |
| 股價 | 依序嘗試：FinMind 還原股價 → Yahoo 還原股價（yfinance）→ FinMind 收盤價 | 12 小時 |
| 財報 | FinMind `TaiwanStockFinancialStatements`、`TaiwanStockBalanceSheet` | 7 天 |

- FinMind 還原股價需要付費權限，目前實際使用 Yahoo 還原股價。頁面會顯示實際來源。
- Yahoo 偶爾晚一天更新，缺的最後幾天會用 FinMind 收盤價依漲跌比例補上。

### API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/etfs` | 已匯入的 ETF 名單清單 |
| GET | `/etfs/<id>/constituents` | 成分股名單 |
| GET | `/etfs/<id>/screen` | 篩選與排序結果 |

`/etfs/<id>/screen` 參數：

| 參數 | 預設 | 說明 |
|------|------|------|
| `start`、`end` | 今年 1/1、今天 | 研究期間 |
| `sort` | `period_return` | `period_return` / `annualized_return` / `sharpe` / `annualized_std` / `mdd` |
| `top` | 3 | 取前幾名 |
| `filter` | 1 | 0 = 關閉財務篩選 |
| `roe_min`、`gm_min` | 10、15 | 門檻 %；空字串 = 不檢查 |
| `eps_pos` | 1 | 0 = 不檢查 EPS |
| `fin_end` | 開始年 − 1 | 財報最後年度（共取 5 年） |

範例：`http://localhost:5000/etfs/0050/screen?start=2026-01-01&end=2026-10-16&top=3`

### 更新成分股名單

系統內每檔 ETF 有兩份名單：

| 名單 | 用途 |
|------|------|
| `0050` | 研究開始日名單（正式結果用這份） |
| `0050@2026-10-16` | 期末名單，僅供對照（頁面會顯示警告） |

**步驟 1：匯入目前名單**

從玩股網 `https://www.wantgoo.com/stock/etf/0050/constituent` 或投信官網複製持股明細，整理成 UTF-8 CSV：

```
代號,名稱,權重
2330,台積電,56.66
2454,聯發科,5.99
```

```bash
cd backend
python3 tools/import_constituents.py 0050 元大台灣50 ~/Downloads/0050.csv --as-of 2026-10-16
```

**步驟 2：反推研究開始日名單**

```bash
python3 tools/build_start_list.py 0050 2026-01-01
```

會依 `data/index_changes_0050.json` 倒序撤銷開始日之後的每次審核（刪掉當次納入、加回當次刪除）。

目前已記錄 2026 年三次審核：

| 審核 | 生效日（收盤後） | 納入 | 刪除 |
|------|------------------|------|------|
| 3 月 | 2026/3/20 | 金像電、鴻勁、京元電子、欣興、華邦電 | 貿聯-KY、聯詠、統一超、瑞昱、萬海 |
| 6 月 | 2026/6/18 | 南電、創意、貿聯-KY、臻鼎-KY | 康霈、中鋼、台塑、和泰車 |
| 9 月 | 2026/9/18 | 藥華藥 | 世芯-KY |

之後有新的審核（例如 2026/12），把結果加進 `index_changes_0050.json`，重新匯入當時名單後再跑一次步驟 2。論文引用時，建議以臺灣指數公司或證交所正式公告再核對一次。

**新增其他 ETF**：同樣用步驟 1 匯入，名稱換成該 ETF 代號；需要反推的話，另建 `index_changes_<代號>.json`。

### 已知限制與待確認

- **選股與驗證使用同一段期間**（以今年報酬排序、看今年表現），結果必然偏好今年漲最多的股票。系統可改用不同期間（例如以 2025 年選股、看 2026 年），待教授決定。
- **金融股**目前直接排除，待教授確認是否改為只檢查 ROE、EPS。
- **年初名單的權重**無法反推，權重欄留空（等權重計算不受影響）。

---

## 資料驗證

### 第二階段（建議每次交付前執行）

在 `backend/` 底下：

```bash
# 股價：Yahoo 還原 vs FinMind 收盤（兩者差距約等於期間配息）
python3 tools/verify_data.py 2330 2317 0050 --start 2026-01-01 --end 2026-10-16

# 財報：與 Goodinfo / 財報狗的年度 ROE、EPS、毛利率比對
python3 tools/verify_data.py 2330 2317 2881 --fin 2025
```

- EPS、毛利率應與公開年報一致；ROE 因各網站計算方式不同，差 1～2 個百分點屬正常
- 2026/10 已抽查台積電、鴻海、富邦金、和泰車，皆與年報一致

**異常價格檢查**（台股漲跌幅限制 ±10%，還原股價單日變動不應超過）：

```bash
python3 -c "
from stock_data import get_price_series
for sid in ['2454','2303','3711','2308','2330']:
    s,_ = get_price_series(sid,'2026-01-01','2026-10-16')
    r = s.pct_change().dropna()
    print(sid, f'最大漲 {r.max()*100:+.1f}%', f'最大跌 {r.min()*100:+.1f}%', '超過10%:', list(r[r.abs()>0.105].index.date))
"
```

### 第一階段

**價格**

```bash
python3 -c "
from data_source import get_nav_series
nav = get_nav_series('0050', '1Y')
print('最新日期:', nav.index[-1].date())
print('最新價格:', nav.iloc[-1])
print('交易日數:', len(nav))
"
```

一年應約 240～250 個交易日（只含交易日）。價格為還原股價，會略低於當時的實際收盤價。

**指標**

```bash
python3 -c "
from data_source import get_nav_series
from calculators.returns import daily_returns, annualized_return
from calculators.risk import max_drawdown, annualized_std
from calculators.ratios import sharpe_ratio

nav = get_nav_series('0050', '3Y')
ann = annualized_return(nav); std = annualized_std(daily_returns(nav))
print(f'年化報酬：{ann*100:.2f}%')
print(f'年化波動：{std*100:.2f}%')
print(f'最大回檔：{max_drawdown(nav)*100:.2f}%')
print(f'Sharpe  ：{sharpe_ratio(ann, 0.015, std):.2f}')
"
```

與 MoneyDJ「績效評比」或 GoodInfo 的含息報酬比對，誤差 1～2% 內屬正常（計算基準日不同）。

**RR 評級**

```bash
python3 -c "
from scraper.sitca import classify_rr, rr_label
for fid, name in [('0050','元大台灣50'),('00679B','元大美債20年'),('00892','富邦台灣核心半導體ETF基金'),('00878','國泰永續高股息')]:
    print(f'{fid:<8} -> {rr_label(classify_rr(fid, name))}')
"
```

| ETF | 預期 RR |
|-----|---------|
| 0050 | RR4（中高） |
| 00679B | RR2（低） |
| 00892 | RR5（高） |
| 00878 | RR4（中高） |

---

## 測試

```bash
cd backend
python3 -m pytest tests -q
```

不需網路（股價與財報用假資料）。涵蓋：績效計算、排序、財務篩選（含論文案例：華碩毛利率 14.43% 應被排除）、財報年度化、年初名單反推、還原股價來源切換、第一階段年化修正。

---

## 快取管理

```bash
cd backend

# 清除全部快取（含 MoneyDJ 清單、股價、財報）
python3 -c "from scraper.cache import clear_all; clear_all()"

# 只清股價與財報快取
rm -f scraper/cache/price_*.json scraper/cache/fin_*.json

# 重建 MoneyDJ 基金清單
python3 -c "from scraper.moneydj import scrape_fund_list; scrape_fund_list(use_cache=False)"
```

### FinMind 請求量

- 免費方案有請求次數上限，以 FinMind 官網公告為準
- 成分股篩選第一次執行（50 檔）約需 150 次請求（股價 + 兩份財報），之後走快取
- 第一階段評分排名每檔 ETF 約 1 次請求

---

## 常見問題

**`ModuleNotFoundError: No module named 'flask'`**
→ 虛擬環境沒啟動：`source venv/bin/activate`

**`ModuleNotFoundError: No module named 'data_source'` 或其他舊檔案不見**
→ 解壓更新檔時用了 Finder「取代」，整個資料夾被換掉。救回被刪的檔案：
```bash
git ls-files -d | xargs git checkout --
```
之後一律用 `unzip -o 檔案.zip` 解壓。

**`400 Bad Request` 打 FinMind API**
→ Token 有空白或換行，重新 `export FINMIND_TOKEN="token"`

**成分股篩選頁一直重新整理**
→ 用了 VS Code Live Server。改用 `python3 -m http.server 8080`

**頁面顯示「未還原收盤價」**
→ 沒安裝 yfinance：`pip install yfinance`

**成分股篩選第一次很慢（1～2 分鐘）**
→ 正常，需逐檔抓股價與財報；之後走快取

**前端空白或 API 失敗**
→ 確認後端有跑（Terminal 1 顯示 Running on 5000），前端用 `http://localhost:8080` 開

**MoneyDJ 爬蟲回傳空清單**
→ 清快取後重試：`python3 -c "from scraper.cache import clear_all; clear_all()"`

---

## 開發紀錄

### 第一階段（2026 上學期）
- ETF 搜尋、單檔分析、組合比較、多準則評分、MVO 資產配置與回測

### 第二階段（2026 下學期）

**第 1 週（10/13 報告）**
- 新增成分股篩選頁：0050 成分股報酬排序、取前 N 名等權重組合、與 0050 比較

**第 2 週（10/20 報告）**
- 財務指標篩選（ROE、EPS、毛利率，2021～2025 財報），金融股先排除
- 股價改用還原股價（Yahoo），並處理 Yahoo 缺日
- 匯入 0050 完整 50 檔；改用 2026 年初名單（由 10/16 名單反推三次審核）
- 修正第一階段年化計算錯誤，舊頁面同步改用還原股價
- 無毛利欄位公司改以營收減營業成本計算毛利率
- 新增驗證工具與測試（31 項）

**待辦**
- 等教授確認：選股期間、金融股處理、第二檔 ETF
- 第二檔 ETF 成分股匯入與比較