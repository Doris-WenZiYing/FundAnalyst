"""
risk.py — 風險指標計算
"""

import numpy as np
import pandas as pd


def annualized_std(daily_returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    年化標準差（波動率）
    公式：日標準差 × √252
    """
    if daily_returns is None or len(daily_returns) < 2:
        return None
    return float(daily_returns.std() * np.sqrt(periods_per_year))


def downside_std(daily_returns: pd.Series, rf_daily: float = 0.0, periods_per_year: int = 252) -> float:
    """
    下行標準差：只計算低於無風險利率的部分，用於 Sortino 分母
    若沒有任何負報酬日，回傳極小值避免除以 0
    """
    if daily_returns is None or daily_returns.empty:
        return 1e-10
    downside = daily_returns[daily_returns < rf_daily]
    if downside.empty or len(downside) < 2:
        return 1e-10
    return float(downside.std() * np.sqrt(periods_per_year))


def max_drawdown(nav_series: pd.Series) -> float:
    """
    最大回檔（MDD）
    公式：min((谷底 - 前高) / 前高)
    回傳負值，e.g. -0.123 代表 -12.3%
    """
    if nav_series is None or len(nav_series) < 2:
        return None
    rolling_max = nav_series.cummax()
    drawdown    = (nav_series - rolling_max) / rolling_max
    return float(drawdown.min())


def drawdown_series(nav_series: pd.Series) -> pd.Series:
    """
    完整回檔序列（供 Area Chart 視覺化用）
    每個時間點相對前高的跌幅
    """
    if nav_series is None or nav_series.empty:
        return pd.Series(dtype=float)
    rolling_max = nav_series.cummax()
    return (nav_series - rolling_max) / rolling_max