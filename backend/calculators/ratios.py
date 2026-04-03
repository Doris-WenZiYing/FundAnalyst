"""
ratios.py — Sharpe / Sortino / Calmar
"""


def sharpe_ratio(annualized_return: float, rf: float, annualized_std: float) -> float:
    """
    Sharpe Ratio = (Rp - Rf) / σp

    參數：
      annualized_return: 基金年化報酬率
      rf:                無風險利率（年化，e.g. 0.015）
      annualized_std:    年化標準差

    TODO:
      - 計算 (annualized_return - rf) / annualized_std
      - 若 annualized_std == 0，回傳 None 或 0
    """
    # TODO: 實作
    pass


def sortino_ratio(annualized_return: float, rf: float, downside_std: float) -> float:
    """
    Sortino Ratio = (Rp - Rf) / σd

    參數：
      downside_std: 下行標準差（見 risk.py）

    TODO:
      - 計算 (annualized_return - rf) / downside_std
      - 若 downside_std == 0，回傳 None
    """
    # TODO: 實作
    pass


def calmar_ratio(annualized_return: float, mdd: float) -> float:
    """
    Calmar Ratio = 年化報酬率 / |MDD|

    參數：
      mdd: 最大回檔（負值，e.g. -0.123）

    TODO:
      - 計算 annualized_return / abs(mdd)
      - 若 mdd == 0，回傳 None
    """
    # TODO: 實作
    pass
