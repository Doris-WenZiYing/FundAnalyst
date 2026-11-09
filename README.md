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

以下指令分 macOS 與 Windows 兩種。Windows 一律使用 **PowerShell**（開始選單搜尋「PowerShell」或「終端機」），專案路徑請換成實際放的位置。

| 動作 | macOS（Terminal） | Windows（PowerShell） |
|------|-------------------|------------------------|
| Python 指令 | `python3` | `python` |
| 啟動虛擬環境 | `source venv/bin/activate` | `.\venv\Scripts\Activate.ps1` |
| 設定 FinMind token | `export FINMIND_TOKEN="token"` | `$env:FINMIND_TOKEN="token"` |
| 下載資料夾 | `~/Downloads` | `$HOME\Downloads` |

**macOS**

```bash
cd ~/Developer/FundAnalyst
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Windows（PowerShell）**

先安裝 Python 3.9 以上（[python.org](https://www.python.org/downloads/)），安裝時勾選 **Add Python to PATH**。

```powershell
cd C:\Users\你的名字\FundAnalyst
python -m venv venv

# 第一次啟動虛擬環境若出現「已停用指令碼執行」，先執行這行（只需一次）
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`requirements.txt` 需包含 `yfinance`（第二階段還原股價使用）。

> Windows 終端機顯示中文若出現亂碼或 `UnicodeEncodeError`，在執行 Python 前先下 `$env:PYTHONUTF8="1"`。

### 建立 MoneyDJ × FinMind 對照表（第一階段功能需要）

MoneyDJ 使用自己的基金代號（ACFP132），FinMind 使用證交所代號（00892）。

```bash
# macOS
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 fund_mapper.py
```

```powershell
# Windows（PowerShell）
.\venv\Scripts\Activate.ps1
$env:FINMIND_TOKEN="貼上你的token"
cd backend
python fund_mapper.py
```

會產生 `backend/fund_mapping.json`，有新 ETF 上市時再重跑即可。

### 匯入成分股名單（第二階段功能需要）

見下方〈第二階段 → 更新成分股名單〉。

---

## 啟動

### 視窗 1 — 後端

```bash
# macOS
cd ~/Developer/FundAnalyst
source venv/bin/activate
export FINMIND_TOKEN="貼上你的token"
cd backend
python3 app.py
```

```powershell
# Windows（PowerShell）
cd C:\Users\你的名字\FundAnalyst
.\venv\Scripts\Activate.ps1
$env:FINMIND_TOKEN="貼上你的token"
$env:PYTHONUTF8="1"
cd backend
python app.py
```

token 只在目前這個視窗有效，關掉視窗後重開要再設定一次。

看到 `Running on http://127.0.0.1:5000` 代表後端正常。

### 視窗 2 — 前端

另開一個終端機視窗：

```bash
# macOS
cd ~/Developer/FundAnalyst/frontend
python3 -m http.server 8080
```

```powershell
# Windows（PowerShell）
cd C:\Users\你的名字\FundAnalyst\frontend
python -m http.server 8080
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
2. **財務篩選**：13 個指標（論文表 1 的盈餘能力、價值評估、財務穩健三類，加上成長性），每個都可以**留白不使用**
   - 「論文預設」按鈕 = 論文 3.3.1 的三個條件：ROE 五年平均 > 10%、EPS 連續五年皆為正、毛利率五年平均 > 15%，其餘留白
   - 財報年度預設為開始日期前一年往回 5 年（開始日 2026/1/1 → 2021～2025）
   - 價值評估指標（本益比、股價淨值比、殖利率）取**研究開始日前最後一個交易日**的數值，避免用到未來資料
   - **金融股自動忽略不適用的指標**（毛利率、營業利益率、負債比率、流動比率），其他條件照常檢查（教授 10/21 指示）
   - 任一年度缺資料視為未通過（論文要求「連續五年」）；EPS 成長率例外，前一年 EPS ≤ 0 的年度無法計算、不列入
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

**財務篩選指標**（門檻方向：＞ 為下限、＜ 為上限；五年平均類取 5 個年度數值的平均）

| 類別 | 指標 | 條件 | 計算方式 | 金融股 |
|------|------|------|----------|--------|
| 盈餘能力 | ROE | ＞ | 年度歸屬母公司淨利 / 平均母公司業主權益（上年底與本年底平均）× 100 | 檢查 |
| 盈餘能力 | ROA | ＞ | 年度稅後淨利 / 平均總資產 × 100 | 檢查 |
| 盈餘能力 | EPS 每年為正 | — | 四季 EPS 加總，五年每年都 > 0 | 檢查 |
| 盈餘能力 | 毛利率 | ＞ | 年度毛利 / 年度營收 × 100；無毛利欄位時以「營收 − 營業成本」計算（例：和泰車） | 忽略 |
| 盈餘能力 | 營業利益率 | ＞ | 年度營業利益 / 年度營收 × 100 | 忽略 |
| 盈餘能力 | 稅後淨利率 | ＞ | 年度稅後淨利 / 年度營收 × 100 | 檢查 |
| 財務穩健 | 負債比率 | ＜ | 年底總負債 / 年底總資產 × 100 | 忽略 |
| 財務穩健 | 流動比率 | ＞ | 年底流動資產 / 年底流動負債 × 100 | 忽略 |
| 成長性 | 營收成長率 | ＞ | 年度營收相對前一年增減 % | 檢查 |
| 成長性 | EPS 成長率 | ＞ | 年度 EPS 相對前一年增減 %（前一年 EPS ≤ 0 不列入） | 檢查 |
| 價值評估 | 本益比 | ＜ | FinMind `TaiwanStockPER`，開始日前一交易日；虧損時無本益比，視為未通過 | 檢查 |
| 價值評估 | 股價淨值比 | ＜ | 同上 | 檢查 |
| 價值評估 | 現金殖利率 | ＞ | 同上 | 檢查 |

金融股（銀行、保險、證券）的負債比率本來就在 90% 左右，也沒有毛利、營業利益、流動資產負債的分類，所以這四項自動忽略。

> 同一段期間內，期間報酬率與年化報酬率的排序結果相同。期間未滿一年時，年化報酬率僅供參考。

### 資料來源

| 資料 | 來源 | 快取 |
|------|------|------|
| 成分股名單 | 玩股網 / 投信官網，手動匯入 | `data/etf_constituents.json` |
| 指數審核異動 | 臺灣50指數定期審核新聞公告 | `data/index_changes_0050.json` |
| 股價 | 依序嘗試：FinMind 還原股價 → Yahoo 還原股價（yfinance）→ FinMind 收盤價 | 12 小時 |
| 財報 | FinMind `TaiwanStockFinancialStatements`、`TaiwanStockBalanceSheet` | 7 天 |
| 本益比、股價淨值比、殖利率 | FinMind `TaiwanStockPER`（只有用到價值評估指標時才抓） | 7 天 |

- FinMind 還原股價需要付費權限，目前實際使用 Yahoo 還原股價。頁面會顯示實際來源。
- Yahoo 偶爾晚一天更新，缺的最後幾天會用 FinMind 收盤價依漲跌比例補上。

### API

| Method | Path | 說明 |
|--------|------|------|
| GET | `/etfs` | 已匯入的 ETF 名單清單 |
| GET | `/etfs/<id>/constituents` | 成分股名單 |
| GET | `/etfs/<id>/screen` | 篩選與排序結果 |
| GET | `/screen/indicators` | 可用的篩選指標與論文預設門檻 |

`/etfs/<id>/screen` 參數：

| 參數 | 預設 | 說明 |
|------|------|------|
| `start`、`end` | 今年 1/1、今天 | 研究期間 |
| `sort` | `period_return` | `period_return` / `annualized_return` / `sharpe` / `annualized_std` / `mdd` |
| `top` | 3 | 取前幾名 |
| `filter` | 1 | 0 = 關閉財務篩選 |
| `roe_min`、`gm_min` | 10、15 | ROE、毛利率下限 %；空字串 = 不使用 |
| `eps_pos` | 1 | 0 = 不檢查 EPS 每年為正 |
| `roa_min`、`opm_min`、`npm_min` | 不使用 | ROA、營業利益率、稅後淨利率下限 % |
| `debt_max`、`cr_min` | 不使用 | 負債比率上限 %、流動比率下限 % |
| `revg_min`、`epsg_min` | 不使用 | 營收成長率、EPS 成長率下限 % |
| `per_max`、`pbr_max`、`dy_min` | 不使用 | 本益比上限、股價淨值比上限（倍）、殖利率下限 % |
| `fin_end` | 開始年 − 1 | 財報最後年度（共取 5 年） |

範例：`http://localhost:5000/etfs/0050/screen?start=2026-01-01&end=2026-10-16&top=3`

### 更新成分股名單

> **git 裡已經包含 0050 的完整名單（年初 50 檔 + 2026/10/16 期末 50 檔），直接啟動就能用，不需要再匯入。** 以下步驟只有在要更新名單或新增其他 ETF 時才需要。

系統內每檔 ETF 有兩份名單：

| 名單 | 用途 |
|------|------|
| `0050` | 研究開始日名單（正式結果用這份） |
| `0050@2026-10-16` | 期末名單，僅供對照（頁面會顯示警告） |

**步驟 1：匯入目前名單**

從玩股網 `https://www.wantgoo.com/stock/etf/0050/constituent` 或投信官網複製持股明細（玩股網沒有下載按鈕，直接選取表格複製），貼到 Excel，只留三欄，第一列是標題：

```
代號,名稱,權重
2330,台積電,56.66
2454,聯發科,5.99
```

存成 **UTF-8 的 CSV**，不然中文會變亂碼：

- **Windows Excel**：檔案 → 另存新檔 → 存檔類型選「**CSV UTF-8（逗號分隔）(*.csv)**」。不要選一般的「CSV（逗號分隔）」，那是 Big5 編碼
- **macOS Excel**：另存新檔 → 格式選「CSV UTF-8（逗號分隔）」
- **macOS Numbers**：檔案 → 輸出至 → CSV → 文字編碼選 Unicode (UTF-8)

存到「下載」資料夾，檔名 `0050.csv`，然後匯入：

```bash
# macOS
cd backend
python3 tools/import_constituents.py 0050 元大台灣50 ~/Downloads/0050.csv --as-of 2026-10-16
```

```powershell
# Windows（PowerShell）
cd backend
python tools\import_constituents.py 0050 元大台灣50 "$HOME\Downloads\0050.csv" --as-of 2026-10-16
```

成功會顯示 `已匯入 0050@2026-10-16 元大台灣50：50 檔`。名單會存成「代號@日期」，不會蓋掉研究用的年初名單。若只讀到幾檔，代表 CSV 不完整（例如只放了上面的範例兩筆）。

**步驟 2：反推研究開始日名單**

```bash
# macOS
python3 tools/build_start_list.py 0050 2026-01-01
```

```powershell
# Windows（PowerShell）
python tools\build_start_list.py 0050 2026-01-01
```

會依 `data/index_changes_0050.json` 倒序撤銷開始日之後的每次審核（刪掉當次納入、加回當次刪除）。

目前已記錄 2026 年三次審核：

| 審核 | 生效日（收盤後） | 納入 | 刪除 |
|------|------------------|------|------|
| 3 月 | 2026/3/20 | 金像電、鴻勁、京元電子、欣興、華邦電 | 貿聯-KY、聯詠、統一超、瑞昱、萬海 |
| 6 月 | 2026/6/18 | 南電、創意、貿聯-KY、臻鼎-KY | 康霈、中鋼、台塑、和泰車 |
| 9 月 | 2026/9/18 | 藥華藥 | 世芯-KY |

之後有新的審核（例如 2026/12），把結果加進 `index_changes_0050.json`，重新匯入當時名單後再跑一次步驟 2。論文引用時，建議以臺灣指數公司或證交所正式公告再核對一次。

**暫不使用某檔股票**：資料有問題的股票不必從名單刪除，在 `etf_constituents.json` 該 ETF 底下加 `excluded_stocks`，頁面會跳過它並顯示原因。重新反推名單時會保留這個設定。

```json
"excluded_stocks": {
  "2207": "財報資料不完整（FinMind 缺營業利益欄位，流動比率約 9 倍與實際不符）"
}
```

目前暫不使用：**和泰車（2207）**。

**新增其他 ETF**：同樣用步驟 1 匯入，名稱換成該 ETF 代號；需要反推的話，另建 `index_changes_<代號>.json`。

### 已知限制與待確認

- **選股與驗證使用同一段期間**（以今年報酬排序、看今年表現），結果必然偏好今年漲最多的股票。系統可改用不同期間（例如以 2025 年選股、看 2026 年），待教授決定。
- **年初名單的權重**無法反推，權重欄留空（等權重計算不受影響）。

---

## 實戰選股（第 4 週）

依業主 11/9 確認的四階段規則，從 0050 成分股選出三檔，兩週後觀察報酬率。程式：`backend/tools/pick_stocks.py`（獨立執行，不影響網站）。

### 執行

macOS：
```bash
cd backend
python3 tools/pick_stocks.py                      # 選股（選股日預設 2026-11-09）
python3 tools/pick_stocks.py --fill-close         # 收盤（13:30）後補上選股日收盤價
```

Windows PowerShell：
```powershell
cd backend
python tools\pick_stocks.py
python tools\pick_stocks.py --fill-close
```

其他參數：`--date 2026-11-09`（選股日）、`--etf 0050@2026-10-16`（母體名單）。

第一次執行約 5 分鐘（50 檔 × 財報、季報、股價、估值），之後 12 小時內有快取。

### 輸出（`backend/picks/`）

| 檔案 | 內容 |
|---|---|
| `picks_<日期>.json` | 入選三檔：總分、四構面分數、穩健價值分數、入選理由、參考收盤價、選股日收盤價、MOPS 連結 |
| `scores_<日期>.csv` | 全部成分股：各指標數值與同產業百分位、構面分數、排除原因、風險提醒（Excel 可直接開） |

### 規則

**第一階段：初步排除**
- 完整性：最近 3 個完整會計年度＋最近連續 8 季財報；必要欄位缺漏 → 排除。產業不適用的指標（金融股的毛利率、營業利益率、負債比率、流動比率）標 N/A，不算缺漏
- 長期虧損：最近 3 年「歸屬於母公司業主之稅後淨利」至少 2 年 < 0 → 排除
- 流動性：近 20 個交易日平均成交金額 < 3,000 萬元 → 排除

**第二階段：基本面評分**（各指標換算成同產業百分位 0–100，產業只有 1、2 檔就直接跟那 1、2 檔比）

| 構面 | 指標與權重 | 小計 |
|---|---|---|
| 獲利能力 | ROE 8%、ROA 5%、EPS 5%、毛利率 4%、營業利益率 4%、稅後淨利率 4% | 30% |
| 成長能力 | 營收成長率 15%、EPS 成長率 15% | 30% |
| 財務穩健 | 負債比率 10%（越低越好）、流動比率 10% | 20% |
| 價值評估 | 本益比 8%（越低越好）、股價淨值比 7%（越低越好）、殖利率 5% | 20% |

- 財報指標取 3 年平均；估值指標取選股日前一交易日
- N/A 的指標不計，權重按比例分給同構面其他指標
- 穩健價值分數 = 財務穩健 × 50% + 價值評估 × 50%（列出供參考）

**第三階段：風險與流動性**
- 近 60 個交易日年化波動率：母體 75–90 百分位 → 風險提醒；90–100 百分位 → 排除
- 重大訊息：人工檢查。點 `mops_news` 連結，看選股日前 30 個日曆日的重大訊息，以及過去發生但尚未解決的重大風險事件；有問題就改用下一名

**第四階段**：依總分排序取前三名，記錄選股理由、選股日期、當日收盤價

### 注意
- 選股日當天盤中執行時還沒有當日收盤價，選股用前一交易日資料，收盤後用 `--fill-close` 補上
- 2026Q3 財報 11/14 才公告，11/9 選股不會用到

## 資料驗證

### 第二階段（建議每次交付前執行）

在 `backend/` 底下：

```bash
# 股價：Yahoo 還原 vs FinMind 收盤（兩者差距約等於期間配息）
python3 tools/verify_data.py 2330 2317 0050 --start 2026-01-01 --end 2026-10-16

# 財報：與 Goodinfo / 財報狗的年度 ROE、EPS、毛利率比對
python3 tools/verify_data.py 2330 2317 2881 --fin 2025
```

Windows 把 `python3` 換成 `python`、`tools/` 換成 `tools\`，其餘相同。本節其他 `python3 -c "..."` 指令在 PowerShell 也可直接貼上執行（`python3` 改成 `python`）。

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
python3 -m pytest tests -q      # Windows：python -m pytest tests -q
```

不需網路（股價與財報用假資料）。涵蓋：績效計算、排序、財務篩選（含論文案例：華碩毛利率 14.43% 應被排除）、財報年度化、年初名單反推、還原股價來源切換、第一階段年化修正。

---

## 快取管理

```bash
cd backend

# 清除全部快取（含 MoneyDJ 清單、股價、財報）
python3 -c "from scraper.cache import clear_all; clear_all()"

# 只清股價與財報快取
rm -f scraper/cache/price_*.json scraper/cache/fin_*.json scraper/cache/val_*.json

# 重建 MoneyDJ 基金清單
python3 -c "from scraper.moneydj import scrape_fund_list; scrape_fund_list(use_cache=False)"
```

Windows（PowerShell）只清股價與財報快取：

```powershell
Remove-Item scraper\cache\price_*.json, scraper\cache\fin_*.json, scraper\cache\val_*.json
```

其他兩行把 `python3` 換成 `python` 即可。

### FinMind 請求量

- 免費方案有請求次數上限，以 FinMind 官網公告為準
- 成分股篩選第一次執行（50 檔）約需 150 次請求（股價 + 兩份財報）；有用到價值評估指標時再多 50 次。之後走快取
- 第一階段評分排名每檔 ETF 約 1 次請求

---

## 常見問題

**`ModuleNotFoundError: No module named 'flask'`**
→ 虛擬環境沒啟動：macOS `source venv/bin/activate`，Windows `.\venv\Scripts\Activate.ps1`

**Windows：`Activate.ps1 無法載入，因為這個系統上已停用指令碼執行`**
→ 執行一次 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`，再重新啟動虛擬環境

**Windows：`'python3' 不是內部或外部命令`**
→ Windows 請用 `python`，不是 `python3`

**Windows：中文亂碼或 `UnicodeEncodeError`**
→ 先執行 `$env:PYTHONUTF8="1"` 再跑 Python

**匯入成分股後名稱變亂碼，或顯示「CSV 裡沒有讀到任何股票代號」**
→ CSV 不是 UTF-8。Excel 另存時要選「CSV UTF-8（逗號分隔）」

**`ModuleNotFoundError: No module named 'data_source'` 或其他舊檔案不見**
→ 解壓更新檔時用了 Finder「取代」，整個資料夾被換掉。救回被刪的檔案：
```bash
git ls-files -d | xargs git checkout --
```
之後一律用 `unzip -o 檔案.zip` 解壓。

**`400 Bad Request` 打 FinMind API**
→ Token 有空白或換行，或這個視窗沒設定 token。重新設定：macOS `export FINMIND_TOKEN="token"`，Windows `$env:FINMIND_TOKEN="token"`

**成分股篩選頁一直重新整理**
→ 用了 VS Code Live Server。改用 `python3 -m http.server 8080`

**頁面顯示「未還原收盤價」**
→ 沒安裝 yfinance：`pip install yfinance`

**成分股篩選第一次很慢（1～2 分鐘）**
→ 正常，需逐檔抓股價與財報；之後走快取

**網頁顯示「無法連線後端：getEtfs is not defined」**
→ 瀏覽器用到快取的舊版 js。按 **Ctrl + F5**（macOS：Cmd + Shift + R）強制重新整理；也確認前端視窗是在**新版**專案的 `frontend` 資料夾啟動，舊版的伺服器視窗要先關掉

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

**第 3 週（10/27 報告）**
- 財務篩選擴充為 13 個指標（盈餘能力、財務穩健、成長性、價值評估），每個都可以留白不使用
- 「論文預設」「全部清空」按鈕；表格只顯示有使用的指標欄位
- 金融股改為自動忽略不適用的指標（毛利率、營業利益率、負債比率、流動比率），不再整檔排除
- 價值評估指標取研究開始日前一交易日，避免用到未來資料
- 和泰車（2207）財報資料不完整，暫不納入分析（`excluded_stocks`）

**第 4 週（11/10 報告）**
- 實戰選股程式 `tools/pick_stocks.py`：四階段（初步排除、同產業百分位評分、波動率風險過濾、總分排序）選出三檔，輸出選股理由與收盤價

**待辦**
- 兩週後追蹤三檔與 0050 的報酬率
- 等教授確認：選股期間、第二檔 ETF
- 第二檔 ETF 成分股匯入與比較
