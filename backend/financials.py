"""
financials.py — 從 FinMind 財報計算年度 ROE、EPS、毛利率

資料集（欄位名稱已用 2330、2881 實測確認）：
  TaiwanStockFinancialStatements（綜合損益表，季資料）
    Revenue、GrossProfit、EPS
    EquityAttributableToOwnersOfParent → 損益表裡代表「淨利歸屬於母公司業主」
    金融股沒有 GrossProfit，改有 NetInterestIncome 等欄位
  TaiwanStockBalanceSheet（資產負債表，季資料）
    EquityAttributableToOwnersOfParent（母公司業主權益），金融股可能只有 Equity

年度數字：
  損益表項目 = 四季加總（若 FinMind 回傳的是累計數，則取第四季），程式會自動判斷
  ROE        = 年度歸屬母公司淨利 / 平均權益（上年底與本年底平均；缺上年底就用本年底）× 100
  毛利率      = 年度毛利 / 年度營收 × 100（沒有 GrossProfit 欄位時，毛利 = 營收 − 營業成本 CostOfGoodsSold）
  EPS        = 四季 EPS 加總
"""

import logging
from collections import defaultdict
from statistics import median
from typing import Dict, List, Optional

from data_source import _fetch_with_retry, FINMIND_TOKEN
from scraper import cache

logger = logging.getLogger(__name__)

CACHE_HOURS = 24 * 7          # 財報一季才更新一次
QUARTER_END = {"03-31": 1, "06-30": 2, "09-30": 3, "12-31": 4}

NET_INCOME_KEYS = ("EquityAttributableToOwnersOfParent", "IncomeAfterTaxes", "IncomeAfterTax")
EQUITY_KEYS     = ("EquityAttributableToOwnersOfParent", "Equity")
FINANCIAL_HINTS = ("NetInterestIncome", "NetNonInterestIncome",
                   "NetChangeInProvisionsForInsuranceLiabilities", "BadDebts")


# ── 整理成 {type: {(year, q): value}} ──────────────
def _index(rows: List[Dict]) -> Dict[str, Dict[tuple, float]]:
    out = defaultdict(dict)
    for r in rows or []:
        d = str(r.get("date", ""))
        q = QUARTER_END.get(d[5:10])
        if not q or r.get("value") is None:
            continue
        try:
            out[r["type"]][(int(d[:4]), q)] = float(r["value"])
        except (KeyError, ValueError, TypeError):
            continue
    return out


def _is_cumulative(revenue: Dict[tuple, float]) -> bool:
    """判斷 FinMind 回傳的損益表是單季數還是年度累計數（用營收第四季 / 第一季的比值）"""
    ratios = []
    for y in {y for y, _ in revenue}:
        q1, q4 = revenue.get((y, 1)), revenue.get((y, 4))
        if q1 and q4 and q1 > 0:
            ratios.append(q4 / q1)
    return bool(ratios) and median(ratios) > 2.5


def _annual(series: Dict[tuple, float], year: int, cumulative: bool) -> Optional[float]:
    if cumulative:
        return series.get((year, 4))
    qs = [series.get((year, q)) for q in (1, 2, 3, 4)]
    return sum(qs) if all(v is not None for v in qs) else None


def _first(idx: Dict, keys) -> Dict[tuple, float]:
    for k in keys:
        if idx.get(k):
            return idx[k]
    return {}


def compute_annual(fs_rows: List[Dict], bs_rows: List[Dict], years: List[int]) -> Dict:
    """純計算，不連網，方便測試。years 例如 [2021, 2022, 2023, 2024, 2025]"""
    fs, bs = _index(fs_rows), _index(bs_rows)

    is_financial = "GrossProfit" not in fs and any(k in fs for k in FINANCIAL_HINTS)
    revenue      = fs.get("Revenue", {})
    cumulative   = _is_cumulative(revenue)
    net_income   = _first(fs, NET_INCOME_KEYS)
    equity       = _first(bs, EQUITY_KEYS)

    # 有些公司（例如和泰車）FinMind 沒有 GrossProfit 欄位，改用「營收 − 營業成本」計算
    gross_profit = fs.get("GrossProfit") or {}
    if not gross_profit and not is_financial and fs.get("CostOfGoodsSold"):
        cogs = fs["CostOfGoodsSold"]
        gross_profit = {k: revenue[k] - cogs[k] for k in revenue if k in cogs}

    roe, eps, gm = [], [], []
    for y in years:
        ni   = _annual(net_income, y, cumulative)
        e1   = equity.get((y, 4))
        e0   = equity.get((y - 1, 4))
        base = (e0 + e1) / 2 if (e0 and e1) else e1
        roe.append(round(ni / base * 100, 2) if (ni is not None and base) else None)

        e = _annual(fs.get("EPS", {}), y, cumulative)
        eps.append(round(e, 2) if e is not None else None)

        rev = _annual(revenue, y, cumulative)
        gp  = _annual(gross_profit, y, cumulative)
        gm.append(round(gp / rev * 100, 2) if (gp is not None and rev) else None)

    return {
        "years":        years,
        "roe":          roe,
        "eps":          eps,
        "gross_margin": gm,
        "is_financial": is_financial,
        "cumulative":   cumulative,
        "gross_profit_derived": "GrossProfit" not in fs and bool(gross_profit),
    }


# ── 連網取得（含快取）──────────────────────────────
def _fetch(dataset: str, stock_id: str, start: str, end: str) -> List[Dict]:
    body = _fetch_with_retry({
        "dataset": dataset, "data_id": stock_id,
        "start_date": start, "end_date": end, "token": FINMIND_TOKEN,
    })
    return body.get("data", []) if isinstance(body, dict) else []


def get_fundamentals(stock_id: str, end_year: int, n_years: int = 5) -> Optional[Dict]:
    """取得 end_year 往前 n_years 個年度的 ROE / EPS / 毛利率；抓不到回 None"""
    key = f"fin_v2_{stock_id}_{end_year}_{n_years}"
    hit = cache.get(key, max_age_hours=CACHE_HOURS)
    if hit:
        return hit

    years = list(range(end_year - n_years + 1, end_year + 1))
    start = f"{years[0] - 1}-01-01"           # 多抓一年，算第一年的平均權益
    end   = f"{end_year}-12-31"
    try:
        fs = _fetch("TaiwanStockFinancialStatements", stock_id, start, end)
        bs = _fetch("TaiwanStockBalanceSheet",        stock_id, start, end)
    except Exception as e:
        logger.warning(f"{stock_id} 財報失敗：{e}")
        return None
    if not fs:
        return None

    result = compute_annual(fs, bs, years)
    cache.set(key, result)
    return result
