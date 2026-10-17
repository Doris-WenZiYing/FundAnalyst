"""
stock_data.py — ETF 成分股與個股股價

成分股：data/etf_constituents.json（固定成分股，對應論文 3.5.1 的設計）
股價：  依序嘗試
        1. FinMind TaiwanStockPriceAdj（還原股價，需較高權限）
        2. Yahoo Finance（yfinance，auto_adjust 還原股價，含配息與分割）
        3. FinMind TaiwanStockPrice（未還原收盤價，最後備援）
        回傳時用 adjusted 旗標告訴前端是哪一種，source 記錄實際來源。

注意：這裡「不」把股價補成日曆日（不像 data_source._fill_series），
      只保留實際交易日，年化與波動率才會正確（一年約 252 個交易日）。
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta

import pandas as pd

from data_source import _fetch_with_retry, FINMIND_TOKEN
from scraper import cache

logger = logging.getLogger(__name__)

DATA_PATH   = os.path.join(os.path.dirname(__file__), "data", "etf_constituents.json")
CACHE_HOURS = 12
CHUNK_DAYS  = 900


# ── 成分股 ───────────────────────────────────────
def _load_constituent_file() -> dict:
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def list_etfs() -> list:
    data = _load_constituent_file()
    return [
        {"etf_id": k, "name": v.get("name", k), "as_of": v.get("as_of"),
         "source": v.get("source"), "count": len(v.get("constituents", []))}
        for k, v in data.items()
    ]


def get_constituents(etf_id: str):
    """回傳 {"etf_id", "name", "as_of", "source", "constituents": [...]}，找不到回 None"""
    data = _load_constituent_file()
    if etf_id not in data:
        return None
    return {"etf_id": etf_id, **data[etf_id]}


# ── 股價 ─────────────────────────────────────────
def _fetch_dataset(dataset: str, stock_id: str, start: str, end: str) -> list:
    rows = []
    cur  = datetime.strptime(start, "%Y-%m-%d")
    stop = datetime.strptime(end,   "%Y-%m-%d")
    while cur <= stop:
        chunk_end = min(cur + timedelta(days=CHUNK_DAYS), stop)
        body = _fetch_with_retry({
            "dataset":    dataset,
            "data_id":    stock_id,
            "start_date": cur.strftime("%Y-%m-%d"),
            "end_date":   chunk_end.strftime("%Y-%m-%d"),
            "token":      FINMIND_TOKEN,
        })
        rows.extend(body.get("data", []) if isinstance(body, dict) else [])
        cur = chunk_end + timedelta(days=1)
        time.sleep(0.3)
    return rows


def _to_series(rows: list) -> pd.Series:
    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows)
    if "close" not in df.columns:
        return pd.Series(dtype=float)
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates("date").sort_values("date")
    s = df.set_index("date")["close"].astype(float)
    return s[s > 0]


def _fetch_yahoo(stock_id: str, start: str, end: str) -> pd.Series:
    """Yahoo 還原收盤價。上市用 .TW，上櫃用 .TWO。yfinance 的 end 不含當天，所以 +1 天。"""
    try:
        import yfinance as yf
    except ImportError:
        logger.info("未安裝 yfinance，略過 Yahoo 還原股價")
        return pd.Series(dtype=float)

    end_excl = (datetime.strptime(end, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    for suffix in (".TW", ".TWO"):
        try:
            df = yf.download(f"{stock_id}{suffix}", start=start, end=end_excl,
                             auto_adjust=True, progress=False, threads=False)
        except Exception as e:
            logger.info(f"Yahoo {stock_id}{suffix} 失敗：{e}")
            continue
        if df is None or df.empty or "Close" not in df:
            continue
        close = df["Close"]
        if isinstance(close, pd.DataFrame):          # 新版 yfinance 欄位是 MultiIndex
            close = close.iloc[:, 0]
        close = close.dropna().astype(float)
        close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
        close = close[close > 0]
        if len(close) >= 2:
            return close
    return pd.Series(dtype=float)


def _fetch_finmind(dataset: str, stock_id: str, start: str, end: str) -> pd.Series:
    try:
        return _to_series(_fetch_dataset(dataset, stock_id, start, end))
    except Exception as e:
        logger.info(f"{stock_id} {dataset} 失敗：{e}")
        return pd.Series(dtype=float)


# FinMind 還原股價需要付費權限；第一次拿不到就記下來，之後不再嘗試（避免每檔都重試浪費時間）
_finmind_adj_available = True


def _fetch_finmind_adj(stock_id: str, start: str, end: str) -> pd.Series:
    global _finmind_adj_available
    if not _finmind_adj_available:
        return pd.Series(dtype=float)
    s = _fetch_finmind("TaiwanStockPriceAdj", stock_id, start, end)
    if s.empty:
        _finmind_adj_available = False
        logger.info("FinMind 還原股價不可用，改用 Yahoo")
    return s


# (來源名稱, 是否還原, 取得函式)
PRICE_SOURCES = (
    ("FinMind 還原股價", True,  _fetch_finmind_adj),
    ("Yahoo 還原股價",   True,  _fetch_yahoo),
    ("FinMind 收盤價",   False, lambda sid, s, e: _fetch_finmind("TaiwanStockPrice", sid, s, e)),
)


def _extend_with_raw(series: pd.Series, stock_id: str, end: str) -> pd.Series:
    """
    Yahoo 偶爾晚一天更新，最後幾個交易日會缺。
    缺的日子用 FinMind 收盤價補上：以 Yahoo 最後一天為基準，依收盤價漲跌比例接續。
    （補的只有最後一兩天，期間內剛好除息的機率很低，影響可忽略）
    """
    if series.empty:
        return series
    last = series.index[-1]
    if last.strftime("%Y-%m-%d") >= end:
        return series
    raw = _fetch_finmind("TaiwanStockPrice", stock_id, last.strftime("%Y-%m-%d"), end)
    if raw.empty or last not in raw.index:
        return series
    tail = raw[raw.index > last]
    if tail.empty:
        return series
    extended = series.iloc[-1] * tail / raw.loc[last]
    logger.info(f"{stock_id} Yahoo 缺 {len(tail)} 天，以 FinMind 收盤價補上")
    return pd.concat([series, extended])


def get_price_series(stock_id: str, start: str, end: str, with_source: bool = False):
    """
    回傳 (pd.Series, adjusted: bool)；with_source=True 時回傳 (Series, adjusted, source)。
    Series index 為交易日，值為收盤價；抓不到資料時為空 Series。
    """
    key = f"price_v3_{stock_id}_{start}_{end}"
    hit = cache.get(key, max_age_hours=CACHE_HOURS)
    if hit:
        s = pd.Series(hit["close"], index=pd.to_datetime(hit["dates"]), dtype=float)
        out = (s, hit["adjusted"], hit.get("source"))
        return out if with_source else out[:2]

    series, adjusted, source = pd.Series(dtype=float), False, None
    for name, is_adj, fetch in PRICE_SOURCES:
        series = fetch(stock_id, start, end)
        if len(series) >= 2:
            adjusted, source = is_adj, name
            if name == "Yahoo 還原股價":
                series = _extend_with_raw(series, stock_id, end)
            break

    if len(series) >= 2:
        cache.set(key, {
            "dates":    [d.strftime("%Y-%m-%d") for d in series.index],
            "close":    series.tolist(),
            "adjusted": adjusted,
            "source":   source,
        })
    out = (series, adjusted, source)
    return out if with_source else out[:2]
