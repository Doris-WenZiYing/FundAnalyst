"""
stock_selection.py — ETF 成分股篩選與排序

流程（對應 0929 討論）：
  1. 母體 = ETF 成分股
  2. 篩選：財務指標門檻（financial_filter，第二週接資料）
  3. 排序：依報酬率等指標排序（rank_stocks）
  4. 取前 N 名（1 / 2 / 3）

輸入的股價 Series 必須只含交易日（不要補成日曆日）。
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

TRADING_DAYS = 252

# 可排序的欄位：(中文名稱, 越大越好?)
SORT_KEYS = {
    "period_return":     ("期間報酬率", True),
    "annualized_return": ("年化報酬率", True),
    "sharpe":            ("夏普值",     True),
    "annualized_std":    ("年化波動率", False),
    "mdd":               ("最大回檔",   True),   # MDD 為負值，越接近 0 越好
}

# 論文 3.3.1 的三個門檻
THESIS_RULES = {
    "roe_avg_min":          10.0,   # ROE 五年平均 > 10%
    "eps_all_positive":     True,   # EPS 連續五年 > 0
    "gross_margin_avg_min": 15.0,   # 毛利率五年平均 > 15%
    "exclude_financials":   True,   # 金融股沒有毛利率，先排除（之後再跟教授確認）
}


def _r(v, n=4):
    if v is None:
        return None
    v = float(v)
    return None if (np.isnan(v) or np.isinf(v)) else round(v, n)


# ── 單一股票績效 ─────────────────────────────────
def stock_metrics(prices: pd.Series, rf: float = 0.0) -> Dict:
    """
    prices：交易日收盤價。
    rf：年化無風險利率（論文假設 0）。

    period_return     = 末值 / 初值 - 1
    annualized_return = (1 + period_return) ^ (252 / 交易日報酬筆數) - 1
    annualized_std    = 日報酬標準差 × √252
    sharpe            = (年化報酬 - rf) / 年化波動
    mdd               = 期間內最大回檔（負值）
    """
    prices = prices.dropna()
    if len(prices) < 2:
        return {"days": len(prices)}

    rets   = prices.pct_change().dropna()
    n      = len(rets)
    period = prices.iloc[-1] / prices.iloc[0] - 1
    ann    = (1 + period) ** (TRADING_DAYS / n) - 1 if n > 0 else None
    std    = rets.std() * np.sqrt(TRADING_DAYS) if n > 1 else None
    sharpe = (ann - rf) / std if (ann is not None and std) else None
    mdd    = (prices / prices.cummax() - 1).min()

    return {
        "start_date":        prices.index[0].strftime("%Y-%m-%d"),
        "end_date":          prices.index[-1].strftime("%Y-%m-%d"),
        "start_price":       _r(prices.iloc[0], 2),
        "end_price":         _r(prices.iloc[-1], 2),
        "days":              n,
        "period_return":     _r(period),
        "annualized_return": _r(ann),
        "annualized_std":    _r(std),
        "sharpe":            _r(sharpe),
        "mdd":               _r(mdd),
    }


# ── 排序與取前 N 名 ──────────────────────────────
def rank_stocks(rows: List[Dict], sort_key: str = "period_return", top_n: int = 3) -> List[Dict]:
    """
    rows：[{"stock_id", "name", "metrics": {...}, "passed_filter": bool(可省略)}, ...]
    沒有通過篩選或缺排序值的股票排在最後，不給名次。
    回傳新 list，每筆加上 rank（int 或 None）與 selected（是否在前 N 名）。
    """
    if sort_key not in SORT_KEYS:
        raise ValueError(f"不支援的排序欄位：{sort_key}")
    higher_better = SORT_KEYS[sort_key][1]

    def eligible(r):
        return r.get("passed_filter", True) and r.get("metrics", {}).get(sort_key) is not None

    ranked = sorted(
        (dict(r) for r in rows if eligible(r)),
        key=lambda r: r["metrics"][sort_key],
        reverse=higher_better,
    )
    rest = [dict(r) for r in rows if not eligible(r)]

    for i, r in enumerate(ranked):
        r["rank"]     = i + 1
        r["selected"] = i < top_n
    for r in rest:
        r["rank"]     = None
        r["selected"] = False
    return ranked + rest


# ── 等權重組合（買入持有）────────────────────────
def equal_weight_portfolio(series: Dict[str, pd.Series]) -> pd.Series:
    """
    各股期初投入相同金額、期間不再平衡（對應論文等權重、固定成分股）。
    只取所有股票都有交易的日期。回傳起點 = 1 的組合淨值。
    """
    if not series:
        return pd.Series(dtype=float)
    df = pd.DataFrame(series).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    return (df / df.iloc[0]).mean(axis=1)


def to_normalized_points(s: pd.Series) -> List[Dict]:
    """轉成前端圖表格式，起點 = 100"""
    if s is None or s.empty:
        return []
    base = s.iloc[0]
    return [{"date": d.strftime("%Y-%m-%d"), "normalized": _r(v / base * 100, 2)}
            for d, v in s.items()]


# ── 財務指標篩選（論文 3.3.1）────────────────────
RULE_LABELS = {
    "not_financial":    "非金融股",
    "complete":         "財報年度完整",
    "roe_avg":          "ROE 平均",
    "eps_all_positive": "EPS 每年為正",
    "gross_margin_avg": "毛利率平均",
}


def financial_filter(fin: Optional[Dict], rules: Optional[Dict] = None) -> Dict:
    """
    fin：financials.get_fundamentals() 的結果
         {"years": [...], "roe": [...%], "eps": [...], "gross_margin": [...%], "is_financial": bool}
    rules：覆蓋 THESIS_RULES 的門檻；值設為 None / False 代表不檢查該條件
    回傳 {"passed", "checks": {規則: bool}, "reasons": [未通過原因], "values": {...}}
    fin 為 None（抓不到財報）時視為未通過。
    """
    rules = {**THESIS_RULES, **(rules or {})}
    if not fin:
        return {"passed": False, "checks": {}, "reasons": ["抓不到財報資料"], "values": {}}

    def avg(xs):
        xs = [x for x in (xs or []) if x is not None]
        return sum(xs) / len(xs) if xs else None

    roe, eps, gm = fin.get("roe") or [], fin.get("eps") or [], fin.get("gross_margin") or []
    roe_avg, gm_avg = avg(roe), avg(gm)
    eps_vals = [x for x in eps if x is not None]
    is_fin   = bool(fin.get("is_financial"))
    n_years  = len(fin.get("years") or [])

    checks, reasons = {}, []
    if rules.get("exclude_financials", True):
        checks["not_financial"] = not is_fin
        if is_fin:
            reasons.append("金融股（無毛利率，依論文設計排除）")

    # 論文要求「連續五年」，任何一年缺 ROE 或 EPS 就算資料不完整
    complete = n_years > 0 and all(x is not None for x in roe + eps)
    if not is_fin:
        complete = complete and all(x is not None for x in gm)
    checks["complete"] = complete
    if not complete and not is_fin:
        reasons.append(f"財報不足 {n_years} 年")

    if rules.get("roe_avg_min") is not None:
        ok = roe_avg is not None and roe_avg > rules["roe_avg_min"]
        checks["roe_avg"] = ok
        if not ok and roe_avg is not None:
            reasons.append(f"ROE 平均 {roe_avg:.1f}% ≤ {rules['roe_avg_min']:g}%")
    if rules.get("eps_all_positive"):
        ok = bool(eps_vals) and all(x > 0 for x in eps_vals)
        checks["eps_all_positive"] = ok
        if not ok and eps_vals:
            reasons.append("EPS 有虧損年度")
    if rules.get("gross_margin_avg_min") is not None and not is_fin:
        ok = gm_avg is not None and gm_avg > rules["gross_margin_avg_min"]
        checks["gross_margin_avg"] = ok
        if not ok and gm_avg is not None:
            reasons.append(f"毛利率平均 {gm_avg:.1f}% ≤ {rules['gross_margin_avg_min']:g}%")

    return {
        "passed":  all(checks.values()),
        "checks":  checks,
        "reasons": reasons,
        "values":  {"roe_avg": _r(roe_avg, 2), "gross_margin_avg": _r(gm_avg, 2),
                    "eps_min": _r(min(eps_vals), 2) if eps_vals else None},
    }
