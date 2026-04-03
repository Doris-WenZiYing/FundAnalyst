"""
基金分析平台 — Flask 後端入口
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # 允許前端跨域呼叫


# ─────────────────────────────────────
#  TODO: 初始化資料來源
#  - 從 data/ 載入 CSV 或連接 DB
#  - 載入基準指數資料（台灣加權指數 / S&P 500）
#  - 設定無風險利率（預設 1.5%）
# ─────────────────────────────────────


# ── 基金列表 ──────────────────────────

@app.route("/funds", methods=["GET"])
def get_funds():
    """
    GET /funds
    查詢參數：
      - q: 搜尋關鍵字（基金名稱 / 代號）
      - type: 基金類型篩選
      - sort: 排序欄位（sharpe / return / mdd）

    TODO:
      1. 從資料來源讀取基金列表
      2. 套用 q / type / sort 過濾條件
      3. 回傳格式：
         [
           {
             "id": "0001",
             "name": "XX基金",
             "company": "XX投信",
             "type": "股票型",
             "nav": 12.34,
             "nav_date": "2024-01-15"
           }, ...
         ]
    """
    # TODO: 實作
    return jsonify({"message": "TODO: 回傳基金列表"})


# ── 單一基金 ──────────────────────────

@app.route("/funds/<fund_id>", methods=["GET"])
def get_fund(fund_id):
    """
    GET /funds/<fund_id>
    回傳單一基金基本資訊

    TODO:
      1. 用 fund_id 查詢基金資料
      2. 回傳格式：
         {
           "id": "0001",
           "name": "XX基金",
           "company": "XX投信",
           "type": "股票型",
           "aum": 50.2,        # 規模（億）
           "expense_ratio": 1.5,
           "risk_level": 3,
           "nav": 12.34,
           "nav_date": "2024-01-15"
         }
    """
    # TODO: 實作
    return jsonify({"message": f"TODO: 回傳基金 {fund_id} 資料"})


@app.route("/funds/<fund_id>/nav", methods=["GET"])
def get_fund_nav(fund_id):
    """
    GET /funds/<fund_id>/nav
    查詢參數：
      - period: 1Y / 3Y / 5Y（預設 3Y）

    TODO:
      1. 依 period 計算起始日期
      2. 查詢該基金的歷史 NAV
      3. 同時回傳基準指數的歷史資料（供比較圖用）
      4. 回傳格式：
         {
           "fund": [{"date": "2021-01-04", "nav": 10.00}, ...],
           "benchmark": [{"date": "2021-01-04", "value": 100.00}, ...]
         }
    """
    # TODO: 實作
    return jsonify({"message": f"TODO: 回傳基金 {fund_id} NAV 歷史"})


@app.route("/funds/<fund_id>/metrics", methods=["GET"])
def get_fund_metrics(fund_id):
    """
    GET /funds/<fund_id>/metrics
    查詢參數：
      - period: 1Y / 3Y / 5Y（預設 3Y）

    TODO:
      1. 取得該基金在指定期間的 NAV 序列
      2. 取得同期間的基準指數資料
      3. 呼叫 calculators 各模組計算指標
      4. 回傳格式：
         {
           "period": "3Y",
           "sharpe": 1.23,
           "sortino": 1.89,
           "mdd": -0.123,
           "beta": 0.82,
           "alpha": 0.021,
           "calmar": 0.95,
           "annualized_return": 0.087,
           "annualized_std": 0.124
         }
    """
    # TODO: 實作
    return jsonify({"message": f"TODO: 回傳基金 {fund_id} 指標"})


# ── 多基金比較 ────────────────────────

@app.route("/compare", methods=["POST"])
def compare_funds():
    """
    POST /compare
    Body: { "fund_ids": ["0001", "0002", "0003"], "period": "3Y" }

    TODO:
      1. 解析 fund_ids 和 period
      2. 驗證：基金數量限制 3–5 檔
      3. 對每檔基金分別呼叫指標計算
      4. 回傳格式：
         {
           "period": "3Y",
           "funds": [
             {
               "id": "0001",
               "name": "XX基金",
               "metrics": { "sharpe": 1.23, "sortino": 1.89, ... },
               "nav_series": [{"date": "...", "normalized": 100.0}, ...]
             }, ...
           ]
         }
      注意：nav_series 起點標準化為 100
    """
    # TODO: 實作
    body = request.get_json()
    return jsonify({"message": "TODO: 回傳多基金比較資料", "received": body})


# ─────────────────────────────────────

if __name__ == "__main__":
    app.run(debug=True, port=5000)
