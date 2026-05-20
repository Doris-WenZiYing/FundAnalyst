"""
test_moneydj.py — MoneyDJ 爬蟲驗證腳本
在 backend/ 目錄下執行：python3 test_moneydj.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from scraper import cache
from scraper.moneydj import _get_category_codes, _scrape_category, scrape_fund_detail

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}


def test_categories():
    print("=" * 50)
    print("測試 1：取得分類代號")
    cache.clear_all()
    codes = _get_category_codes(use_cache=False)
    print(f"結果：共 {len(codes)} 個分類，前 5 個：{codes[:5]}")
    return codes


def test_category_funds(cat_code="ET000001"):
    print(f"\n{'='*50}")
    print(f"測試 2：爬取分類 {cat_code}")
    funds = _scrape_category(cat_code)
    print(f"結果：共 {len(funds)} 檔，前 3 筆：")
    for f in funds[:3]:
        print(f"  {f}")
    return funds


def test_fund_detail(fund_code="ACFP132"):
    print(f"\n{'='*50}")
    print(f"測試 3：基金 {fund_code} 詳細資訊")
    detail = scrape_fund_detail(fund_code, use_cache=False)
    print(f"結果：{detail}")


if __name__ == "__main__":
    codes = test_categories()
    if codes:
        funds = test_category_funds(codes[0])
        if funds:
            test_fund_detail(funds[0]["fund_code"])

            # 加在 test_moneydj.py 最下面，test_fund_detail 函式後面

def find_stock_code_on_page():
    import re
    resp = requests.get(
        "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACFP132",
        headers=HEADERS, timeout=15
    )
    resp.encoding = "big5"
    
    print("頁面上所有 4-6 位純數字：")
    nums = set(re.findall(r'\b\d{4,6}\b', resp.text))
    print(sorted(nums))
    
    print("\n含關鍵字的文字片段：")
    for kw in ["上市", "股票代號", "ETF代號", "證券代號"]:
        idx = resp.text.find(kw)
        if idx != -1:
            print(f"  「{kw}」→ {resp.text[idx:idx+40]}")
        else:
            print(f"  「{kw}」→ 找不到")


if __name__ == "__main__":
    codes = test_categories()
    if codes:
        funds = test_category_funds(codes[0])
        if funds:
            test_fund_detail(funds[0]["fund_code"])
    find_stock_code_on_page()   # ← 加這行

def test_finmind_stock_info():
    import os
    TOKEN = os.environ.get("FINMIND_TOKEN", "")
    resp = requests.get(
        "https://api.finmindtrade.com/api/v4/data",
        params={"dataset": "TaiwanStockInfo", "token": TOKEN},
        timeout=15
    )
    data = resp.json()
    print(f"HTTP：{resp.status_code}")
    if data.get("data"):
        df_sample = data["data"][:3]
        print("欄位：", list(df_sample[0].keys()))
        print("前3筆：")
        for r in df_sample:
            print(f"  {r}")
    else:
        print("回傳：", data)

test_finmind_stock_info()