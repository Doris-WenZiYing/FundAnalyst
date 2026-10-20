"""
執行：在 backend/ 底下 `python -m pytest tests -q`
不需要網路，股價用假資料。
"""

import numpy as np
import pandas as pd
import pytest

from calculators.stock_selection import (
    stock_metrics, rank_stocks, equal_weight_portfolio, financial_filter,
)


def _prices(start_price, end_price, days=200):
    idx = pd.bdate_range("2026-01-02", periods=days)
    return pd.Series(np.linspace(start_price, end_price, days), index=idx)


# ── stock_metrics ───────────────────────────────
def test_period_return_and_annualized():
    s = _prices(100, 120, days=253)            # 252 筆日報酬 = 一年
    m = stock_metrics(s)
    assert m["period_return"] == pytest.approx(0.20, abs=1e-4)
    assert m["annualized_return"] == pytest.approx(0.20, abs=1e-4)
    assert m["days"] == 252


def test_mdd_is_negative_drawdown():
    idx = pd.bdate_range("2026-01-02", periods=4)
    m = stock_metrics(pd.Series([100, 120, 90, 110], index=idx))
    assert m["mdd"] == pytest.approx(90 / 120 - 1, abs=1e-4)


def test_too_short_series():
    assert stock_metrics(pd.Series([100.0], index=pd.bdate_range("2026-01-02", periods=1))) == {"days": 1}


# ── rank_stocks ─────────────────────────────────
def _row(sid, ret, passed=True):
    return {"stock_id": sid, "name": sid, "metrics": {"period_return": ret}, "passed_filter": passed}


def test_rank_top_n_and_filter():
    rows = [_row("A", 0.1), _row("B", 0.5), _row("C", 0.3, passed=False), _row("D", None), _row("E", 0.2)]
    out = rank_stocks(rows, "period_return", top_n=2)
    assert [r["stock_id"] for r in out[:3]] == ["B", "E", "A"]
    assert [r["selected"] for r in out[:3]] == [True, True, False]
    excluded = {r["stock_id"]: r for r in out[3:]}
    assert set(excluded) == {"C", "D"}
    assert all(r["rank"] is None and not r["selected"] for r in excluded.values())


def test_lower_is_better_for_volatility():
    rows = [{"stock_id": "A", "metrics": {"annualized_std": 0.3}},
            {"stock_id": "B", "metrics": {"annualized_std": 0.1}}]
    assert rank_stocks(rows, "annualized_std", 1)[0]["stock_id"] == "B"


def test_bad_sort_key():
    with pytest.raises(ValueError):
        rank_stocks([], "nope")


# ── equal_weight_portfolio ──────────────────────
def test_equal_weight_buy_and_hold():
    a, b = _prices(100, 200, 10), _prices(50, 50, 10)
    port = equal_weight_portfolio({"A": a, "B": b})
    assert port.iloc[0] == pytest.approx(1.0)
    assert port.iloc[-1] == pytest.approx(1.5)   # (2.0 + 1.0) / 2


# ── financial_filter（論文 3.3.1）───────────────
def _fin(roe, eps, gm, financial=False):
    return {"years": [2021, 2022, 2023, 2024, 2025], "roe": roe, "eps": eps,
            "gross_margin": gm, "is_financial": financial}


def test_thesis_rules():
    good = _fin([12, 11, 10.5, 13, 12], [1, 2, 3, 2, 1], [20] * 5)
    assert financial_filter(good)["passed"]

    # 華碩案例：毛利率五年平均 14.43%，依論文條件應被排除
    asus = _fin([12.655] * 5, [21.11] * 5, [14.432] * 5)
    res = financial_filter(asus)
    assert not res["passed"] and res["checks"]["gross_margin_avg"] is False
    assert any("毛利率" in r for r in res["reasons"])

    neg_eps = _fin([12] * 5, [1, -0.5, 2, 2, 2], [20] * 5)
    assert not financial_filter(neg_eps)["passed"]


def test_financial_stock_excluded():
    bank = _fin([11] * 5, [2] * 5, [None] * 5, financial=True)
    res = financial_filter(bank)
    assert not res["passed"] and res["checks"]["not_financial"] is False
    assert any("金融股" in r for r in res["reasons"])


def test_missing_year_fails():
    gap = _fin([12, None, 12, 12, 12], [1] * 5, [20] * 5)
    res = financial_filter(gap)
    assert not res["passed"] and res["checks"]["complete"] is False


def test_rule_can_be_disabled():
    low_gm = _fin([12] * 5, [1] * 5, [10] * 5)
    assert not financial_filter(low_gm)["passed"]
    assert financial_filter(low_gm, {"gross_margin_avg_min": None})["passed"]


def test_no_fundamentals_fails():
    res = financial_filter(None)
    assert not res["passed"] and res["reasons"] == ["抓不到財報資料"]


# ── financials.compute_annual ───────────────────
from financials import compute_annual   # noqa: E402

Q = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}


def _fs_rows(years, cumulative=False, financial=False):
    """每季營收 100、毛利 40、母公司淨利 10、EPS 1（單季）"""
    rows = []
    for y in years:
        for q in (1, 2, 3, 4):
            k = q if cumulative else 1
            d = f"{y}-{Q[q]}"
            rows += [
                {"date": d, "type": "Revenue", "value": 100 * k},
                {"date": d, "type": "EquityAttributableToOwnersOfParent", "value": 10 * k},
                {"date": d, "type": "EPS", "value": 1 * k},
            ]
            rows.append({"date": d, "type": "NetInterestIncome" if financial else "GrossProfit",
                         "value": 40 * k})
    return rows


def _bs_rows(years, equity=400):
    return [{"date": f"{y}-{Q[q]}", "type": "EquityAttributableToOwnersOfParent", "value": equity}
            for y in years for q in (1, 2, 3, 4)]


def test_compute_annual_single_quarter():
    years = [2021, 2022, 2023, 2024, 2025]
    out = compute_annual(_fs_rows([2020] + years), _bs_rows([2020] + years), years)
    assert out["cumulative"] is False and out["is_financial"] is False
    assert out["eps"] == [4.0] * 5               # 四季加總
    assert out["roe"] == [10.0] * 5              # 40 / 400
    assert out["gross_margin"] == [40.0] * 5     # 160 / 400


def test_compute_annual_cumulative_same_result():
    years = [2021, 2022, 2023, 2024, 2025]
    out = compute_annual(_fs_rows([2020] + years, cumulative=True), _bs_rows([2020] + years), years)
    assert out["cumulative"] is True
    assert out["eps"] == [4.0] * 5 and out["roe"] == [10.0] * 5 and out["gross_margin"] == [40.0] * 5


def test_compute_annual_missing_quarter_gives_none():
    years = [2024, 2025]
    rows = [r for r in _fs_rows(years) if r["date"] != "2025-06-30"]
    out = compute_annual(rows, _bs_rows(years), years)
    assert out["eps"][0] == 4.0 and out["eps"][1] is None


def test_compute_annual_detects_financial():
    years = [2025]
    out = compute_annual(_fs_rows(years, financial=True), _bs_rows(years), years)
    assert out["is_financial"] is True and out["gross_margin"] == [None]


# ── 舊網站年化 bug 修正 ──────────────────────────
def test_fill_series_keeps_trading_days_only():
    from data_source import _fill_series
    s = _prices(100, 110, days=10)                # 10 個交易日，中間有週末
    out = _fill_series(s)
    assert len(out) == 10


def test_annualized_return_uses_return_periods():
    from calculators.returns import annualized_return
    s = _prices(100, 120, days=253)
    assert annualized_return(s) == pytest.approx(0.20, abs=1e-6)


# ── API ─────────────────────────────────────────
GOOD_FIN = _fin([15] * 5, [5] * 5, [30] * 5)
BAD_FIN  = _fin([5] * 5, [1] * 5, [30] * 5)


@pytest.fixture
def client(monkeypatch):
    import app as app_module

    fake = {
        "2330": _prices(100, 150), "2454": _prices(100, 90), "2317": _prices(100, 130),
        "2308": _prices(100, 110), "3711": _prices(100, 170), "2303": _prices(100, 100),
        "0050": _prices(100, 125),
    }

    def fake_price(sid, start, end, with_source=False):
        s = fake.get(sid, pd.Series(dtype=float))
        out = (s, True, "Yahoo 還原股價") if not s.empty else (s, False, None)
        return out if with_source else out[:2]

    # 3711 財報不合格，用來確認會被篩掉
    def fake_fin(sid, end_year, n_years=5):
        return BAD_FIN if sid == "3711" else GOOD_FIN

    monkeypatch.setattr(app_module, "get_price_series", fake_price)
    monkeypatch.setattr(app_module, "get_fundamentals", fake_fin)
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def test_screen_endpoint_without_filter(client):
    r = client.get("/etfs/0050/screen?start=2026-01-01&end=2026-10-08&top=2&filter=0")
    assert r.status_code == 200
    d = r.get_json()
    assert [x["stock_id"] for x in d["rankings"][:2]] == ["3711", "2330"]
    assert [x["selected"] for x in d["rankings"]].count(True) == 2
    assert d["portfolio"]["metrics"]["period_return"] == pytest.approx((0.7 + 0.5) / 2, abs=1e-3)
    assert d["benchmark"]["metrics"]["period_return"] == pytest.approx(0.25, abs=1e-3)
    assert d["adjusted"] is True and d["price_sources"] == ["Yahoo 還原股價"]
    assert d["filter"]["enabled"] is False


def test_screen_endpoint_with_filter(client):
    d = client.get("/etfs/0050/screen?start=2026-01-01&end=2026-10-08&top=2").get_json()
    assert d["filter"]["enabled"] is True
    assert d["filter"]["fin_years"] == [2021, 2022, 2023, 2024, 2025]
    assert d["filter"]["passed"] == 5 and d["filter"]["total"] == 6
    top = [x["stock_id"] for x in d["rankings"] if x["selected"]]
    assert top == ["2330", "2317"]                      # 3711 被財務條件篩掉
    excluded = next(x for x in d["rankings"] if x["stock_id"] == "3711")
    assert excluded["rank"] is None and any("ROE" in r for r in excluded["filter"]["reasons"])


def test_screen_filter_threshold_params(client):
    d = client.get("/etfs/0050/screen?start=2026-01-01&end=2026-10-08&roe_min=&top=1").get_json()
    assert d["filter"]["passed"] == 6                   # 不檢查 ROE → 全部通過
    assert d["rankings"][0]["stock_id"] == "3711"
    assert client.get("/etfs/0050/screen?roe_min=abc").status_code == 400


def test_screen_rejects_bad_input(client):
    assert client.get("/etfs/9999/screen").status_code == 404
    assert client.get("/etfs/0050/screen?sort=xx").status_code == 400
    assert client.get("/etfs/0050/screen?start=2026-05-01&end=2026-01-01").status_code == 400


def test_etf_list(client):
    d = client.get("/etfs").get_json()
    assert d[0]["etf_id"] == "0050"


# ── Yahoo 解析（模擬新版 yfinance 的 MultiIndex 欄位）────
def test_yahoo_multiindex(monkeypatch):
    import sys, types
    import stock_data
    idx = pd.to_datetime(["2026-10-15", "2026-10-16"])
    cols = pd.MultiIndex.from_tuples([("Close", "2330.TW"), ("Open", "2330.TW")], names=["Price", "Ticker"])
    df = pd.DataFrame([[2440.0, 2420.0], [2420.0, 2430.0]], index=idx, columns=cols)
    calls = []

    def fake_download(ticker, **kw):
        calls.append((ticker, kw["end"]))
        return df if ticker.endswith(".TW") else pd.DataFrame()

    monkeypatch.setitem(sys.modules, "yfinance", types.SimpleNamespace(download=fake_download))
    s = stock_data._fetch_yahoo("2330", "2026-10-15", "2026-10-16")
    assert list(s) == [2440.0, 2420.0]
    assert calls[0] == ("2330.TW", "2026-10-17")        # end +1 天


def test_price_source_order(monkeypatch):
    import stock_data
    monkeypatch.setattr(stock_data.cache, "get", lambda *a, **k: None)
    monkeypatch.setattr(stock_data.cache, "set", lambda *a, **k: None)
    monkeypatch.setattr(stock_data, "_finmind_adj_available", True)
    monkeypatch.setattr(stock_data, "_fetch_finmind", lambda ds, *a: pd.Series(dtype=float)
                        if ds == "TaiwanStockPriceAdj" else _prices(1, 2))
    monkeypatch.setattr(stock_data, "_fetch_yahoo", lambda *a: _prices(10, 20))
    monkeypatch.setattr(stock_data, "PRICE_SOURCES", (
        ("FinMind 還原股價", True, stock_data._fetch_finmind_adj),
        ("Yahoo 還原股價", True, lambda *a: stock_data._fetch_yahoo(*a)),
        ("FinMind 收盤價", False, lambda sid, s, e: stock_data._fetch_finmind("TaiwanStockPrice", sid, s, e)),
    ))
    s, adj, src = stock_data.get_price_series("2330", "2026-01-01", "2026-10-16", with_source=True)
    assert adj is True and src == "Yahoo 還原股價" and s.iloc[0] == 10
    assert stock_data._finmind_adj_available is False


def test_old_nav_series_uses_trading_days(monkeypatch):
    import stock_data, data_source
    monkeypatch.setattr(stock_data, "get_price_series", lambda sid, s, e: (_prices(100, 120, 253), True))
    nav = data_source.get_nav_series("0056", "1Y")
    from calculators.returns import annualized_return
    assert len(nav) == 253 and annualized_return(nav) == pytest.approx(0.20, abs=1e-6)


def test_yahoo_missing_last_day_extended(monkeypatch):
    import stock_data
    yahoo = pd.Series([65.62, 108.90], index=pd.to_datetime(["2026-01-02", "2026-10-15"]))
    raw   = pd.Series([108.0, 109.0], index=pd.to_datetime(["2026-10-15", "2026-10-16"]))
    monkeypatch.setattr(stock_data, "_fetch_finmind", lambda ds, sid, s, e: raw)
    out = stock_data._extend_with_raw(yahoo, "0050", "2026-10-16")
    assert out.index[-1] == pd.Timestamp("2026-10-16")
    assert out.iloc[-1] == pytest.approx(108.90 * 109.0 / 108.0)
    # 已經到結束日就不動
    assert stock_data._extend_with_raw(out, "0050", "2026-10-16").equals(out)


# ── 年初名單反推 ─────────────────────────────────
def test_build_start_list_reverses_changes():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location("bsl", os.path.join(os.path.dirname(__file__), "..", "tools", "build_start_list.py"))
    bsl = importlib.util.module_from_spec(spec); spec.loader.exec_module(bsl)
    end = [{"stock_id": s, "name": s, "weight": 1.0} for s in ["A", "B", "N1", "N2"]]
    changes = [
        {"review": "3月", "effective": "2026-03-20", "added": [["N1", "N1"], ["X", "X"]], "removed": [["R1", "R1"], ["Y", "Y"]]},
        {"review": "6月", "effective": "2026-06-18", "added": [["N2", "N2"], ["Y", "Y"]], "removed": [["R2", "R2"], ["X", "X"]]},
        {"review": "去年12月", "effective": "2025-12-19", "added": [["A", "A"]], "removed": [["Z", "Z"]]},
    ]
    # 期末名單要含 6 月加入的 Y，3 月加入、6 月又刪除的 X 不在期末
    end.append({"stock_id": "Y", "name": "Y", "weight": 1.0})
    start, applied = bsl.rebuild(end, changes, "2026-01-01")
    ids = {c["stock_id"] for c in start}
    # 撤銷 6 月：刪 N2、Y，加回 R2、X → 撤銷 3 月：刪 N1、X，加回 R1、Y
    # 去年 12 月的異動在開始日前，不撤銷，所以 A 留著
    assert ids == {"A", "B", "R1", "R2", "Y"}
    assert applied == ["6月", "3月"]
    assert all(c["weight"] is None for c in start)


def test_screen_uses_benchmark_id(client, monkeypatch):
    import app as app_module
    data = app_module.get_constituents("0050")
    monkeypatch.setattr(app_module, "get_constituents",
                        lambda etf_id: {**data, "benchmark_id": "0050"} if etf_id == "0050@2026-10-16" else None)
    d = client.get("/etfs/0050@2026-10-16/screen?start=2026-01-01&end=2026-10-08&filter=0").get_json()
    assert d["benchmark"]["label"].startswith("0050")
    assert d["benchmark"]["metrics"]["period_return"] == pytest.approx(0.25, abs=1e-3)


def test_gross_margin_from_cogs_when_no_gross_profit():
    """和泰車：FinMind 沒有 GrossProfit，只有 Revenue 與 CostOfGoodsSold"""
    years = [2025]
    rows = [r for r in _fs_rows(years) if r["type"] != "GrossProfit"]
    rows += [{"date": f"2025-{Q[q]}", "type": "CostOfGoodsSold", "value": 75} for q in (1, 2, 3, 4)]
    out = compute_annual(rows, _bs_rows(years), years)
    assert out["gross_margin"] == [25.0] and out["gross_profit_derived"] is True
    assert out["is_financial"] is False


def test_hotai_2022_loss_matches():
    """和泰車 2022 實際季 EPS：7.86、-1.49、-24.99、-16.77 → 年度 -35.39"""
    eps = [7.86, -1.49, -24.99, -16.77]
    rows = [{"date": f"2022-{Q[q]}", "type": "EPS", "value": v} for q, v in zip((1, 2, 3, 4), eps)]
    rows += [{"date": f"2022-{Q[q]}", "type": "Revenue", "value": 6e10} for q in (1, 2, 3, 4)]
    out = compute_annual(rows, [], [2022])
    assert out["eps"] == [-35.39]


# ── 匯入 → 反推 完整流程 ─────────────────────────
def _run_tool(name, argv):
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(name, os.path.join(os.path.dirname(__file__), "..", "tools", f"{name}.py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod.main(argv)


def test_import_then_build_flow(tmp_path):
    import json, shutil, os
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    data = tmp_path / "c.json"
    shutil.copy(os.path.join(base, "etf_constituents.json"), data)
    changes = os.path.join(base, "index_changes_0050.json")
    before = json.loads(data.read_text(encoding="utf-8"))

    # 範例 CSV 只有 2 檔：匯入不會蓋掉年初名單 "0050"
    small = tmp_path / "small.csv"
    small.write_text("代號,名稱,權重\n2330,台積電,56.66\n2454,聯發科,5.99\n", encoding="utf-8-sig")
    _run_tool("import_constituents", ["0050", "元大台灣50", str(small), "--as-of", "2026-10-20", "--data", str(data)])
    d = json.loads(data.read_text(encoding="utf-8"))
    assert d["0050"] == before["0050"] and len(d["0050@2026-10-20"]["constituents"]) == 2

    # 反推時用最新的 2 檔名單 → 應該明確報錯，而不是默默產生錯的名單
    with pytest.raises(SystemExit) as e:
        _run_tool("build_start_list", ["0050", "2026-01-01", "--data", str(data), "--changes", changes])
    assert "0050@2026-10-20" in str(e.value)

    # 匯入完整名單後重跑，年初名單與原本一致
    full = tmp_path / "full.csv"
    rows = before["0050@2026-10-16"]["constituents"]
    full.write_text("代號,名稱,權重\n" + "".join(f"{c['stock_id']},{c['name']},{c['weight']}\n" for c in rows), encoding="utf-8-sig")
    _run_tool("import_constituents", ["0050", "元大台灣50", str(full), "--as-of", "2026-10-20", "--data", str(data)])
    _run_tool("build_start_list", ["0050", "2026-01-01", "--data", str(data), "--changes", changes])
    d = json.loads(data.read_text(encoding="utf-8"))
    assert {c["stock_id"] for c in d["0050"]["constituents"]} == {c["stock_id"] for c in before["0050"]["constituents"]}
