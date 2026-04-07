"""
data_source.py — 資料來源層
切換資料來源只需改這個檔案，calculators 和路由不受影響

FinMind API 文件：https://finmindtrade.com/analysis/#/Announcement/api
免費方案：每天 600 次請求，每次最多 1000 筆
"""

import os
import requests
import pandas as pd
from functools import lru_cache
from datetime import datetime, timedelta

# ── 設定 ────────────────────────────────────────
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")  # 建議放環境變數
FINMIND_BASE  = "https://api.finmindtrade.com/api/v4/data"

# 基準指數：用 0050（元大台灣 50）當台股基準
# 若要用台灣加權指數可改成 "TAIEX"（但 FinMind 免費方案不一定有）
BENCHMARK_ID = "0050"

PERIOD_DAYS = {"1Y": 365, "3Y": 1095, "5Y": 1825}


# ── 共用 fetch ───────────────────────────────────
def _finmind_get(dataset: str, data_id: str, start_date: str, end_date: str = None) -> pd.DataFrame:
    """
    呼叫 FinMind API，回傳 DataFrame
    """
    if not end_date:
        end_date = datetime.today().strftime("%Y-%m-%d")

    params = {
        "dataset":   dataset,
        "data_id":   data_id,
        "start_date": start_date,
        "end_date":  end_date,
        "token":     FINMIND_TOKEN,
    }
    resp = requests.get(FINMIND_BASE, params=params, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    if body.get("status") != 200:
        raise RuntimeError(f"FinMind error: {body.get('msg')}")

    return pd.DataFrame(body.get("data", []))


def _start_date(period: str) -> str:
    days = PERIOD_DAYS.get(period, 1095)
    return (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")


# ── 基金清單 ─────────────────────────────────────
@lru_cache(maxsize=1)          # 避免重複打，快取到程序重啟
def get_fund_list() -> pd.DataFrame:
    """
    取得台灣基金基本資訊清單
    dataset: TaiwanMutualFundInfo
    回傳欄位：fund_id, name, company, category
    """
    params = {
        "dataset": "TaiwanMutualFundInfo",
        "token":   FINMIND_TOKEN,
    }
    resp = requests.get(FINMIND_BASE, params=params, timeout=15)
    resp.raise_for_status()
    body = resp.json()

    if body.get("status") != 200:
        raise RuntimeError(f"FinMind error: {body.get('msg')}")

    df = pd.DataFrame(body.get("data", []))

    # FinMind 欄位：fund_id / fund_name / fund_company / fund_type
    # 統一改成專案內的命名
    df = df.rename(columns={
        "fund_id":      "fund_id",
        "fund_name":    "name",
        "fund_company": "company",
        "fund_type":    "type",
    })

    # TODO: FinMind 實際欄位名稱需要測試後再對齊，以上是推測命名
    return df


# ── 基金 NAV 歷史 ─────────────────────────────────
def get_nav_series(fund_id: str, period: str) -> pd.Series:
    """
    取得基金歷史 NAV，回傳以日期為 index 的 Series
    dataset: TaiwanMutualFund
    """
    start = _start_date(period)
    df = _finmind_get("TaiwanMutualFund", fund_id, start)

    if df.empty:
        return pd.Series(dtype=float)

    # FinMind 回傳欄位：date / fund_id / nav
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    return df["nav"].astype(float)


# ── 基準指數 ──────────────────────────────────────
def get_benchmark_series(period: str) -> pd.Series:
    """
    取得基準指數歷史資料（0050），回傳以日期為 index 的 Series
    dataset: TaiwanStockPrice
    """
    start = _start_date(period)
    df = _finmind_get("TaiwanStockPrice", BENCHMARK_ID, start)

    if df.empty:
        return pd.Series(dtype=float)

    # FinMind 回傳欄位：date / stock_id / close / ...
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")

    return df["close"].astype(float)


# ── 單一基金基本資訊 ───────────────────────────────
def get_fund_info(fund_id: str):
    """
    從基金清單中找出單一基金的基本資訊
    """
    funds = get_fund_list()
    row = funds[funds["fund_id"] == fund_id]
    if row.empty:
        return None
    return row.iloc[0].to_dict()