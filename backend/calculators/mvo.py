"""
mvo.py — 均值變異數最佳化（Mean-Variance Optimization）
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from typing import Dict, List, Tuple

RF = 0.015


def _align_returns(nav_dict: Dict[str, pd.Series]) -> pd.DataFrame:
    ret = {fid: nav.pct_change().dropna() for fid, nav in nav_dict.items()}
    return pd.DataFrame(ret).dropna()


def _ann_metrics(w, mu, cov, rf=RF):
    r = float(np.dot(w, mu) * 252)
    v = float(np.sqrt(np.dot(w.T, np.dot(cov * 252, w))))
    s = (r - rf) / v if v > 0 else 0.0
    return r, v, s


def _base(n):
    return (
        tuple((0.0, 1.0) for _ in range(n)),
        {'type': 'eq', 'fun': lambda x: x.sum() - 1},
        np.full(n, 1 / n),
    )


def max_sharpe(nav_dict: Dict[str, pd.Series], rf: float = RF) -> Dict:
    """最大 Sharpe Ratio 投資組合"""
    df = _align_returns(nav_dict)
    if df.empty or len(df) < 30:
        return {"error": "資料不足（需至少 30 個交易日）"}

    fids = list(df.columns)
    n    = len(fids)
    mu   = df.mean().values
    cov  = df.cov().values
    bounds, cons, x0 = _base(n)

    res = minimize(lambda w: -_ann_metrics(w, mu, cov, rf)[2],
                   x0, method='SLSQP', bounds=bounds, constraints=cons,
                   options={'maxiter': 1000, 'ftol': 1e-9})

    if not res.success:
        return {"error": f"最佳化未收斂：{res.message}"}

    r, v, s = _ann_metrics(res.x, mu, cov, rf)
    return {
        "weights":         {fid: round(float(w), 4) for fid, w in zip(fids, res.x)},
        "expected_return": round(r, 4),
        "volatility":      round(v, 4),
        "sharpe":          round(s, 4),
    }


def min_volatility(nav_dict: Dict[str, pd.Series]) -> Dict:
    """最小波動率投資組合"""
    df = _align_returns(nav_dict)
    if df.empty or len(df) < 30:
        return {"error": "資料不足（需至少 30 個交易日）"}

    fids = list(df.columns)
    n    = len(fids)
    mu   = df.mean().values
    cov  = df.cov().values
    bounds, cons, x0 = _base(n)

    res = minimize(lambda w: float(np.sqrt(np.dot(w.T, np.dot(cov * 252, w)))),
                   x0, method='SLSQP', bounds=bounds, constraints=cons,
                   options={'maxiter': 1000})

    if not res.success:
        return {"error": f"最佳化未收斂：{res.message}"}

    r, v, s = _ann_metrics(res.x, mu, cov)
    return {
        "weights":         {fid: round(float(w), 4) for fid, w in zip(fids, res.x)},
        "expected_return": round(r, 4),
        "volatility":      round(v, 4),
        "sharpe":          round(s, 4),
    }


def efficient_frontier(nav_dict: Dict[str, pd.Series], n_points: int = 25) -> List[Dict]:
    """效率前緣曲線（供前端散點圖）"""
    df = _align_returns(nav_dict)
    if df.empty or len(df) < 30:
        return []

    fids    = list(df.columns)
    n       = len(fids)
    mu      = df.mean().values
    cov     = df.cov().values
    bounds  = tuple((0.0, 1.0) for _ in range(n))
    x0      = np.full(n, 1 / n)
    targets = np.linspace(float(np.min(mu) * 252) * 0.9,
                          float(np.max(mu) * 252) * 1.1, n_points)

    frontier = []
    for t in targets:
        cons = [
            {'type': 'eq', 'fun': lambda x: x.sum() - 1},
            {'type': 'eq', 'fun': lambda x, t=t: np.dot(x, mu) * 252 - t},
        ]
        res = minimize(
            lambda w: float(np.sqrt(np.dot(w.T, np.dot(cov * 252, w)))),
            x0, method='SLSQP', bounds=bounds, constraints=cons,
            options={'maxiter': 500}
        )
        if res.success:
            r, v, s = _ann_metrics(res.x, mu, cov)
            frontier.append({"return": round(r, 4), "volatility": round(v, 4), "sharpe": round(s, 4)})

    return frontier


def equal_weight_metrics(nav_dict: Dict[str, pd.Series], rf: float = RF) -> Dict:
    """等權重配置指標（回測基準）"""
    df = _align_returns(nav_dict)
    if df.empty:
        return {}
    fids = list(df.columns)
    n    = len(fids)
    w    = np.full(n, 1 / n)
    r, v, s = _ann_metrics(w, df.mean().values, df.cov().values, rf)
    return {
        "weights":         {fid: round(1 / n, 4) for fid in fids},
        "expected_return": round(r, 4),
        "volatility":      round(v, 4),
        "sharpe":          round(s, 4),
    }
