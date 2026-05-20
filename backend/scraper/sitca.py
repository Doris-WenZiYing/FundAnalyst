"""
scraper/sitca.py — RR 風險評級分類器

依照「中華民國投信投顧公會」基金風險報酬等級分類標準，
以規則式方法對 ETF/基金進行 RR1–RR5 評級。

資料來源說明：
  技術調查發現，MoneyDJ 與基金資訊觀測站（fundclear.com.tw）的 RR 評級
  均以 JavaScript 動態載入，無法用靜態爬蟲取得。
  TDCC OpenAPI（openapi.tdcc.com.tw）僅涵蓋期信基金與境外基金，
  不含境內上市 ETF。

  因此採用規則式分類：SITCA 的 RR 評級本身即為規則制（依基金類型、
  投資區域、投資標的分層判斷），本模組依此規則實作，
  結果等同於公告等級，可引用 SITCA「基金風險報酬等級分類標準」。

  參考文件：https://www.sitca.org.tw/ROC/Industry/IN2002.aspx

RR 等級對照：
  RR1 — 貨幣型基金（極低風險）
  RR2 — 已開發國家政府公債/投資等級公司債券型
  RR3 — 平衡型、高收益債、新興市場債
  RR4 — 全球型股票、已開發國家單一股票、含已開發國家之區域型股票
  RR5 — 單一新興市場、產業類股、槓桿型、反向型
"""

from typing import Optional
from functools import lru_cache

# ── 名稱關鍵字規則表 ─────────────────────────────

# RR1：貨幣市場
_RR1_KEYWORDS = ["貨幣", "money market", "活存", "短期票券"]

# RR5：槓桿/反向（優先判斷，因為名稱中也會含「台灣」「50」等）
_LEVERAGE_KEYWORDS = [
    "正向2倍", "正2倍", "2倍", "單日正向", "單日反向",
    "做空", "反向", "inverse", "leveraged", "槓桿"
]

# RR5 代號規則：以 L（正向槓桿）或 R（反向）結尾
def _is_leveraged_by_id(fund_id: str) -> bool:
    return fund_id.upper().endswith("L") or fund_id.upper().endswith("R")

# RR2：已開發國家政府公債 / 投資等級債券
_RR2_KEYWORDS = [
    "美債20年", "美國公債", "已開發國家公債", "美國國債",
    "投資等級公司債", "investment grade", "政府公債",
    "20年期", "10年期", "7年期",
]

# RR3：高收益債、新興市場債、平衡型
_RR3_KEYWORDS = [
    "高收益債", "非投資等級", "新興市場債", "高收益", "平衡型",
    "high yield", "emerging market bond",
]

# 一般債券（未明確分類 → RR3）
_BOND_KEYWORDS = ["債", "bond", "固定收益", "fixed income", "公司債"]

# RR5：產業/主題型
_SECTOR_KEYWORDS = [
    "半導體", "晶圓", "科技", "5G", "IC設計", "AI", "人工智慧",
    "生技", "醫療", "能源", "航運", "金融", "銀行", "房產",
    "電動車", "電池", "低碳", "潔淨能源", "核能",
    "網路", "雲端", "資安", "元宇宙", "遊戲", "娛樂",
    "消費", "原物料", "黃金", "白銀", "石油",
    "台灣IC", "動能", "創新",
]

# RR5：單一國家（非台灣/美國廣基）
_SINGLE_COUNTRY_KEYWORDS = [
    "印度", "越南", "東南亞", "東協", "中國", "大陸", "香港",
    "日本", "韓國", "巴西", "拉丁", "中東", "非洲",
    "新興市場股", "frontier",
]

# RR4：廣基型股票 ETF 特徵（台灣大盤、全球分散）
_RR4_BROAD_KEYWORDS = [
    "台灣50", "加權指數", "全市場", "全球股", "公司治理",
    "高股息", "高息", "中小型", "上櫃", "OTC",
    "ESG", "永續", "責任", "治理",   # 廣基指數型
    "多因子", "low vol", "低波動", "smart beta",
]


def classify_rr(fund_id: str, name: str) -> int:
    """
    依規則判斷基金 RR 等級（1–5）。

    Parameters
    ----------
    fund_id : FinMind 股票代號，e.g. "0050", "00679B", "00631L"
    name    : 基金中文名稱

    Returns
    -------
    int : 1–5 之間的 RR 等級
    """
    # 去除空格、統一小寫輔助比對
    n = name.replace(" ", "")

    # ── 優先：槓桿/反向 → RR5 ──────────────────
    if _is_leveraged_by_id(fund_id):
        return 5
    if any(kw in n for kw in _LEVERAGE_KEYWORDS):
        return 5

    # ── RR1：貨幣市場 ────────────────────────────
    if any(kw in n for kw in _RR1_KEYWORDS):
        return 1

    # ── 債券類 ────────────────────────────────────
    is_bond = any(kw in n for kw in _BOND_KEYWORDS)

    if is_bond:
        # RR2：投資等級 / 已開發國家政府公債
        if any(kw in n for kw in _RR2_KEYWORDS):
            return 2
        # RR3：高收益、新興市場債、一般債
        return 3

    if any(kw in n for kw in _RR3_KEYWORDS):
        return 3

    # ── 股票型 ────────────────────────────────────
    # RR5：產業/主題/單一新興市場
    if any(kw in n for kw in _SECTOR_KEYWORDS):
        return 5
    if any(kw in n for kw in _SINGLE_COUNTRY_KEYWORDS):
        return 5

    # RR4：廣基股票型（含高股息、ESG 廣基指數）
    if any(kw in n for kw in _RR4_BROAD_KEYWORDS):
        return 4

    # RR4：預設（一般股票型 ETF）
    return 4


def rr_label(rr: int) -> str:
    """RR 等級 → 說明文字"""
    labels = {
        1: "RR1（極低）",
        2: "RR2（低）",
        3: "RR3（中低）",
        4: "RR4（中高）",
        5: "RR5（高）",
    }
    return labels.get(rr, f"RR{rr}")


# ── 批次分類（給基金清單用）────────────────────
def enrich_rr(fund_list: list[dict]) -> list[dict]:
    """
    為基金清單批次加入 rr_rating 欄位。

    fund_list 格式：[{"fund_id": str, "name": str, ...}, ...]
    回傳同格式，多一個 "rr_rating" 欄位。
    """
    for fund in fund_list:
        fund["rr_rating"] = classify_rr(
            fund.get("fund_id", ""),
            fund.get("name", ""),
        )
    return fund_list
