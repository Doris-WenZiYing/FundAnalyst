"""
returns.py — 報酬率計算
"""

import numpy as np
import pandas as pd


def daily_returns(nav_series: pd.Series) -> pd.Series:
    """計算每日報酬率，去除第一筆 NaN"""
    return nav_series.pct_change().dropna()


def annualized_return(nav_series: pd.Series, periods_per_year: int = 252) -> float:
    """
    年化報酬率
    公式：(末值 / 初值) ^ (periods_per_year / n) - 1
    """
    if nav_series is None or len(nav_series) < 2:
        return None
    start = nav_series.iloc[0]
    end   = nav_series.iloc[-1]
    n     = len(nav_series)
    if start <= 0:
        return None
    return float((end / start) ** (periods_per_year / n) - 1)


def cumulative_return(nav_series: pd.Series) -> float:
    """累積報酬率：(末值 - 初值) / 初值"""
    if nav_series is None or len(nav_series) < 2:
        return None
    start = nav_series.iloc[0]
    if start == 0:
        return None
    return float((nav_series.iloc[-1] - start) / start)


def normalize_to_100(nav_series: pd.Series) -> pd.Series:
    """將 NAV 序列起點標準化為 100（供比較圖用）"""
    if nav_series is None or nav_series.empty:
        return nav_series
    base = nav_series.iloc[0]
    if base == 0:
        return nav_series
    return nav_series / base * 100