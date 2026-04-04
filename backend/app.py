"""
app.py（FinMind API）
把原本 load_data() + get_nav_series() + get_benchmark_series()
全部換成 data_source.py，其餘路由邏輯不變
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
from calculators.risk import annualized_std, downside_std, max_drawdown
from calculators.ratios import sharpe_ratio, sortino_ratio, calmar_ratio
from calculators.capm import beta, alpha

app = Flask(__name__)
CORS(app)

RF = 0.015  # 無風險利率


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


@app.route("/funds", methods=["GET"])
def get_funds():
    q     = request.args.get("q", "").lower()
    ftype = request.args.get("type", "")
    sort  = request.args.get("sort", "")
    limit = request.args.get("limit", type=int)

    df = get_fund_list()  # ← 從 FinMind 拿，其餘邏輯完全一樣

    if q:
        df = df[df["name"].str.lower().str.contains(q) | df["fund_id"].str.contains(q)]
    if ftype:
        df = df[df["type"] == ftype]
    if sort and sort in df.columns:
        df = df.sort_values(sort)
    if limit:
        df = df.head(limit)

    return jsonify(df.to_dict(orient="records"))


@app.route("/funds/<fund_id>", methods=["GET"])
def get_fund(fund_id):
    info = get_fund_info(fund_id)  # ← 從 FinMind 拿
    if not info:
        return jsonify({"error": "找不到基金"}), 404
    return jsonify(info)


@app.route("/funds/<fund_id>/nav", methods=["GET"])
def get_fund_nav(fund_id):
    period = request.args.get("period", "3Y")
    nav    = get_nav_series(fund_id, period)   # ← 從 FinMind 拿
    bench  = get_benchmark_series(period)       # ← 從 FinMind 拿

    if nav.empty:
        return jsonify({"error": "無 NAV 資料"}), 404

    return jsonify({
        "fund":                [{"date": str(d.date()), "nav": round(v, 4)} for d, v in nav.items()],
        "fund_normalized":     [{"date": str(d.date()), "value": round(v, 4)} for d, v in normalize_to_100(nav).items()],
        "benchmark_normalized":[{"date": str(d.date()), "value": round(v, 4)} for d, v in normalize_to_100(bench).items()] if not bench.empty else [],
    })


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
            "id":       fid,
            "name":     info["name"] if info else fid,
            "metrics":  compute_metrics(nav, bench, period),
            "nav_series": [
                {"date": str(d.date()), "normalized": round(v, 4)}
                for d, v in normalize_to_100(nav).items()
            ],
        })

    return jsonify({"period": period, "funds": results})


if __name__ == "__main__":
    app.run(debug=True, port=5000)