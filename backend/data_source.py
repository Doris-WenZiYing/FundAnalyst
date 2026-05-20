"""
data_source.py — 資料來源層

資料來源整合：
  MoneyDJ 爬蟲  → 基金清單（名稱、公司）
  fund_mapper   → MoneyDJ代號 ↔ FinMind股票代號
  scraper.sitca → RR 評級（規則式，依投信投顧公會分類標準）
  FinMind API   → 歷史收盤價（分頁自動拼接 + 前向補值）
"""

import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
FINMIND_BASE  = "https://api.finmindtrade.com/api/v4/data"
BENCHMARK_ID  = "0050"
PERIOD_DAYS   = {"1Y": 365, "3Y": 1095, "5Y": 1825}

_moneydj_fund_list = None

# ── 備用 ETF 清單 ────────────────────────────────
_ETF_FALLBACK = [
    {"fund_id": "0050",   "name": "元大台灣50",       "company": "元大投信", "type": "股票型"},
    {"fund_id": "0056",   "name": "元大高股息",       "company": "元大投信", "type": "股票型"},
    {"fund_id": "00878",  "name": "國泰永續高股息",   "company": "國泰投信", "type": "股票型"},
    {"fund_id": "00881",  "name": "國泰台灣5G+",      "company": "國泰投信", "type": "股票型"},
    {"fund_id": "006208", "name": "富邦台灣50",       "company": "富邦投信", "type": "股票型"},
    {"fund_id": "00692",  "name": "富邦公司治理",     "company": "富邦投信", "type": "股票型"},
    {"fund_id": "00646",  "name": "元大S&P500",      "company": "元大投信", "type": "海外股票型"},
    {"fund_id": "00679B", "name": "元大美債20年",     "company": "元大投信", "type": "債券型"},
    {"fund_id": "00720B", "name": "元大投資級公司債", "company": "元大投信", "type": "債券型"},
    {"fund_id": "00713",  "name": "元大台灣高息低波", "company": "元大投信", "type": "股票型"},
    {"fund_id": "00733",  "name": "富邦台灣中小",     "company": "富邦投信", "type": "股票型"},
    {"fund_id": "00663",  "name": "國泰臺韓科技",     "company": "國泰投信", "type": "股票型"},
]


# ── MoneyDJ 清單（懶載入）────────────────────────
def _get_moneydj_list() -> list:
    global _moneydj_fund_list
    if _moneydj_fund_list is not None:
        return _moneydj_fund_list
    try:
        from scraper.moneydj import scrape_fund_list
        _moneydj_fund_list = scrape_fund_list(use_cache=True)
        logger.info(f"MoneyDJ 載入 {len(_moneydj_fund_list)} 檔")
    except Exception as e:
        logger.warning(f"MoneyDJ 失敗，用備用清單：{e}")
        _moneydj_fund_list = []
    return _moneydj_fund_list


# ── fund_id 轉 FinMind 代號 ──────────────────────
def _to_stock_id(fund_id: str) -> str:
    if fund_id.replace("B", "").isdigit():
        return fund_id
    try:
        from fund_mapper import get_stock_id
        sid = get_stock_id(fund_id)
        if sid:
            return sid
    except Exception:
        pass
    return fund_id


# ── FinMind 重試 ─────────────────────────────────
def _fetch_with_retry(params: dict, max_retries: int = 3, backoff: float = 2.0) -> dict:
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(FINMIND_BASE, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(backoff ** (attempt + 2))
                continue
            resp.raise_for_status()
            body = resp.json()
            if isinstance(body, dict) and "detail" in body:
                raise RuntimeError(f"FinMind 錯誤：{body['detail']}")
            return body
        except requests.exceptions.Timeout:
            last_error = "逾時"
        except requests.exceptions.ConnectionError:
            last_error = "連線失敗"
        except RuntimeError:
            raise
        except Exception as e:
            last_error = str(e)
        if attempt < max_retries:
            time.sleep(backoff ** attempt)
    raise RuntimeError(f"FinMind 失敗（重試 {max_retries} 次）：{last_error}")


# ── 分頁自動拼接（>1000 筆）──────────────────────
def _fetch_paginated(stock_id: str, start_date: str, end_date: str = None) -> pd.DataFrame:
    if not end_date:
        end_date = datetime.today().strftime("%Y-%m-%d")

    all_data      = []
    current_start = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt        = datetime.strptime(end_date,   "%Y-%m-%d")
    chunk_days    = 900

    while current_start <= end_dt:
        chunk_end = min(current_start + timedelta(days=chunk_days), end_dt)
        params = {
            "dataset":    "TaiwanStockPrice",
            "data_id":    stock_id,
            "start_date": current_start.strftime("%Y-%m-%d"),
            "end_date":   chunk_end.strftime("%Y-%m-%d"),
            "token":      FINMIND_TOKEN,
        }
        try:
            body  = _fetch_with_retry(params)
            chunk = body.get("data", []) if isinstance(body, dict) else []
            all_data.extend(chunk)
        except Exception as e:
            logger.warning(f"{stock_id} 分頁失敗 {current_start.date()}：{e}")

        current_start = chunk_end + timedelta(days=1)
        time.sleep(0.3)

    if not all_data:
        return pd.DataFrame()

    df = pd.DataFrame(all_data)
    df["date"] = pd.to_datetime(df["date"])
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


# ── 時序補值 ─────────────────────────────────────
def _fill_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    idx = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(idx).ffill().dropna()


def _start_date(period: str) -> str:
    days = PERIOD_DAYS.get(period, 1095)
    return (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── 公開介面 ─────────────────────────────────────
def get_fund_list() -> pd.DataFrame:
    """
    回傳基金清單（fund_id 為 FinMind 股票代號）。
    若 MoneyDJ + fund_mapper 有資料，優先使用；否則用備用 ETF 清單。
    自動附加 RR 評級（依投信投顧公會規則分類）。
    """
    from scraper.sitca import classify_rr

    moneydj = _get_moneydj_list()

    if moneydj:
        try:
            from fund_mapper import load_mapping
            mapping = load_mapping()
        except Exception:
            mapping = {}

        rows = []
        for f in moneydj:
            fc       = f.get("fund_code", "")
            stock_id = mapping.get(fc)
            if not stock_id:
                continue
            name = f.get("name", "")
            rows.append({
                "fund_id":   stock_id,
                "fund_code": fc,
                "name":      name,
                "company":   f.get("company", ""),
                "type":      f.get("type", "ETF"),
                "rr_rating": classify_rr(stock_id, name),
            })

        if rows:
            return pd.DataFrame(rows).drop_duplicates("fund_id")

    # 備用清單也加 RR
    fallback = []
    for f in _ETF_FALLBACK:
        fallback.append({
            **f,
            "rr_rating": classify_rr(f["fund_id"], f["name"]),
        })
    return pd.DataFrame(fallback)


def get_fund_info(fund_id: str):
    """取得單一基金資訊，含 RR 評級"""
    from scraper.sitca import classify_rr, rr_label

    funds = get_fund_list()
    row   = funds[funds["fund_id"] == fund_id]
    if row.empty:
        return None

    info = row.iloc[0].to_dict()

    # 確保 rr_rating 存在
    rr = info.get("rr_rating") or classify_rr(fund_id, info.get("name", ""))
    info["rr_rating"]    = rr
    info["rr_label"]     = rr_label(rr)

    # 基金規模（從 FinMind TaiwanStockMarketValue）
    info["aum"] = _get_etf_aum(fund_id)

    # MoneyDJ 詳細資訊（不再需要 aum/expense_ratio，已移除）
    for k in ["region", "manager"]:
        info.setdefault(k, None)

    # 最新收盤價
    try:
        s = get_nav_series(fund_id, "1Y")
        info["nav"]      = float(s.iloc[-1])       if not s.empty else None
        info["nav_date"] = str(s.index[-1].date()) if not s.empty else None
    except Exception:
        info["nav"] = info["nav_date"] = None

    return info


def get_nav_series(fund_id: str, period: str) -> pd.Series:
    """取得歷史收盤價 Series（自動分頁 + 補值）"""
    stock_id = _to_stock_id(fund_id)
    df = _fetch_paginated(stock_id, _start_date(period))
    if df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    return _fill_series(df.set_index("date")["close"].astype(float))


def get_benchmark_series(period: str) -> pd.Series:
    """取得 0050 基準指數（自動分頁 + 補值）"""
    df = _fetch_paginated(BENCHMARK_ID, _start_date(period))
    if df.empty or "close" not in df.columns:
        return pd.Series(dtype=float)
    return _fill_series(df.set_index("date")["close"].astype(float))


# ── ETF 基金規模（市值）────────────────────────
def _get_etf_aum(stock_id: str):
    """
    從 FinMind TaiwanStockMarketValue 取得 ETF 市值（約等於 AUM）
    回傳單位：億元（四捨五入至小數點第一位）
    """
    try:
        # 只需抓最近 30 天即可拿到最新市值
        start = (datetime.today() - timedelta(days=30)).strftime("%Y-%m-%d")
        params = {
            "dataset":    "TaiwanStockMarketValue",
            "data_id":    stock_id,
            "start_date": start,
            "token":      FINMIND_TOKEN,
        }
        body = _fetch_with_retry(params)
        data = body.get("data", []) if isinstance(body, dict) else []
        if not data:
            return None
        # 取最新一筆，欄位為 market_value（單位：千元）
        latest = sorted(data, key=lambda x: x.get("date", ""))[-1]
        market_value_k = float(latest.get("market_value", 0))  # 千元
        return round(market_value_k / 100_000, 1)              # 千元 → 億元
    except Exception as e:
        logger.debug(f"取得 {stock_id} AUM 失敗：{e}")
        return None