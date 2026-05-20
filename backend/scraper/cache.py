"""
cache.py — 簡易 JSON 檔案快取

把爬蟲結果存成本地 JSON，避免每次重啟都重新爬。
快取位置：backend/scraper/cache/
快取有效期：預設 24 小時
"""

import json
import os
import time
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _path(key: str) -> str:
    safe = key.replace("/", "_").replace(":", "_")
    return os.path.join(CACHE_DIR, f"{safe}.json")


def get(key: str, max_age_hours: float = 24) -> Optional[Any]:
    """
    讀取快取，若超過 max_age_hours 視為過期回傳 None
    """
    fpath = _path(key)
    if not os.path.exists(fpath):
        return None
    try:
        age = time.time() - os.path.getmtime(fpath)
        if age > max_age_hours * 3600:
            logger.debug(f"快取過期：{key}")
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"讀取快取失敗 [{key}]：{e}")
        return None


def set(key: str, data: Any) -> None:
    """寫入快取"""
    _ensure_dir()
    fpath = _path(key)
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"寫入快取失敗 [{key}]：{e}")


def clear(key: str) -> None:
    """刪除特定快取"""
    fpath = _path(key)
    if os.path.exists(fpath):
        os.remove(fpath)


def clear_all() -> None:
    """清除所有快取"""
    _ensure_dir()
    for f in os.listdir(CACHE_DIR):
        if f.endswith(".json"):
            os.remove(os.path.join(CACHE_DIR, f))
    logger.info("已清除所有爬蟲快取")
