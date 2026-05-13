"""
app.py — Flask 後端主程式
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from data_source import (
    get_fund_list,
    get_fund_info,
    get_nav_series,
    get_benchmark_series,
)
from calculators.returns import daily_returns, annualized_return, normalize_to_100
from calculators.risk    import annualized_std, downside_std, max_drawdown
from calculators.ratios  import sharpe_ratio, sortino_ratio, calmar_ratio
from calculators.capm    import beta, alpha
from calculators.scoring import compute_scores, DEFAULT_WEIGHTS

app  = Flask(__name__)
CORS(app)

RF = 0.015  # 無風險利率（台灣 10 年期公債，約 1.5%）


# ── 共用：計算單一 ETF 的所有指標 ─────────────
def compute_metrics(nav, bench, period):
    ret           = daily_returns(nav)
    bench_ret     = daily_returns(bench)
    ann_ret       = annualized_return(nav)
    ann_std       = annualized_std(ret)
    d_std         = downside_std(ret, rf_daily=RF / 252)
    mdd           = max_drawdown(nav)
    bench_ann_ret = annualized_return(bench)
    b             = beta(ret, bench_ret)

    def _r(v): return round(v, 4) if v is not None else None

    return {
        "period":            period,
        "annualized_return": _r(ann_ret),
        "annualized_std":    _r(ann_std),
        "sharpe":            _r(sharpe_ratio(ann_ret, RF, ann_std)),
        "sortino":           _r(sortino_ratio(ann_ret, RF, d_std)),
        "mdd":               _r(mdd),
        "beta":              _r(b),
        "alpha":             _r(alpha(ann_ret, RF, b, bench_ann_ret)),
        "calmar":            _r(calmar_ratio(ann_ret, mdd)),
    }


# ── GET /funds ─────────────────────────────────
@app.route("/funds", methods=["GET"])
def get_funds():
    q     = request.args.get("q", "").lower()
    ftype = request.args.get("type", "")
    sort  = request.args.get("sort", "")
    limit = request.args.get("limit", type=int)

    df = get_fund_list()

    if q:
        df = df[df["name"].str.lower().str.contains(q, na=False) |
                df["fund_id"].str.lower().str.contains(q, na=False)]
    if ftype:
        df = df[df["type"] == ftype]
    if sort and sort in df.columns:
        df = df.sort_values(sort)
    if limit:
        df = df.head(limit)

    return jsonify(df.to_dict(orient="records"))


# ── GET /funds/<id> ────────────────────────────
@app.route("/funds/<fund_id>", methods=["GET"])
def get_fund(fund_id):
    info = get_fund_info(fund_id)
    if not info:
        return jsonify({"error": "找不到 ETF"}), 404
    return jsonify(info)


# ── GET /funds/<id>/nav ────────────────────────
@app.route("/funds/<fund_id>/nav", methods=["GET"])
def get_fund_nav(fund_id):
    period = request.args.get("period", "3Y")
    nav    = get_nav_series(fund_id, period)
    bench  = get_benchmark_series(period)

    if nav.empty:
        return jsonify({"error": "無 NAV 資料"}), 404

    return jsonify({
        "fund": [
            {"date": str(d.date()), "nav": round(v, 4)}
            for d, v in nav.items()
        ],
        "fund_normalized": [
            {"date": str(d.date()), "value": round(v, 4)}
            for d, v in normalize_to_100(nav).items()
        ],
        "benchmark_normalized": [
            {"date": str(d.date()), "value": round(v, 4)}
            for d, v in normalize_to_100(bench).items()
        ] if not bench.empty else [],
    })


# ── GET /funds/<id>/metrics ────────────────────
@app.route("/funds/<fund_id>/metrics", methods=["GET"])
def get_fund_metrics(fund_id):
    period = request.args.get("period", "3Y")
    nav    = get_nav_series(fund_id, period)
    bench  = get_benchmark_series(period)

    if nav.empty:
        return jsonify({"error": "無 NAV 資料"}), 404
    if bench.empty:
        return jsonify({"error": "無基準指數資料"}), 404

    return jsonify(compute_metrics(nav, bench, period))


# ── POST /compare ──────────────────────────────
@app.route("/compare", methods=["POST"])
def compare_funds():
    body     = request.get_json()
    fund_ids = body.get("fund_ids", [])
    period   = body.get("period", "3Y")

    if not 2 <= len(fund_ids) <= 5:
        return jsonify({"error": "基金數量需在 2–5 檔之間"}), 400

    bench   = get_benchmark_series(period)
    results = []

    for fid in fund_ids:
        nav  = get_nav_series(fid, period)
        info = get_fund_info(fid)
        if nav.empty:
            continue
        results.append({
            "id":   fid,
            "name": info["name"] if info else fid,
            "metrics": compute_metrics(nav, bench, period),
            "nav_series": [
                {"date": str(d.date()), "normalized": round(v, 4)}
                for d, v in normalize_to_100(nav).items()
            ],
        })

    return jsonify({"period": period, "funds": results})


# ── POST /score ────────────────────────────────
@app.route("/score", methods=["POST"])
def score_funds():
    """
    多準則評選模型
    body: {
      "period": "3Y",
      "weights": {
        "return":    {"dimension_weight": 0.33, "metrics": {"annualized_return": 0.6, "alpha": 0.4}},
        "risk":      {"dimension_weight": 0.34, "metrics": {"mdd": 0.4, "beta": 0.3, "annualized_std": 0.3}},
        "stability": {"dimension_weight": 0.33, "metrics": {"sharpe": 0.4, "sortino": 0.35, "calmar": 0.25}}
      }
    }
    """
    body    = request.get_json() or {}
    period  = body.get("period", "3Y")
    weights = body.get("weights", DEFAULT_WEIGHTS)

    bench   = get_benchmark_series(period)
    if bench.empty:
        return jsonify({"error": "無法取得基準指數資料"}), 500

    fund_list = get_fund_list().to_dict(orient="records")
    funds_metrics = []

    for fund in fund_list:
        fid = fund["fund_id"]
        try:
            nav = get_nav_series(fid, period)
            if nav.empty:
                continue
            m = compute_metrics(nav, bench, period)
            funds_metrics.append({
                "fund_id": fid,
                "name":    fund["name"],
                "metrics": m,
            })
        except Exception as e:
            app.logger.warning(f"計算 {fid} 失敗：{e}")
            continue

    if not funds_metrics:
        return jsonify({"error": "無法計算任何 ETF 的指標"}), 500

    rankings = compute_scores(funds_metrics, weights)
    return jsonify({"period": period, "rankings": rankings})


# ── GET /score/defaults ────────────────────────
@app.route("/score/defaults", methods=["GET"])
def score_defaults():
    """回傳預設權重設定，讓前端初始化 slider 用"""
    return jsonify(DEFAULT_WEIGHTS)


if __name__ == "__main__":
    app.run(debug=True, port=5000)