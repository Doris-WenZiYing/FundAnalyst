"""
risk.py — 風險指標計算
"""

import numpy as np
import pandas as pd


def annualized_std(daily_returns: pd.Series, periods_per_year: int = 252) -> float:
    """
    計算年化標準差（波動率）
    公式：日標準差 × √252

    TODO:
      - 計算 daily_returns 的標準差
      - 乘以 sqrt(periods_per_year)
      - 回傳浮點數（e.g. 0.124 代表 12.4%）
    """
    # TODO: 實作
    pass


def downside_std(daily_returns: pd.Series, rf_daily: float = 0.0, periods_per_year: int = 252) -> float:
    """
    計算下行標準差（只計算低於無風險利率的部分）
    用於 Sortino Ratio 分母

    TODO:
      - 篩選 daily_returns < rf_daily 的部分
      - 計算這部分的標準差
      - 年化（× √252）
      - 若沒有負報酬日，回傳極小值避免除以 0
    """
    # TODO: 實作
    pass


def max_drawdown(nav_series: pd.Series) -> float:
    """
    計算最大回檔（MDD）
    公式：min((谷底 - 前高) / 前高)

    TODO:
      - 計算滾動最高點：nav_series.cummax()
      - 計算每日回檔：(nav - 前高) / 前高
      - 取最小值即為 MDD
      - 回傳負值（e.g. -0.123 代表 -12.3%）
    """
    # TODO: 實作
    pass


def drawdown_series(nav_series: pd.Series) -> pd.Series:
    """
    回傳完整的回檔序列（供 Area Chart 視覺化用）

    TODO:
      - 同 max_drawdown 邏輯，但回傳整條序列而不是最小值
    """
    # TODO: 實作
    pass
