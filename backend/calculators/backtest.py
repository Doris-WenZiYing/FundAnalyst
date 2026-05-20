"""
backtest.py — 回測引擎
比較「MVO 最佳化配置」vs「等權重配置」歷史績效
驗證 MVO 在 MDD 控制上的優勢（計畫書 D 模組）
"""

import numpy as np
import pandas as pd
from typing import Dict
from calculators.returns import annualized_return, normalize_to_100
from calculators.risk    import max_drawdown, annualized_std, drawdown_series


def _build_nav(nav_dict: Dict[str, pd.Series], weights: Dict[str, float]) -> pd.Series:
    """建立等比例買入持有的投資組合淨值序列"""
    df = pd.DataFrame(nav_dict).dropna()
    if df.empty:
        return pd.Series(dtype=float)
    normalized = df / df.iloc[0]
    w = pd.Series({fid: weights.get(fid, 0.0) for fid in df.columns})
    return (normalized * w).sum(axis=1)


def _metrics(nav: pd.Series, rf: float = 0.015) -> Dict:
    if nav.empty or len(nav) < 10:
        return {}
    ret     = nav.pct_change().dropna()
    ann_ret = annualized_return(nav)
    std     = annualized_std(ret)
    mdd     = max_drawdown(nav)
    dd_ser  = drawdown_series(nav)
    sharpe  = (ann_ret - rf) / std if std and std > 0 else None
    nav_100 = normalize_to_100(nav)

    def _r(v): return round(float(v), 4) if v is not None else None

    return {
        "nav_series": [
            {"date": str(d.date()), "value": _r(v)}
            for d, v in nav_100.items()
        ],
        "drawdown_series": [
            {"date": str(d.date()), "value": _r(v)}
            for d, v in dd_ser.items()
        ],
        "annualized_return": _r(ann_ret),
        "volatility":        _r(std),
        "mdd":               _r(mdd),
        "sharpe":            _r(sharpe),
    }


def run_backtest(nav_dict: Dict[str, pd.Series],
                 mvo_weights: Dict[str, float],
                 rf: float = 0.015) -> Dict:
    """
    回測 MVO 配置 vs 等權重配置。

    Parameters
    ----------
    nav_dict    : {fund_id: pd.Series}
    mvo_weights : {fund_id: float}

    Returns
    -------
    {"mvo": {...}, "equal": {...}, "verdict": str}
    """
    n             = len(nav_dict)
    equal_weights = {fid: 1 / n for fid in nav_dict}

    mvo_m   = _metrics(_build_nav(nav_dict, mvo_weights),   rf)
    equal_m = _metrics(_build_nav(nav_dict, equal_weights), rf)

    return {"mvo": mvo_m, "equal": equal_m, "verdict": _verdict(mvo_m, equal_m)}


def _verdict(mvo: Dict, equal: Dict) -> str:
    parts = []

    m_mdd, e_mdd = mvo.get("mdd"), equal.get("mdd")
    if m_mdd is not None and e_mdd is not None:
        diff = abs(e_mdd) - abs(m_mdd)
        if diff > 0.005:
            parts.append(f"MVO 最大回檔 {m_mdd*100:.1f}%，優於等權重 {e_mdd*100:.1f}%，降低 {diff*100:.1f}%")
        elif diff < -0.005:
            parts.append(f"等權重最大回檔 {e_mdd*100:.1f}%，MVO 為 {m_mdd*100:.1f}%")
        else:
            parts.append(f"兩者最大回檔相近（MVO {m_mdd*100:.1f}% vs 等權重 {e_mdd*100:.1f}%）")

    m_s, e_s = mvo.get("sharpe"), equal.get("sharpe")
    if m_s is not None and e_s is not None:
        if m_s > e_s + 0.05:
            parts.append(f"MVO Sharpe {m_s:.2f} 優於等權重 {e_s:.2f}")
        elif m_s < e_s - 0.05:
            parts.append(f"等權重 Sharpe {e_s:.2f} 優於 MVO {m_s:.2f}")

    m_r, e_r = mvo.get("annualized_return"), equal.get("annualized_return")
    if m_r is not None and e_r is not None:
        parts.append(f"年化報酬 MVO {m_r*100:.1f}% vs 等權重 {e_r*100:.1f}%")

    return "｜".join(parts) if parts else "回測完成，請查看上方圖表"
