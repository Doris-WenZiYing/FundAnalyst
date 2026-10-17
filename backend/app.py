"""
app.py — Flask 後端
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from data_source import (
    get_fund_list, get_fund_info,
    get_nav_series, get_benchmark_series,
)
from calculators.returns import daily_returns, annualized_return, normalize_to_100
from calculators.risk    import annualized_std, downside_std, max_drawdown
from calculators.ratios  import sharpe_ratio, sortino_ratio, calmar_ratio
from calculators.capm    import beta, alpha
from calculators.scoring import compute_scores, DEFAULT_WEIGHTS
from calculators.mvo     import max_sharpe, min_volatility, efficient_frontier, equal_weight_metrics
from calculators.backtest import run_backtest

app  = Flask(__name__)
CORS(app)
RF   = 0.015


# ── 共用：計算單一 ETF 指標 ───────────────────────
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
        "fund": [{"date": str(d.date()), "nav": round(v, 4)} for d, v in nav.items()],
        "fund_normalized": [{"date": str(d.date()), "value": round(v, 4)}
                            for d, v in normalize_to_100(nav).items()],
        "benchmark_normalized": [{"date": str(d.date()), "value": round(v, 4)}
                                  for d, v in normalize_to_100(bench).items()]
                                 if not bench.empty else [],
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
            "metrics":    compute_metrics(nav, bench, period),
            "nav_series": [{"date": str(d.date()), "normalized": round(v, 4)}
                           for d, v in normalize_to_100(nav).items()],
        })

    return jsonify({"period": period, "funds": results})


# ── POST /score ────────────────────────────────
@app.route("/score", methods=["POST"])
def score_funds():
    body    = request.get_json() or {}
    period  = body.get("period", "3Y")
    weights = body.get("weights", DEFAULT_WEIGHTS)

    bench = get_benchmark_series(period)
    if bench.empty:
        return jsonify({"error": "無法取得基準指數"}), 500

    funds_metrics = []
    for fund in get_fund_list().to_dict(orient="records"):
        fid = fund["fund_id"]
        try:
            nav = get_nav_series(fid, period)
            if nav.empty:
                continue
            funds_metrics.append({
                "fund_id": fid,
                "name":    fund["name"],
                "metrics": compute_metrics(nav, bench, period),
            })
        except Exception as e:
            app.logger.warning(f"{fid} 計算失敗：{e}")

    if not funds_metrics:
        return jsonify({"error": "無法計算任何指標"}), 500

    return jsonify({"period": period, "rankings": compute_scores(funds_metrics, weights)})


@app.route("/score/defaults", methods=["GET"])
def score_defaults():
    return jsonify(DEFAULT_WEIGHTS)


# ── POST /optimize ─────────────────────────────
@app.route("/optimize", methods=["POST"])
def optimize():
    """
    MVO 資產配置最佳化

    body: {
      "fund_ids": ["0050", "00878", "0056"],
      "period":   "3Y",
      "method":   "max_sharpe" | "min_volatility"
    }

    回傳: {
      "mvo":      {weights, expected_return, volatility, sharpe},
      "equal":    {weights, expected_return, volatility, sharpe},
      "frontier": [{return, volatility, sharpe}, ...],
    }
    """
    body     = request.get_json() or {}
    fund_ids = body.get("fund_ids", [])
    period   = body.get("period", "3Y")
    method   = body.get("method", "max_sharpe")

    if len(fund_ids) < 2:
        return jsonify({"error": "至少需要 2 檔 ETF"}), 400
    if len(fund_ids) > 10:
        return jsonify({"error": "最多 10 檔 ETF"}), 400

    # 抓歷史資料
    nav_dict = {}
    for fid in fund_ids:
        try:
            nav = get_nav_series(fid, period)
            if not nav.empty:
                nav_dict[fid] = nav
        except Exception as e:
            app.logger.warning(f"{fid} 資料取得失敗：{e}")

    if len(nav_dict) < 2:
        return jsonify({"error": "有效資料不足 2 檔"}), 400

    # 取 ETF 名稱
    fund_names = {}
    for fid in nav_dict:
        info = get_fund_info(fid)
        fund_names[fid] = info["name"] if info else fid

    # 執行最佳化
    if method == "min_volatility":
        mvo_result = min_volatility(nav_dict)
    else:
        mvo_result = max_sharpe(nav_dict)

    if "error" in mvo_result:
        return jsonify(mvo_result), 400

    equal_result  = equal_weight_metrics(nav_dict)
    frontier_data = efficient_frontier(nav_dict, n_points=25)

    return jsonify({
        "fund_ids":   list(nav_dict.keys()),
        "fund_names": fund_names,
        "period":     period,
        "method":     method,
        "mvo":        mvo_result,
        "equal":      equal_result,
        "frontier":   frontier_data,
    })


# ── POST /backtest ─────────────────────────────
@app.route("/backtest", methods=["POST"])
def backtest():
    """
    回測 MVO 配置 vs 等權重配置

    body: {
      "fund_ids":   ["0050", "00878"],
      "mvo_weights": {"0050": 0.6, "00878": 0.4},
      "period":     "3Y"
    }
    """
    body        = request.get_json() or {}
    fund_ids    = body.get("fund_ids", [])
    mvo_weights = body.get("mvo_weights", {})
    period      = body.get("period", "3Y")

    if len(fund_ids) < 2:
        return jsonify({"error": "至少需要 2 檔 ETF"}), 400

    nav_dict = {}
    for fid in fund_ids:
        try:
            nav = get_nav_series(fid, period)
            if not nav.empty:
                nav_dict[fid] = nav
        except Exception as e:
            app.logger.warning(f"{fid} 資料取得失敗：{e}")

    if len(nav_dict) < 2:
        return jsonify({"error": "有效資料不足 2 檔"}), 400

    result = run_backtest(nav_dict, mvo_weights)
    result["period"] = period
    return jsonify(result)


# ══════════════════════════════════════════════
# ETF 成分股篩選（2026 秋季新增）
# ══════════════════════════════════════════════
from datetime import date
from stock_data import list_etfs, get_constituents, get_price_series
from financials import get_fundamentals
from calculators.stock_selection import (
    stock_metrics, rank_stocks, equal_weight_portfolio,
    to_normalized_points, financial_filter, SORT_KEYS, THESIS_RULES,
)


def _float_arg(name, default):
    """門檻參數：空字串或 'off' 代表不檢查（回傳 None）"""
    raw = request.args.get(name)
    if raw is None:
        return default
    if raw.strip() in ("", "off", "none"):
        return None
    return float(raw)


def _filter_rules_from_args():
    return {
        "roe_avg_min":          _float_arg("roe_min", THESIS_RULES["roe_avg_min"]),
        "gross_margin_avg_min": _float_arg("gm_min",  THESIS_RULES["gross_margin_avg_min"]),
        "eps_all_positive":     request.args.get("eps_pos", "1") != "0",
        "exclude_financials":   True,
    }


def _window_from_args():
    today = date.today()
    start = request.args.get("start") or f"{today.year}-01-01"
    end   = request.args.get("end")   or today.isoformat()
    return start, end


# ── GET /etfs ──────────────────────────────────
@app.route("/etfs", methods=["GET"])
def etf_list():
    return jsonify(list_etfs())


# ── GET /etfs/<id>/constituents ────────────────
@app.route("/etfs/<etf_id>/constituents", methods=["GET"])
def etf_constituents(etf_id):
    data = get_constituents(etf_id)
    if not data:
        return jsonify({"error": f"沒有 {etf_id} 的成分股資料"}), 404
    return jsonify(data)


# ── GET /etfs/<id>/screen ──────────────────────
@app.route("/etfs/<etf_id>/screen", methods=["GET"])
def etf_screen(etf_id):
    """
    成分股排序篩選
    query：start, end（預設今年 1/1 到今天）
           sort（period_return / annualized_return / sharpe / annualized_std / mdd）
           top（取前幾名，預設 3）
           filter（1 = 啟用財務篩選，預設 1）
           roe_min、gm_min（門檻 %，空字串 = 不檢查）、eps_pos（0 = 不檢查）
           fin_end（財報最後一年，預設為開始日期的前一年），共取 5 年
    """
    data = get_constituents(etf_id)
    if not data:
        return jsonify({"error": f"沒有 {etf_id} 的成分股資料"}), 404

    start, end = _window_from_args()
    sort_key   = request.args.get("sort", "period_return")
    top_n      = max(1, min(request.args.get("top", default=3, type=int), 10))
    if sort_key not in SORT_KEYS:
        return jsonify({"error": f"不支援的排序欄位：{sort_key}"}), 400
    if start >= end:
        return jsonify({"error": "開始日期必須早於結束日期"}), 400

    use_filter = request.args.get("filter", "1") != "0"
    try:
        rules   = _filter_rules_from_args()
        fin_end = request.args.get("fin_end", type=int) or int(start[:4]) - 1
    except ValueError:
        return jsonify({"error": "篩選門檻必須是數字"}), 400
    fin_years = list(range(fin_end - 4, fin_end + 1))

    rows, prices, errors, adjusted_flags, sources = [], {}, [], [], set()
    for c in data["constituents"]:
        sid = c["stock_id"]
        try:
            s, adj, src = get_price_series(sid, start, end, with_source=True)
        except Exception as e:
            app.logger.warning(f"{sid} 股價失敗：{e}")
            s, adj, src = None, False, None
        if s is None or len(s) < 2:
            errors.append({"stock_id": sid, "name": c.get("name"), "error": "無股價資料"})
            continue
        prices[sid] = s
        adjusted_flags.append(adj)
        sources.add(src)
        row = {
            "stock_id": sid,
            "name":     c.get("name"),
            "weight":   c.get("weight"),
            "metrics":  stock_metrics(s),
        }
        if use_filter:
            try:
                fin = get_fundamentals(sid, fin_end)
            except Exception as e:
                app.logger.warning(f"{sid} 財報失敗：{e}")
                fin = None
            row["fundamentals"]  = fin
            row["filter"]        = financial_filter(fin, rules)
            row["passed_filter"] = row["filter"]["passed"]
        rows.append(row)

    if not rows:
        return jsonify({"error": "所有成分股都抓不到股價，請確認 FINMIND_TOKEN", "errors": errors}), 502

    ranked   = rank_stocks(rows, sort_key, top_n)
    selected = [r for r in ranked if r["selected"]]

    # 前 N 名等權重組合
    port = equal_weight_portfolio({r["stock_id"]: prices[r["stock_id"]] for r in selected})

    # 基準：ETF 本身
    bench_id = data.get("benchmark_id", etf_id)          # 對照名單（0050@日期）仍以 0050 為基準
    bench_s, bench_adj, bench_src = get_price_series(bench_id, start, end, with_source=True)
    sources.add(bench_src)

    return jsonify({
        "etf":      {"etf_id": etf_id, "name": data.get("name"), "as_of": data.get("as_of"),
                     "source": data.get("source"), "count": len(data["constituents"])},
        "window":   {"start": start, "end": end},
        "sort":     {"key": sort_key, "label": SORT_KEYS[sort_key][0]},
        "top_n":    top_n,
        "adjusted": bool(adjusted_flags) and all(adjusted_flags) and bench_adj,
        "price_sources": sorted(x for x in sources if x),
        "filter": {
            "enabled":   use_filter,
            "rules":     rules,
            "fin_years": fin_years,
            "passed":    sum(1 for r in rows if r.get("passed_filter", True)),
            "total":     len(rows),
        },
        "rankings": ranked,
        "errors":   errors,
        "portfolio": {
            "label":   f"前 {top_n} 名等權重",
            "metrics": stock_metrics(port) if not port.empty else {},
            "series":  to_normalized_points(port),
        },
        "benchmark": {
            "label":   f"{bench_id} {data.get('name', '').split('（')[0]}".strip(),
            "metrics": stock_metrics(bench_s) if len(bench_s) >= 2 else {},
            "series":  to_normalized_points(bench_s),
        },
        "selected_series": [
            {"stock_id": r["stock_id"], "name": r["name"],
             "series": to_normalized_points(prices[r["stock_id"]])}
            for r in selected
        ],
    })


if __name__ == "__main__":
    app.run(debug=True, port=5000)
