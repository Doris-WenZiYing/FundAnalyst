# FundLens — 基金分析平台

## 目錄結構

```
FundAnalyst/
├── venv/                        # Python 虛擬環境（不進 git）
├── backend/
│   ├── app_finmind.py           # Flask 主程式（用這支）
│   ├── data_source.py           # FinMind API 呼叫層
│   ├── calculators/
│   │   ├── returns.py
│   │   ├── risk.py
│   │   ├── ratios.py
│   │   └── capm.py
│   └── requirements.txt
└── frontend/
    ├── index.html               # 首頁
    ├── fund.html                # 單一基金分析頁
    ├── compare.html             # 投資組合比較頁
    ├── css/style.css
    └── js/
        ├── api.js
        └── charts.js
```

---

## 每次開發前：啟動流程

每次打開新的 terminal，都要做這三步：

### Terminal 1 — 後端

```bash
# Step 1：進專案根目錄
cd /Users/doris/Developer/FundAnalyst

# Step 2：啟動虛擬環境（提示符前出現 (venv) 才算成功）
source venv/bin/activate

# Step 3：設定 FinMind Token
export FINMIND_TOKEN="貼上你的token"

# Step 4：進 backend 啟動 Flask
cd backend
python3 app.py
```

看到以下訊息代表後端正常：
```
* Running on http://127.0.0.1:5000
```

---

### Terminal 2 — 前端

```bash
# 開新的 terminal（後端那個不要關）

# Step 1：進前端目錄
cd /Users/doris/Developer/FundAnalyst/frontend

# Step 2：啟動靜態伺服器
python3 -m http.server 8080
```

看到以下訊息代表前端正常：
```
Serving HTTP on :: port 8080
```

---

### 開瀏覽器

| 網址 | 用途 |
|------|------|
| `http://localhost:8080` | 首頁（基金列表） |
| `http://localhost:8080/fund.html?id=基金代號` | 單一基金分析頁 |
| `http://localhost:8080/compare.html` | 投資組合比較頁 |
| `http://localhost:5000/funds` | 直接測試後端 API |

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

---

## API 端點一覽

| Method | Path | 說明 |
|--------|------|------|
| GET | `/funds` | 基金列表（支援 q / type / sort / limit）|
| GET | `/funds/<id>` | 單一基金基本資訊 |
| GET | `/funds/<id>/nav?period=3Y` | 歷史 NAV |
| GET | `/funds/<id>/metrics?period=3Y` | 風險指標 |
| POST | `/compare` | 多基金比較 |

---

## 常見問題

**`ModuleNotFoundError: No module named 'flask'`**
→ 虛擬環境沒啟動，執行 `source venv/bin/activate`

**`400 Bad Request` 打 FinMind API**
→ Token 有空白或換行，重新 `export FINMIND_TOKEN="token"` 確認沒有多餘字元

**前端打開是空白或 API 失敗**
→ 確認後端有跑（Terminal 1 有 Running on 5000）
→ 確認前端用 `http://localhost:8080` 開，不是直接開 HTML 檔案