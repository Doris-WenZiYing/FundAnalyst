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

# ── 財務篩選指標（論文表 1：盈餘能力、價值評估、財務穩健，加上成長性）──
# kind：avg = 五年平均；all_positive = 五年每年都 > 0；point = 研究開始日前一交易日的數值
# op  ：">" 越大越好（門檻為下限）、"<" 越小越好（門檻為上限）
# financial_na：金融股不適用（沒有毛利、營業利益、流動資產負債分類），篩選時自動忽略
# default：論文預設門檻；None = 預設不使用（留白）
INDICATORS = {
    "roe":              dict(label="ROE",        group="盈餘能力", kind="avg", op=">", unit="%", param="roe_min",  default=10.0),
    "roa":              dict(label="ROA",        group="盈餘能力", kind="avg", op=">", unit="%", param="roa_min",  default=None),
    "eps_positive":     dict(label="EPS 每年為正", group="盈餘能力", kind="all_positive", source="eps", param="eps_pos", default=True),
    "gross_margin":     dict(label="毛利率",      group="盈餘能力", kind="avg", op=">", unit="%", param="gm_min",   default=15.0, financial_na=True),
    "operating_margin": dict(label="營業利益率",   group="盈餘能力", kind="avg", op=">", unit="%", param="opm_min",  default=None, financial_na=True),
    "net_margin":       dict(label="稅後淨利率",   group="盈餘能力", kind="avg", op=">", unit="%", param="npm_min",  default=None),
    "debt_ratio":       dict(label="負債比率",     group="財務穩健", kind="avg", op="<", unit="%", param="debt_max", default=None, financial_na=True),
    "current_ratio":    dict(label="流動比率",     group="財務穩健", kind="avg", op=">", unit="%", param="cr_min",   default=None, financial_na=True),
    "revenue_growth":   dict(label="營收成長率",   group="成長性",   kind="avg", op=">", unit="%", param="revg_min", default=None),
    "eps_growth":       dict(label="EPS 成長率",  group="成長性",   kind="avg", op=">", unit="%", param="epsg_min", default=None, partial=True),
    "per":              dict(label="本益比",       group="價值評估", kind="point", op="<", unit="倍", param="per_max", default=None),
    "pbr":              dict(label="股價淨值比",   group="價值評估", kind="point", op="<", unit="倍", param="pbr_max", default=None),
    "dividend_yield":   dict(label="現金殖利率",   group="價值評估", kind="point", op=">", unit="%", param="dy_min",  default=None),
}

# 論文 3.3.1 的三個條件
THESIS_RULES = {k: v["default"] for k, v in INDICATORS.items()}


def indicator_catalog() -> List[Dict]:
    """給前端產生篩選欄位用"""
    return [{"key": k, **{f: v.get(f) for f in ("label", "group", "kind", "op", "unit", "param", "default")},
             "financial_na": bool(v.get("financial_na"))} for k, v in INDICATORS.items()]


def needs_valuation(rules: Dict) -> bool:
    return any(rules.get(k) is not None for k, v in INDICATORS.items() if v["kind"] == "point")


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


# ── 財務指標篩選 ─────────────────────────────────
def _fmt(v, unit):
    return f"{v:.1f}{unit}" if unit == "%" else f"{v:.2f} {unit}"


def financial_filter(fin: Optional[Dict], rules: Optional[Dict] = None,
                     valuation: Optional[Dict] = None) -> Dict:
    """
    fin       ：financials.get_fundamentals() 的結果（各指標五年數列）
    rules     ：{指標: 門檻}；None / False = 不使用（留白）。未給的指標用 THESIS_RULES
    valuation ：financials.get_valuation() 的結果（本益比等）
    回傳 {"passed", "checks": {指標: True/False/"skip"}, "reasons": [...], "values": {指標: 數值}}

    - 金融股遇到 financial_na 的指標自動忽略（checks 記為 "skip"）
    - 五年平均類指標，任一年缺資料視為未通過（論文要求連續五年）；EPS 成長率例外，
      前一年 EPS ≤ 0 的年度本來就無法計算，有算得出來的年度即可
    """
    rules  = {**THESIS_RULES, **(rules or {})}
    active = {k: t for k, t in rules.items() if k in INDICATORS and t is not None and t is not False}
    is_fin = bool(fin and fin.get("is_financial"))
    checks, reasons, values = {}, [], {}

    if not fin and any(INDICATORS[k]["kind"] != "point" for k in active):
        return {"passed": False, "checks": {}, "reasons": ["抓不到財報資料"], "values": {}}

    n_years = len((fin or {}).get("years") or []) or 5
    missing = []                                  # 財報不足的指標，最後合併成一句原因
    for key, threshold in active.items():
        ind = INDICATORS[key]
        if is_fin and ind.get("financial_na"):
            checks[key] = "skip"
            continue

        if ind["kind"] == "all_positive":
            xs = (fin or {}).get(ind["source"]) or []
            vals = [x for x in xs if x is not None]
            values[key] = _r(min(vals), 2) if vals else None
            if len(vals) < len(xs) or not vals:
                checks[key] = False
                missing.append(ind["label"].split(" ")[0])
            else:
                checks[key] = all(x > 0 for x in vals)
                if not checks[key]:
                    reasons.append("EPS 有虧損年度")
            continue

        if ind["kind"] == "point":
            v = (valuation or {}).get(key)
            values[key] = _r(v, 2)
            if v is None:
                checks[key] = False
                reasons.append(f"無{ind['label']}資料" + ("（虧損）" if key == "per" else ""))
                continue
        else:
            xs = (fin or {}).get(key) or []
            vals = [x for x in xs if x is not None]
            v = sum(vals) / len(vals) if vals else None
            values[key] = _r(v, 2)
            complete = bool(vals) if ind.get("partial") else (bool(xs) and len(vals) == len(xs))
            if not complete:
                checks[key] = False
                missing.append(ind["label"])
                continue

        ok = v > threshold if ind["op"] == ">" else v < threshold
        checks[key] = ok
        if not ok:
            sign = "≤" if ind["op"] == ">" else "≥"
            prefix = "" if ind["kind"] == "point" else "平均 "
            reasons.append(f"{ind['label']} {prefix}{_fmt(v, ind['unit'])} {sign} {_fmt(float(threshold), ind['unit'])}")

    if missing:
        reasons.insert(0, f"財報不足 {n_years} 年（{'、'.join(missing)}）")

    return {
        "passed":       all(c is True for c in checks.values() if c != "skip"),
        "checks":       checks,
        "skipped":      [INDICATORS[k]["label"] for k, c in checks.items() if c == "skip"],
        "reasons":      reasons,
        "values":       values,
        "is_financial": is_fin,
    }