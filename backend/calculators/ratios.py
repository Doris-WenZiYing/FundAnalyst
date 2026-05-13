"""
ratios.py — Sharpe / Sortino / Calmar
"""


def sharpe_ratio(annualized_return: float, rf: float, annualized_std: float) -> float:
    """
    Sharpe Ratio = (Rp - Rf) / σp
    annualized_std == 0 時回傳 None（無法計算）
    """
    if annualized_return is None or annualized_std is None or annualized_std == 0:
        return None
    return (annualized_return - rf) / annualized_std


def sortino_ratio(annualized_return: float, rf: float, downside_std: float) -> float:
    """
    Sortino Ratio = (Rp - Rf) / σd
    只懲罰下行波動，比 Sharpe 更適合評估防禦型基金
    """
    if annualized_return is None or downside_std is None or downside_std == 0:
        return None
    return (annualized_return - rf) / downside_std


def calmar_ratio(annualized_return: float, mdd: float) -> float:
    """
    Calmar Ratio = 年化報酬率 / |MDD|
    同時衡量報酬與最大損失，數值越高越好
    """
    if annualized_return is None or mdd is None or mdd == 0:
        return None
    return annualized_return / abs(mdd)