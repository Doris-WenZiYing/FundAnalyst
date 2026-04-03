"""
returns.py — 報酬率計算
"""

import numpy as np
import pandas as pd


def daily_returns(nav_series: pd.Series) -> pd.Series:
    """
    計算每日報酬率
    nav_series: 以日期為 index 的淨值 Series

    TODO:
      - 用 .pct_change() 計算日報酬率
      - 處理 NaN（首日無報酬率）
    """
    # TODO: 實作
    pass


def annualized_return(nav_series: pd.Series, periods_per_year: int = 252) -> float:
    """
    計算年化報酬率
    公式：(末值 / 初值) ^ (periods_per_year / n) - 1

    TODO:
      - 取 nav_series 的首尾值
      - 計算持有天數 n
      - 回傳年化報酬率（浮點數，e.g. 0.087 代表 8.7%）
    """
    # TODO: 實作
    pass


def cumulative_return(nav_series: pd.Series) -> float:
    """
    計算累積報酬率
    公式：(末值 - 初值) / 初值

    TODO: 實作
    """
    # TODO: 實作
    pass


def normalize_to_100(nav_series: pd.Series) -> pd.Series:
    """
    將 NAV 序列起點標準化為 100（供比較圖用）

    TODO:
      - 用 nav_series / nav_series.iloc[0] * 100
    """
    # TODO: 實作
    pass
