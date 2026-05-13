"""
scoring.py — 多準則評選模型

三個面向：
  - 報酬面 (return)   : 年化報酬、Alpha
  - 風險面 (risk)     : MDD、Beta、年化波動率
  - 穩定面 (stability): Sharpe、Sortino、Calmar

每個指標可自訂權重，三個面向也可自訂權重。
最終輸出每檔 ETF 的三面向分數 + 總分（0–100），依總分排名。
"""

import numpy as np
from typing import Dict, List, Optional


# ── 指標正規化設定 ────────────────────────────────
# (direction, ref_min, ref_max)
# direction =  1 → 越大越好
# direction = -1 → 越小越好
METRIC_CONFIG = {
    "annualized_return": ( 1, -0.10,  0.25),  # -10% ~ +25%
    "alpha":             ( 1, -0.05,  0.10),  # -5%  ~ +10%
    "mdd":               (-1, -0.50,  0.00),  # -50% ~  0%（越接近 0 越好）
    "beta":              (-1,  0.00,  2.00),  #   0  ~  2（越低越穩）
    "annualized_std":    (-1,  0.00,  0.40),  #  0%  ~ 40%（越低越穩）
    "sharpe":            ( 1, -1.00,  3.00),  #  -1  ~  3
    "sortino":           ( 1, -1.00,  3.00),
    "calmar":            ( 1,  0.00,  2.00),  #   0  ~  2
}

# 面向 → 所屬指標
DIMENSIONS = {
    "return":    ["annualized_return", "alpha"],
    "risk":      ["mdd", "beta", "annualized_std"],
    "stability": ["sharpe", "sortino", "calmar"],
}

# 預設權重
DEFAULT_WEIGHTS = {
    "return": {
        "dimension_weight": 0.33,
        "metrics": {"annualized_return": 0.6, "alpha": 0.4},
    },
    "risk": {
        "dimension_weight": 0.34,
        "metrics": {"mdd": 0.4, "beta": 0.3, "annualized_std": 0.3},
    },
    "stability": {
        "dimension_weight": 0.33,
        "metrics": {"sharpe": 0.4, "sortino": 0.35, "calmar": 0.25},
    },
}


def _normalize(key: str, value: Optional[float]) -> float:
    """
    將指標值用固定參考範圍轉換為 0–100 分。
    超出範圍的值會被 clip 到 0 或 100。
    None / NaN 給 0 分（保守處理）。
    """
    if value is None:
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if np.isnan(v) or np.isinf(v):
        return 0.0

    direction, ref_min, ref_max = METRIC_CONFIG[key]
    span = ref_max - ref_min
    if span == 0:
        return 50.0

    if direction == 1:
        score = (v - ref_min) / span
    else:
        score = (ref_max - v) / span

    return float(np.clip(score * 100, 0.0, 100.0))


def _dimension_score(metrics: dict, dim_key: str, metric_weights: dict) -> float:
    """
    計算單一面向分數（0–100）。
    metric_weights 不需要事先正規化，函式內部會處理。
    """
    keys = DIMENSIONS[dim_key]
    total_w = 0.0
    weighted = 0.0

    for k in keys:
        w = float(metric_weights.get(k, 1.0 / len(keys)))
        s = _normalize(k, metrics.get(k))
        weighted += w * s
        total_w  += w

    if total_w == 0:
        return 0.0
    return round(weighted / total_w, 2)


def compute_scores(
    funds_metrics: List[Dict],
    weights: Optional[Dict] = None,
) -> List[Dict]:
    """
    計算所有 ETF 的多準則評分並排名。

    Parameters
    ----------
    funds_metrics : list of dict
        格式：[{"fund_id": str, "name": str, "metrics": dict}, ...]

    weights : dict（可選）
        格式：
        {
          "return":    {"dimension_weight": float, "metrics": {key: float, ...}},
          "risk":      {"dimension_weight": float, "metrics": {key: float, ...}},
          "stability": {"dimension_weight": float, "metrics": {key: float, ...}},
        }
        若未提供，使用 DEFAULT_WEIGHTS。

    Returns
    -------
    list of dict，依 total_score 由高到低排序，並附上 rank。
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    results = []

    for fund in funds_metrics:
        m = fund.get("metrics", {})

        # 各面向分數
        scores = {}
        for dim_key in DIMENSIONS:
            dim_cfg = weights.get(dim_key, {})
            metric_w = dim_cfg.get("metrics", {})
            scores[f"{dim_key}_score"] = _dimension_score(m, dim_key, metric_w)

        # 總分（面向加權平均）
        total_w = 0.0
        total   = 0.0
        for dim_key in DIMENSIONS:
            w = float(weights.get(dim_key, {}).get("dimension_weight", 1.0 / 3))
            total   += w * scores[f"{dim_key}_score"]
            total_w += w

        total_score = round(total / total_w, 1) if total_w > 0 else 0.0

        results.append({
            "fund_id":         fund["fund_id"],
            "name":            fund["name"],
            "total_score":     total_score,
            "return_score":    scores["return_score"],
            "risk_score":      scores["risk_score"],
            "stability_score": scores["stability_score"],
            "metrics":         m,
        })

    # 排名
    results.sort(key=lambda x: x["total_score"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    return results