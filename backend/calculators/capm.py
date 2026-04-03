"""
capm.py — Alpha / Beta（CAPM）
"""

import numpy as np
import pandas as pd


def beta(fund_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    """
    Beta (β) = Cov(Rp, Rm) / Var(Rm)

    參數：
      fund_returns:      基金日報酬率序列
      benchmark_returns: 基準指數日報酬率序列（需對齊日期）

    TODO:
      1. 對齊兩序列的日期（inner join on index）
      2. 計算 Cov(fund, benchmark)
      3. 計算 Var(benchmark)
      4. 回傳 cov / var
      5. 若資料不足（< 30 筆），回傳 None
    """
    # TODO: 實作
    pass


def alpha(annualized_return: float, rf: float, beta_val: float, benchmark_return: float) -> float:
    """
    Alpha (α) = Rp - [Rf + β × (Rm - Rf)]

    參數：
      annualized_return: 基金年化報酬率
      rf:                無風險利率（年化）
      beta_val:          已計算的 Beta 值
      benchmark_return:  基準指數年化報酬率

    TODO:
      - 計算 CAPM 預期報酬：rf + beta_val * (benchmark_return - rf)
      - Alpha = annualized_return - 預期報酬
      - 回傳浮點數（e.g. 0.021 代表 +2.1%）
    """
    # TODO: 實作
    pass


def align_series(s1: pd.Series, s2: pd.Series):
    """
    對齊兩個時間序列（取交集日期）

    TODO:
      - 用 pd.concat + dropna 或 inner join 對齊
      - 回傳 (aligned_s1, aligned_s2)
    """
    # TODO: 實作
    pass
