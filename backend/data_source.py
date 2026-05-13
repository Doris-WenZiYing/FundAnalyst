"""
data_source.py — 資料來源層（ETF 版）

FinMind 免費限制：每天 600 次請求
改用 TaiwanStockPrice 抓台灣 ETF 股價（含 0050 當基準）
"""

import os
import time
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ── 設定 ────────────────────────────────────────
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
FINMIND_BASE  = "https://api.finmindtrade.com/api/v4/data"
BENCHMARK_ID  = "0050"
PERIOD_DAYS   = {"1Y": 365, "3Y": 1095, "5Y": 1825}

# ── 內建 ETF 清單 ────────────────────────────────
ETF_LIST = [
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


# ── 重試機制 ─────────────────────────────────────
def _fetch_with_retry(params: dict, max_retries: int = 3, backoff: float = 2.0) -> dict:
    """
    帶重試的 FinMind API 請求
    - 最多重試 max_retries 次
    - 指數退避：第 1 次等 2s，第 2 次等 4s，第 3 次等 8s
    - 429（超過速率限制）等更久
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(FINMIND_BASE, params=params, timeout=15)

            if resp.status_code == 429:
                wait = backoff ** (attempt + 2)
                logger.warning(f"FinMind rate limit，等待 {wait:.0f}s 後重試")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            body = resp.json()

            if isinstance(body, dict) and "detail" in body:
                raise RuntimeError(f"FinMind API 錯誤：{body['detail']}")

            return body

        except requests.exceptions.Timeout:
            last_error = "請求逾時"
            logger.warning(f"FinMind timeout（第 {attempt + 1} 次），重試中...")
        except requests.exceptions.ConnectionError:
            last_error = "連線失敗"
            logger.warning(f"FinMind 連線失敗（第 {attempt + 1} 次），重試中...")
        except RuntimeError:
            raise
        except Exception as e:
            last_error = str(e)
            logger.warning(f"未預期錯誤（第 {attempt + 1} 次）：{e}")

        if attempt < max_retries:
            time.sleep(backoff ** attempt)

    raise RuntimeError(f"FinMind 請求失敗（已重試 {max_retries} 次）：{last_error}")


# ── 時序補值 ─────────────────────────────────────
def _fill_trading_series(series: pd.Series) -> pd.Series:
    """
    補齊時序缺口，讓基金和基準指數日期能對齊：
    1. 重新索引為每日頻率
    2. 前向填補（非交易日沿用前一交易日收盤價）
    3. 去除頭部 NaN
    """
    if series.empty:
        return series
    full_idx = pd.date_range(start=series.index.min(), end=series.index.max(), freq="D")
    return series.reindex(full_idx).ffill().dropna()


def _start_date(period: str) -> str:
    days = PERIOD_DAYS.get(period, 1095)
    return (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── 基金（ETF）清單 ──────────────────────────────
def get_fund_list() -> pd.DataFrame:
    """回傳內建 ETF 清單（不打 API）"""
    return pd.DataFrame(ETF_LIST)


# ── 單一 ETF 基本資訊 ────────────────────────────
def get_fund_info(fund_id: str):
    funds = get_fund_list()
    row   = funds[funds["fund_id"] == fund_id]
    if row.empty:
        return None

    info = row.iloc[0].to_dict()
    info.setdefault("risk_level",    None)
    info.setdefault("aum",           None)
    info.setdefault("expense_ratio", None)

    try:
        nav_series = get_nav_series(fund_id, "1Y")
        if not nav_series.empty:
            info["nav"]      = float(nav_series.iloc[-1])
            info["nav_date"] = str(nav_series.index[-1].date())
        else:
            info["nav"] = info["nav_date"] = None
    except Exception as e:
        logger.warning(f"取得 {fund_id} NAV 失敗：{e}")
        info["nav"] = info["nav_date"] = None

    return info


# ── ETF 歷史收盤價 ───────────────────────────────
def get_nav_series(fund_id: str, period: str) -> pd.Series:
    """取得 ETF 歷史收盤價 Series（已補值）"""
    params = {
        "dataset":    "TaiwanStockPrice",
        "data_id":    fund_id,
        "start_date": _start_date(period),
        "token":      FINMIND_TOKEN,
    }
    body = _fetch_with_retry(params)
    data = body.get("data", []) if isinstance(body, dict) else []

    if not data:
        return pd.Series(dtype=float)

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return _fill_trading_series(df["close"].astype(float))


# ── 基準指數（0050）────────────────────────────
def get_benchmark_series(period: str) -> pd.Series:
    """用 0050 當基準指數（已補值）"""
    params = {
        "dataset":    "TaiwanStockPrice",
        "data_id":    BENCHMARK_ID,
        "start_date": _start_date(period),
        "token":      FINMIND_TOKEN,
    }
    body = _fetch_with_retry(params)
    data = body.get("data", []) if isinstance(body, dict) else []

    if not data:
        return pd.Series(dtype=float)

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return _fill_trading_series(df["close"].astype(float))