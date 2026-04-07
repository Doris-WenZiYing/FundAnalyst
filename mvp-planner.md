# MVP Planner — 基金分析平台（FinMind API 版）

---

## ★ 從零開始執行（Week 0）

> 在開始任何開發之前，先把環境和 FinMind 帳號確認好。

### Step 1：申請 FinMind 帳號與 Token

1. 前往 [FinMind 官網](https://finmindtrade.com) 註冊帳號（免費）
2. 登入後到「個人設定」取得 API Token
3. 免費方案限制：每天 600 次請求，每次最多回傳 1000 筆資料
4. 測試 Token 是否正常：

```bash
curl "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanMutualFundInfo&token=你的TOKEN"
# 應該回傳 JSON，status=200
```

### Step 2：建立專案目錄

```bash
mkdir fund-analysis
cd fund-analysis
mkdir -p backend/calculators backend/data frontend/css frontend/js
```

### Step 3：Python 環境

```bash
# 建議用虛擬環境
python -m venv venv

# 啟動（Mac/Linux）
source venv/bin/activate

# 啟動（Windows）
venv\Scripts\activate

# 安裝依賴
pip install flask flask-cors numpy pandas requests
```

### Step 4：設定環境變數（Token 不寫進程式碼）

```bash
# Mac/Linux（每次開 terminal 要重設，或加到 ~/.zshrc）
export FINMIND_TOKEN="你的Token"

# Windows PowerShell
$env:FINMIND_TOKEN = "你的Token"

# 確認有設定成功
echo $FINMIND_TOKEN
```

### Step 5：確認後端能跑起來

把 `backend/app.py` 放好之後：

```bash
cd backend
python app.py
# 看到 Running on http://127.0.0.1:5000 就成功了
```

### Step 6：測試第一支 API

開瀏覽器或 Postman，打：
```
GET http://localhost:5000/funds
```

有回傳 JSON 就代表後端 + FinMind 串接成功。

---

## 總覽

| 週次 | 主題 | 里程碑 |
|------|------|--------|
| Week 1 | FinMind 串接 & 後端基礎 | `/funds` 和 `/funds/<id>/nav` 回傳真實資料 |
| Week 2 | 指標計算 | 5 個核心指標全部算出來並驗證 |
| Week 3 | 前端基礎 UI | 首頁 + 基金列表頁完成 |
| Week 4 | 單一基金頁 | 指標卡 + NAV 圖表完成 |
| Week 5 | 比較功能 | 多基金對比表 + 走勢疊圖 |
| Week 6 | 雷達圖 & 串接 | 前後端完整串接、雷達圖完成 |
| Week 7 | 收尾 & Demo | 測試、修 bug、準備 Demo |

> 因為資料來源已確認（FinMind API），Week 1 不用浪費時間討論 Q&A，
> 原本 8 週可以壓縮成 7 週。

---

## 詳細週計畫

### Week 1 — FinMind 串接 & 後端基礎
> 目標：後端能從 FinMind 拿到真實基金資料並回傳

**FinMind API 探索**
- [ ] 完成「從零開始執行」的 Step 1–6
- [ ] 印出 `TaiwanMutualFundInfo` 回傳的欄位名稱，對齊 `data_source.py` 的 rename 邏輯
- [ ] 找一檔基金（e.g. 台灣50 相關基金）的 fund_id，測試 `TaiwanMutualFund` 能拿到 NAV
- [ ] 確認 `TaiwanStockPrice` 能拿到 0050 歷史價格（當基準指數用）
- [ ] 確認免費方案能不能拿到 5 年資料（1250 筆），若超過 1000 筆限制需規劃分頁

**後端基礎**
- [ ] 把 `data_source.py` 欄位名稱對齊（實際測試後修正 rename 的 mapping）
- [ ] 完成 `GET /funds`：回傳基金清單（含 q / type 篩選）
- [ ] 完成 `GET /funds/<id>`：回傳單一基金資訊
- [ ] 完成 `GET /funds/<id>/nav`：回傳 NAV 歷史（period=3Y）
- [ ] 用 Postman 或瀏覽器測試三支 API 回傳格式正確

**週末檢查點：** 打 `/funds` 有真實基金列表嗎？打 `/funds/<id>/nav` 有 NAV 歷史資料嗎？

---

### Week 2 — 指標計算
> 目標：5 個核心指標全部實作並驗證正確

- [ ] `returns.py`：`daily_returns` / `annualized_return` / `normalize_to_100`
- [ ] `risk.py`：`annualized_std` / `downside_std` / `max_drawdown`
- [ ] `ratios.py`：`sharpe_ratio` / `sortino_ratio` / `calmar_ratio`
- [ ] `capm.py`：`align_series` / `beta` / `alpha`
- [ ] 完成 `GET /funds/<id>/metrics`：回傳所有指標
- [ ] 手動驗算：找 MoneyDJ 或基金公司網站的指標數字，跟計算結果比對
- [ ] 邊界測試：NAV 資料不足 30 天時，Beta 回傳 None 而不是 crash

**可能遇到的問題：**
- FinMind NAV 資料可能有缺漏日（假日），`daily_returns` 的 `pct_change()` 會跳過，這是正常的
- 0050 和基金的交易日不完全對齊（0050 是股票，每天有資料；基金 NAV 可能只有交易日），`align_series` 會用 inner join 處理

**週末檢查點：** 打 `/funds/<id>/metrics?period=3Y`，Sharpe / MDD / Beta 數字合理嗎？

---

### Week 3 — 前端基礎 UI
> 目標：首頁和基金列表頁的靜態 UI 完成並接上後端

- [ ] 建立共用 `style.css`（色彩 CSS 變數、Card、Button、Table 樣式）
- [ ] 完成 `index.html` 首頁版面（Hero 搜尋列 + 排行區 + 列表區）
- [ ] 完成 `api.js` 的 `getFunds()` / `apiFetch()` 基礎函數
- [ ] 用 JS fetch 打 `GET /funds`，將基金列表渲染到頁面上
- [ ] 搜尋框：輸入文字時打 `GET /funds?q=xxx`，動態更新列表
- [ ] 排行榜區塊：打 `GET /funds?sort=sharpe&limit=5`（注意：Sharpe 排行需要後端先算好，或這週先用假資料）

**週末檢查點：** 打開 `index.html`，基金列表有從後端拿到並顯示嗎？搜尋功能有用嗎？

---

### Week 4 — 單一基金分析頁
> 目標：點進基金後，能看到指標卡和走勢圖

- [ ] 完成 `fund.html` 頁面版面
- [ ] 用 URL 參數取得 fund_id（`?id=TC101`），打 `GET /funds/<id>` 填入基本資訊
- [ ] 完成 `charts.js` 的 `drawNavChart()`，繪製 NAV 折線圖
- [ ] 打 `GET /funds/<id>/nav?period=3Y` 取得資料，渲染圖表
- [ ] 完成 `api.js` 的 `rateMetric()`，判斷 Sharpe / Sortino / MDD / Beta / Alpha 評級
- [ ] 打 `GET /funds/<id>/metrics?period=3Y`，渲染 6 個指標卡（含評級顏色）
- [ ] 期間切換按鈕（1Y / 3Y / 5Y）：切換後重新 fetch 並 redraw
- [ ] 基本 RWD（桌機版排版正確）

**週末檢查點：** 單一基金頁所有資料都能正確顯示嗎？圖表有出來嗎？切換期間有效嗎？

---

### Week 5 — 投資組合比較功能
> 目標：可以選多檔基金，看對比表和走勢疊圖

- [ ] 完成 `compare.html` 頁面版面
- [ ] 在 `fund.html` 實作「加入比較」按鈕（寫入 localStorage）
- [ ] 比較頁讀取 localStorage，渲染比較清單 chips（含移除按鈕）
- [ ] 實作「＋新增基金」Modal（搜尋框打 `GET /funds?q=xxx`，點擊加入）
- [ ] 打 `POST /compare`，回傳多基金的指標和 NAV 序列
- [ ] 繪製指標對比表格（最高值標綠，最低值標紅）
- [ ] 完成 `charts.js` 的 `drawOverlayChart()`，繪製走勢疊圖

**週末檢查點：** 可以選 3 檔基金，並排看到指標差異嗎？疊圖有多條線嗎？

---

### Week 6 — 雷達圖 & 前後端完整串接
> 目標：雷達圖完成，整個流程跑順

- [ ] 完成 `charts.js` 的 `drawRadarChart()`（含各軸正規化到 0–1）
- [ ] 確認所有頁面的前後端串接正確（沒有寫死假資料）
- [ ] 錯誤處理：API 掛掉或資料缺失時，頁面顯示合理的提示而不是空白
- [ ] 處理 FinMind 免費方案限流：若 API 回 429，前端顯示「請稍後再試」
- [ ] 統一 UI 細節（間距、顏色、字型大小）

**週末檢查點：** 從頭到尾點一遍，流程通嗎？有沒有 console error？

---

### Week 7 — 測試、修 Bug & Demo 準備
> 目標：穩定可 Demo 的版本

- [ ] 完整功能測試（列表 → 基金頁 → 加入比較 → 比較頁）
- [ ] 修掉發現的 bug
- [ ] 確認本地端部署步驟文件（README：Token 設定 + 啟動後端 + 開前端）
- [ ] 準備 Demo 腳本（走哪幾個流程、講哪幾個亮點）
- [ ] 錄製備用 Demo 影片（以防現場網路或 FinMind API 不穩）
- [ ] 確認指標說明文字是否通順（非技術人員也看得懂）

**週末檢查點：** 可以當場 Demo 不卡關嗎？README 是否能讓別人在自己電腦跑起來？

---

## Buffer & 風險

| 風險 | 對策 |
|------|------|
| FinMind 免費方案超出每日 600 次限制 | `get_fund_list()` 加 `@lru_cache`；開發時用固定幾檔基金測試，不要亂打 API |
| FinMind 5 年資料超過 1000 筆限制 | Week 1 先確認，若需要分頁則在 `data_source.py` 加分頁邏輯 |
| FinMind API 回傳欄位名稱跟文件不符 | Week 1 第一件事就是印出 `df.columns` 確認，再修 rename mapping |
| Demo 當天 FinMind API 不穩 | Week 7 錄好備用影片；或在 `data_source.py` 加本地 CSV fallback |
| 指標計算數字對不起來 | Week 2 留時間跟 MoneyDJ 交叉驗證 |
| 某週進度落後 | 優先保 Phase 1（基金頁 + 指標卡），雷達圖可砍 |

---

*v2：資料來源確認為 FinMind API，新增「從零開始執行」區塊，週計畫對應調整*