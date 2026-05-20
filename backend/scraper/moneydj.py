"""
moneydj.py — MoneyDJ 基金資料爬蟲

經過實測，MoneyDJ 用 requests 可取得：
  ✅ 基金清單（名稱、代號、投信公司）
  ✅ 最新淨值、淨值日期、年度高低點
  ❌ RR 評級、經理人、費率（JavaScript 渲染，需 Selenium，本版暫不實作）

頁面結構（實測確認）：
  主分類頁  YP301000.djhtm           → 各分類代號（ET000001 等）
  分類頁    YP302000.djhtm?a=ETxxxxxx → 基金連結清單
  基金頁    yp010000.djhtm?a=ACxxxxx  → table[3] = 最新淨值摘要
"""

import re
import time
import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional
from scraper import cache

logger = logging.getLogger(__name__)

BASE_URL      = "https://www.moneydj.com"
MAIN_LIST_URL = f"{BASE_URL}/funddj/yb/YP301000.djhtm"
CAT_URL       = f"{BASE_URL}/funddj/yb/YP302000.djhtm"
DETAIL_URL    = f"{BASE_URL}/funddj/ya/yp010000.djhtm"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
    "Referer": BASE_URL,
}

REQUEST_DELAY = 1.2
CACHE_HOURS   = 24


# ── 共用請求 ─────────────────────────────────────
def _get(url: str, params: dict = None, retries: int = 3) -> Optional[BeautifulSoup]:
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            resp.encoding = "big5"          # MoneyDJ 用 BIG5 編碼
            time.sleep(REQUEST_DELAY)
            return BeautifulSoup(resp.text, "lxml")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logger.error("MoneyDJ 403，可能需要更換 User-Agent")
                return None
            logger.warning(f"HTTP 錯誤（第 {attempt+1} 次）：{e}")
        except requests.exceptions.Timeout:
            logger.warning(f"逾時（第 {attempt+1} 次）：{url}")
        except Exception as e:
            logger.warning(f"請求失敗（第 {attempt+1} 次）：{e}")
        if attempt < retries - 1:
            time.sleep(2 ** attempt)
    return None


def _parse_fund_code(href: str) -> Optional[str]:
    """從 href 解析基金代號，e.g. yp010000.djhtm?a=ACFP132 → ACFP132"""
    if href and "?a=" in href:
        return href.split("?a=")[-1].strip()
    return None


# ── Step 1：取得所有分類代號與名稱 ──────────────
def _get_category_codes(use_cache: bool = True) -> list:
    """
    從 YP301000（主分類頁）抓所有分類代號與對應中文名稱
    回傳：[{"code": "ET000001", "name": "指數型"}, ...]
    """
    CACHE_KEY = "moneydj_categories"
    if use_cache:
        cached = cache.get(CACHE_KEY, CACHE_HOURS)
        if cached:
            return cached

    soup = _get(MAIN_LIST_URL)
    if not soup:
        return []

    categories = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "YP302000" in href and "?a=" in href:
            code = href.split("?a=")[-1].strip()
            name = a.get_text(strip=True)
            if code and code not in seen and name:
                seen.add(code)
                categories.append({"code": code, "name": name})

    logger.info(f"找到 {len(categories)} 個分類")
    if categories:
        cache.set(CACHE_KEY, categories)
    return categories


# ── Step 2：從分類頁抓基金清單 ───────────────────
def _clean_fund_name(name: str) -> str:
    """
    去除基金名稱後面的免責聲明括號
    e.g. '元大台灣50基金（本基金為策略...）' → '元大台灣50基金'
    """
    # 截掉第一個全形或半形左括號之後的內容
    for bracket in ["（", "("]:
        idx = name.find(bracket)
        if idx > 0:
            name = name[:idx]
    return name.strip()


def _scrape_category(cat_code: str, cat_name: str = "") -> list[dict]:
    """
    從 YP302000?a=ETxxxxxx 抓該分類的所有基金。

    頁面上基金連結與公司連結成對出現（實測）：
      yp010000?a=ACFP132  → 富邦台灣核心半導體ETF基金
      yp020000?a=BFZFPA   → 富邦投信
      yp010000?a=ACCA98   → 群益臺灣加權指數...
      yp020000?a=BFZCAA   → 群益投信
      ...

    做法：掃描所有連結，遇到 yp010000 記錄，下一個 yp020000 就是對應公司。
    """
    soup = _get(CAT_URL, params={"a": cat_code})
    if not soup:
        return []

    funds    = []
    seen     = set()
    all_links = soup.find_all("a", href=True)

    i = 0
    while i < len(all_links):
        a    = all_links[i]
        href = a.get("href", "")

        if "yp010000" in href:
            fund_code = _parse_fund_code(href)
            name      = _clean_fund_name(a.get_text(strip=True))

            if fund_code and name and fund_code not in seen:
                seen.add(fund_code)

                # 往後找第一個 yp020000 連結當作公司名稱
                company = ""
                for j in range(i + 1, min(i + 5, len(all_links))):
                    nxt = all_links[j]
                    if "yp020000" in nxt.get("href", ""):
                        company = nxt.get_text(strip=True)
                        break

                funds.append({
                    "fund_code": fund_code,
                    "name":      name,
                    "company":   company,
                    "type":      cat_name,
                })

        i += 1

    return funds


# ── 主要公開函式：取得完整基金清單 ──────────────
def scrape_fund_list(use_cache: bool = True) -> list[dict]:
    """
    完整流程：
      1. 抓主分類頁取得所有分類代號
      2. 遍歷每個分類頁取得基金清單
      3. 去重後回傳

    回傳格式：
    [{"fund_code": "ACFP132", "name": "富邦台灣核心半導體ETF基金",
      "company": "富邦投信", "type": ""}, ...]
    """
    CACHE_KEY = "moneydj_fund_list"
    if use_cache:
        cached = cache.get(CACHE_KEY, CACHE_HOURS)
        if cached:
            logger.info(f"從快取載入基金清單（{len(cached)} 檔）")
            return cached

    cat_codes = _get_category_codes(use_cache=False)
    if not cat_codes:
        logger.error("無法取得分類代號，MoneyDJ 爬蟲中止")
        return []

    all_funds = []
    seen      = set()

    for i, cat in enumerate(cat_codes, 1):
        code = cat["code"]
        name = cat["name"]
        logger.info(f"[{i}/{len(cat_codes)}] 爬取分類 {code} ({name})")
        funds = _scrape_category(code, name)
        for f in funds:
            if f["fund_code"] not in seen:
                seen.add(f["fund_code"])
                all_funds.append(f)

    logger.info(f"MoneyDJ 基金清單：共 {len(all_funds)} 檔")
    if all_funds:
        cache.set(CACHE_KEY, all_funds)
    return all_funds


# ── 個別基金補充資訊 ─────────────────────────────
def scrape_fund_detail(fund_code: str, use_cache: bool = True) -> dict:
    """
    從 yp010000?a=ACxxxxx 取得可用的靜態資料：
      - latest_nav     : 最新淨值
      - nav_date       : 淨值日期
      - nav_high_year  : 年度最高淨值
      - nav_low_year   : 年度最低淨值

    RR 評級、經理人、費率為 JavaScript 渲染，本函式回傳 None。
    """
    CACHE_KEY = f"moneydj_detail_{fund_code}"
    if use_cache:
        cached = cache.get(CACHE_KEY, CACHE_HOURS)
        if cached:
            return cached

    result = {
        "fund_code":    fund_code,
        "nav":          None,
        "nav_date":     None,
        "nav_high_year":None,
        "nav_low_year": None,
        # JS 渲染，暫不支援
        "rr_rating":    None,
        "manager":      None,
        "expense_ratio":None,
        "aum":          None,
        "region":       None,
    }

    soup = _get(DETAIL_URL, params={"a": fund_code})
    if not soup:
        return result

    # table[3] class="t01"：淨值日期 | 最新淨值 | 每日變化 | 最高淨值(年) | 最低淨值(年)
    # 實測欄位順序：['2026/05/19', '39.7600', '-1.4000', '42.9600', '15.5300']
    tables = soup.find_all("table")
    t01_tables = [t for t in tables if "t01" in (t.get("class") or [])]

    for t in t01_tables:
        rows = t.find_all("tr")
        if len(rows) < 2:
            continue
        header_cells = [td.get_text(strip=True) for td in rows[0].find_all(["td", "th"])]
        # 確認是淨值摘要表（含「淨值日期」）
        if "淨值日期" not in " ".join(header_cells) and "最新淨值" not in " ".join(header_cells):
            continue
        data_cells = [td.get_text(strip=True) for td in rows[1].find_all(["td", "th"])]
        if len(data_cells) >= 4:
            result["nav_date"]      = data_cells[0] or None
            result["nav"]           = _to_float(data_cells[1])
            result["nav_high_year"] = _to_float(data_cells[3])
            result["nav_low_year"]  = _to_float(data_cells[4]) if len(data_cells) > 4 else None
        break

    cache.set(CACHE_KEY, result)
    return result


def _to_float(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None
