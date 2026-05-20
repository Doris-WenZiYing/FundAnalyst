"""
fund_mapper.py — MoneyDJ 代號 ↔ FinMind 股票代號 對照表

MoneyDJ 用自己的代號（ACFP132），FinMind 用證交所代號（00892）。
本模組透過名稱模糊比對，自動建立對照表並儲存為 JSON。

使用方式：
  python3 fund_mapper.py          # 建立並儲存對照表
  from fund_mapper import get_stock_id  # 在其他模組中使用
"""

import os
import re
import json
import logging
import requests
from difflib import SequenceMatcher
from typing import Optional

logger = logging.getLogger(__name__)

FINMIND_TOKEN  = os.environ.get("FINMIND_TOKEN", "")
FINMIND_BASE   = "https://api.finmindtrade.com/api/v4/data"
MAPPING_PATH   = os.path.join(os.path.dirname(__file__), "fund_mapping.json")

# 載入到記憶體的對照表（fund_code → stock_id）
_mapping: dict = {}


# ── 名稱正規化 ────────────────────────────────────
def _normalize(name: str) -> str:
    """
    移除不影響比對的詞彙和字元，讓名稱更容易對齊。

    MoneyDJ：「富邦台灣核心半導體ETF基金」→「富邦台灣核心半導體」
    FinMind ：「富邦台灣核心半導體」        →「富邦台灣核心半導體」
    """
    # 移除常見後綴
    for suffix in ["基金", "ETF", "指數股票型基金", "受益憑證"]:
        name = name.replace(suffix, "")
    # 移除括號及內容
    name = re.sub(r"[（(][^）)]*[）)]", "", name)
    # 移除空白和常見噪音字元
    name = re.sub(r"[\s\-_·・　]", "", name)
    # 移除「單日正向」「單日反向」等槓桿說明
    for token in ["單日正向", "單日反向", "正向", "反向", "2倍", "1倍", "-2倍"]:
        name = name.replace(token, "")
    return name.strip()


def _similarity(a: str, b: str) -> float:
    """計算兩個字串的相似度（0–1）"""
    return SequenceMatcher(None, a, b).ratio()


# ── 從 FinMind 抓所有 ETF ─────────────────────────
def _fetch_etf_list() -> list[dict]:
    """
    從 TaiwanStockInfo 取得所有股票，
    篩選 stock_id 為 4–5 位且以 '0' 開頭的（ETF 格式：0050、00878、006208 等）
    """
    resp = requests.get(
        FINMIND_BASE,
        params={"dataset": "TaiwanStockInfo", "token": FINMIND_TOKEN},
        timeout=20,
    )
    resp.raise_for_status()
    body = resp.json()
    all_stocks = body.get("data", [])

    etfs = []
    seen = set()
    for s in all_stocks:
        sid  = s.get("stock_id", "")
        name = s.get("stock_name", "")
        # ETF：stock_id 以 0 開頭，長度 4–6 位
        if sid.startswith("0") and 4 <= len(sid) <= 6 and sid not in seen:
            seen.add(sid)
            etfs.append({"stock_id": sid, "stock_name": name})

    logger.info(f"FinMind ETF 清單：{len(etfs)} 筆")
    return etfs


# ── 建立對照表 ────────────────────────────────────
def build_mapping(moneydj_funds: list[dict], threshold: float = 0.70) -> dict:
    """
    對每一筆 MoneyDJ 基金，找最相似的 FinMind ETF。

    Parameters
    ----------
    moneydj_funds : MoneyDJ 基金清單，每筆含 fund_code、name
    threshold     : 相似度門檻（0–1），低於此值視為無對應

    Returns
    -------
    dict: {fund_code: stock_id, ...}
         無法比對的 fund_code 不會出現在結果中
    """
    etf_list = _fetch_etf_list()
    if not etf_list:
        logger.error("無法取得 FinMind ETF 清單")
        return {}

    # 先對 FinMind ETF 名稱正規化（只算一次）
    etf_normalized = [
        (e["stock_id"], e["stock_name"], _normalize(e["stock_name"]))
        for e in etf_list
    ]

    mapping   = {}
    no_match  = []

    for fund in moneydj_funds:
        code       = fund["fund_code"]
        mj_name    = fund["name"]
        mj_norm    = _normalize(mj_name)

        best_sid   = None
        best_score = 0.0
        best_name  = ""

        for sid, raw_name, etf_norm in etf_normalized:
            # 快速過濾：正規化後長度差距太大的直接跳過
            if abs(len(mj_norm) - len(etf_norm)) > max(len(mj_norm), len(etf_norm)) * 0.6:
                continue

            score = _similarity(mj_norm, etf_norm)

            # 額外加分：一方完全包含另一方
            if etf_norm and mj_norm:
                if etf_norm in mj_norm or mj_norm in etf_norm:
                    score = max(score, 0.80)

            if score > best_score:
                best_score = score
                best_sid   = sid
                best_name  = raw_name

        if best_score >= threshold and best_sid:
            mapping[code] = best_sid
            logger.debug(
                f"✅ {mj_name[:20]:<20} → {best_sid} {best_name[:20]}"
                f"  (score={best_score:.2f})"
            )
        else:
            no_match.append(mj_name[:30])
            logger.debug(
                f"❌ {mj_name[:30]:<30}  "
                f"best={best_score:.2f} ({best_name[:20]})"
            )

    logger.info(
        f"比對完成：{len(mapping)} 筆成功，"
        f"{len(no_match)} 筆無法對應（共 {len(moneydj_funds)} 筆）"
    )
    if no_match:
        logger.debug(f"無法對應：{no_match[:10]}")

    return mapping


# ── 儲存 / 載入對照表 ─────────────────────────────
def save_mapping(mapping: dict) -> None:
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)
    logger.info(f"對照表已儲存：{MAPPING_PATH}（{len(mapping)} 筆）")


def load_mapping() -> dict:
    global _mapping
    if _mapping:
        return _mapping
    if not os.path.exists(MAPPING_PATH):
        return {}
    with open(MAPPING_PATH, encoding="utf-8") as f:
        _mapping = json.load(f)
    logger.info(f"對照表載入：{len(_mapping)} 筆")
    return _mapping


# ── 對外查詢 ─────────────────────────────────────
def get_stock_id(fund_code: str) -> Optional[str]:
    """
    給 MoneyDJ 代號，回傳對應的 FinMind 股票代號。
    若無對應回傳 None。
    """
    m = load_mapping()
    return m.get(fund_code)


def get_fund_code(stock_id: str) -> Optional[str]:
    """反查：給 FinMind 股票代號，回傳 MoneyDJ 代號"""
    m = load_mapping()
    for fc, sid in m.items():
        if sid == stock_id:
            return fc
    return None


# ── CLI：建立對照表 ───────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("Step 1：從 MoneyDJ 載入基金清單...")
    from scraper.moneydj import scrape_fund_list
    funds = scrape_fund_list(use_cache=True)
    print(f"  → {len(funds)} 檔")

    print("\nStep 2：從 FinMind 取得 ETF 清單並比對名稱...")
    mapping = build_mapping(funds, threshold=0.70)

    print(f"\nStep 3：儲存對照表到 fund_mapping.json")
    save_mapping(mapping)

    # 印出結果預覽
    print(f"\n{'='*55}")
    print(f"比對成功 {len(mapping)} 筆，預覽前 10 筆：")
    print(f"{'MoneyDJ 代號':<12} {'FinMind 代號':<10} {'MoneyDJ 名稱'}")
    print("-" * 55)
    fund_lookup = {f["fund_code"]: f["name"] for f in funds}
    for fc, sid in list(mapping.items())[:10]:
        print(f"{fc:<12} {sid:<10} {fund_lookup.get(fc, '')[:28]}")

    print(f"\n無法比對：{len(funds) - len(mapping)} 筆")
    print("（共同基金因名稱差異較大，需手動補充 fund_mapping.json）")
