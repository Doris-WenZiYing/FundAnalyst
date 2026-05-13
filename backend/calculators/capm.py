"""
capm.py — Alpha / Beta（CAPM）
"""

import numpy as np
import pandas as pd


def align_series(s1: pd.Series, s2: pd.Series):
    """
    對齊兩個時間序列（取日期交集，去除任一方的 NaN）
    回傳 (aligned_s1, aligned_s2)
    """
    combined = pd.concat([s1, s2], axis=1).dropna()
    return combined.iloc[:, 0], combined.iloc[:, 1]


def beta(fund_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Beta (β) = Cov(Rp, Rm) / Var(Rm)
    資料不足 30 筆時回傳 None（統計上不可靠）
    """
    if fund_returns is None or benchmark_returns is None:
        return None
    if fund_returns.empty or benchmark_returns.empty:
        return None

    f, b = align_series(fund_returns, benchmark_returns)

    if len(f) < 30:
        return None

    var_b = float(np.var(b, ddof=1))
    if var_b == 0:
        return None

    cov_matrix = np.cov(f, b, ddof=1)   # 2×2 covariance matrix
    cov_fb     = cov_matrix[0][1]

    return float(cov_fb / var_b)


def alpha(annualized_return: float, rf: float, beta_val: float, benchmark_return: float) -> float:
    """
    Alpha (α) = Rp - [Rf + β × (Rm - Rf)]
    > 0：基金經理人創造了超過市場風險補償的額外報酬
    """
    if annualized_return is None or beta_val is None or benchmark_return is None:
        return None
    expected = rf + beta_val * (benchmark_return - rf)
    return float(annualized_return - expected)