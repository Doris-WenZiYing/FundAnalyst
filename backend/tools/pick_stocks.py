"""
pick_stocks.py — 實戰選股（四階段）

放在 backend/tools/，在 backend 資料夾執行：
    python tools/pick_stocks.py                 # 選股日預設 2026-11-09
    python tools/pick_stocks.py --date 2026-11-09 --etf 0050@2026-10-16

輸出（backend/picks/）：
    scores_<日期>.csv   每檔股票各階段結果、各指標百分位、分數
    picks_<日期>.json   前三名、入選理由、選股日收盤價

規則（11/9 確認）
  第一階段 初步排除
    - 完整性：最近 3 個完整會計年度 + 最近連續 8 季財報；必要欄位缺漏 → 排除（產業不適用標 N/A，不算缺漏）
    - 長期虧損：最近 3 年「歸屬母公司稅後淨利」至少 2 年 < 0 → 排除
    - 流動性：近 20 個交易日平均成交金額 < 3,000 萬 → 排除
  第二階段 基本面評分（同產業百分位，產業只有 1、2 檔就直接跟那 1、2 檔比）
    獲利 30%：ROE 8、ROA 5、EPS 5、毛利率 4、營業利益率 4、稅後淨利率 4
    成長 30%：營收成長率 15、EPS 成長率 15
    穩健 20%：負債比率 10（越低越好）、流動比率 10
    估值 20%：本益比 8（越低越好）、股價淨值比 7（越低越好）、殖利率 5
    N/A 的指標不計，權重按比例分給同構面其他指標
  第三階段 風險
    - 近 60 個交易日年化波動率在母體 90–100 百分位 → 排除；75–90 → 風險提醒
    - 重大訊息：列出 MOPS 連結，人工檢查選股日前 30 日（及尚未解決的重大事件）
  第四階段 依總分排序取前三名，另列穩健價值分數 = 穩健 50% + 估值 50%
"""

import argparse
import json
import math
import os
import sys
import time
from datetime import date, datetime, timedelta

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_source import _fetch_with_retry, FINMIND_TOKEN          # noqa: E402
from scraper import cache                                          # noqa: E402
import financials as F                                             # noqa: E402
from stock_data import get_constituents                            # noqa: E402

N_YEARS       = 3
N_QUARTERS    = 8
MIN_MONEY     = 30_000_000
VOL_DAYS      = 60
MONEY_DAYS    = 20
VOL_EXCLUDE   = 90
VOL_WARN      = 75

# (key, 名稱, 構面, 權重, 越大越好)
INDICATORS = [
    ("roe",              "ROE",       "獲利能力", 8,  True),
    ("roa",              "ROA",       "獲利能力", 5,  True),
    ("eps",              "EPS",       "獲利能力", 5,  True),
    ("gross_margin",     "毛利率",     "獲利能力", 4,  True),
    ("operating_margin", "營業利益率",  "獲利能力", 4,  True),
    ("net_margin",       "稅後淨利率",  "獲利能力", 4,  True),
    ("revenue_growth",   "營收成長率",  "成長能力", 15, True),
    ("eps_growth",       "EPS 成長率", "成長能力", 15, True),
    ("debt_ratio",       "負債比率",    "財務穩健", 10, False),
    ("current_ratio",    "流動比率",    "財務穩健", 10, True),
    ("per",              "本益比",     "價值評估", 8,  False),
    ("pbr",              "股價淨值比",  "價值評估", 7,  False),
    ("dividend_yield",   "殖利率",     "價值評估", 5,  True),
]
DIMENSIONS = {"獲利能力": 30, "成長能力": 30, "財務穩健": 20, "價值評估": 20}
FINANCIAL_NA = {"gross_margin", "operating_margin", "debt_ratio", "current_ratio"}
PARTIAL_OK   = {"eps_growth"}       # 前一年 EPS ≤ 0 的年度本來就算不出成長率


# ── 抓資料（含快取）────────────────────────────────
def fetch(dataset, stock_id=None, start=None, end=None):
    params = {"dataset": dataset, "token": FINMIND_TOKEN}
    if stock_id:
        params["data_id"] = stock_id
    if start:
        params["start_date"] = start
    if end:
        params["end_date"] = end
    body = _fetch_with_retry(params)
    time.sleep(0.3)
    return body.get("data", []) if isinstance(body, dict) else []


def cached(key, fn, hours=12):
    hit = cache.get(key, max_age_hours=hours)
    if hit is not None:
        return hit
    val = fn()
    if val:
        cache.set(key, val)
    return val


def industry_map():
    rows = cached("pick_info_v1", lambda: fetch("TaiwanStockInfo"), hours=24 * 7)
    out = {}
    for r in rows or []:
        out.setdefault(str(r.get("stock_id")), r.get("industry_category") or "其他")
    return out


# ── 期間計算 ──────────────────────────────────────
def last_complete_year(pick: date) -> int:
    """年報 3/31 前公告；選股日在 4/1 之後才用去年"""
    return pick.year - 1 if pick >= date(pick.year, 4, 1) else pick.year - 2


def expected_quarters(pick: date, n: int):
    """選股日已過公告期限的最近 n 季（Q1 5/15、Q2 8/14、Q3 11/14、Q4 隔年 3/31）"""
    def deadline(y, q):
        return {1: date(y, 5, 15), 2: date(y, 8, 14), 3: date(y, 11, 14), 4: date(y + 1, 3, 31)}[q]
    y, q, out = pick.year, 4, []
    while len(out) < n:
        if deadline(y, q) < pick:
            out.append((y, q))
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out


# ── 單一股票資料 ──────────────────────────────────
def stock_data(sid, pick: date, end_year: int):
    start = f"{end_year - N_YEARS - 1}-01-01"
    end   = (pick - timedelta(days=1)).isoformat()
    fs = cached(f"pick_fs_{sid}_{start}_{end}", lambda: fetch("TaiwanStockFinancialStatements", sid, start, end)) or []
    bs = cached(f"pick_bs_{sid}_{start}_{end}", lambda: fetch("TaiwanStockBalanceSheet", sid, start, end)) or []

    years = list(range(end_year - N_YEARS + 1, end_year + 1))
    fin = F.compute_annual(fs, bs, years) if fs else None

    # 歸屬母公司稅後淨利（年度）
    net_income = []
    if fs:
        idx = F._index(fs)
        ni = F._first(idx, F.NET_INCOME_KEYS)
        cum = F._is_cumulative(idx.get("Revenue", {}))
        net_income = [F._annual(ni, y, cum) for y in years]

    quarters = set()
    for r in fs:
        d = datetime.strptime(r["date"][:10], "%Y-%m-%d")
        quarters.add((d.year, (d.month - 1) // 3 + 1))

    p_start = (pick - timedelta(days=150)).isoformat()
    prices = cached(f"pick_px_{sid}_{p_start}_{end}", lambda: fetch("TaiwanStockPrice", sid, p_start, end)) or []
    valuation = F.get_valuation(sid, pick.isoformat()) or {}
    return fin, net_income, quarters, prices, valuation


def price_stats(prices):
    if not prices:
        return None, None, None, None
    df = pd.DataFrame(prices)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date")
    df = df[df["close"] > 0]
    money = df["Trading_money"].tail(MONEY_DAYS).mean() if "Trading_money" in df else None
    rets = df["close"].pct_change().dropna().tail(VOL_DAYS)
    vol = rets.std() * math.sqrt(252) * 100 if len(rets) >= 20 else None
    last = df.iloc[-1]
    return money, vol, round(float(last["close"]), 2), last["date"].strftime("%Y-%m-%d")


def avg(xs, partial=False):
    vals = [x for x in xs if x is not None]
    if not vals or (not partial and len(vals) < len(xs)):
        return None
    return sum(vals) / len(vals)


# ── 主流程 ────────────────────────────────────────
def run(pick: date, etf_id: str):
    etf = get_constituents(etf_id)
    if not etf:
        sys.exit(f"找不到成分股名單 {etf_id}")
    end_year  = last_complete_year(pick)
    need_q    = expected_quarters(pick, N_QUARTERS)
    inds      = industry_map()
    print(f"選股日 {pick}｜母體 {etf_id}（{len(etf['constituents'])} 檔）｜年度 {end_year - N_YEARS + 1}–{end_year}｜"
          f"季度 {need_q[-1][0]}Q{need_q[-1][1]}–{need_q[0][0]}Q{need_q[0][1]}")

    rows = []
    for i, c in enumerate(etf["constituents"], 1):
        sid, name = c["stock_id"], c["name"]
        print(f"  [{i:2d}/{len(etf['constituents'])}] {sid} {name}", end="\r")
        fin, ni, quarters, prices, val = stock_data(sid, pick, end_year)
        money, vol, close, close_date = price_stats(prices)
        is_fin = bool(fin and fin.get("is_financial"))

        r = {"stock_id": sid, "name": name, "industry": inds.get(sid, "其他"), "is_financial": is_fin,
             "avg_money_20d": money, "volatility_60d": vol, "last_close": close, "last_close_date": close_date,
             "exclude": [], "warn": [], "na": [], "missing": []}

        # 指標數值（3 年平均；估值取選股日前一交易日）
        for key, label, *_ in INDICATORS:
            if is_fin and key in FINANCIAL_NA:
                r[key] = None
                r["na"].append(label)
                continue
            if key in ("per", "pbr", "dividend_yield"):
                v = val.get(key)
            else:
                v = avg((fin or {}).get(key) or [None] * N_YEARS, partial=key in PARTIAL_OK)
            r[key] = v
            if v is None and not (key == "per" and val):          # 本益比虧損時沒有數值，不算缺漏
                r["missing"].append(label)

        # 第一階段
        miss_q = [q for q in need_q if q not in quarters]
        if not fin:
            r["exclude"].append("抓不到財報")
        else:
            if r["missing"]:
                r["exclude"].append("資料缺漏：" + "、".join(r["missing"]))
            if miss_q:
                r["exclude"].append("缺季報：" + "、".join(f"{y}Q{q}" for y, q in miss_q))
            if sum(1 for x in ni if x is None) > 0:
                r["exclude"].append("稅後淨利資料不足 3 年")
            elif sum(1 for x in ni if x < 0) >= 2:
                r["exclude"].append("最近 3 年有 2 年以上虧損")
        if money is None:
            r["exclude"].append("無成交資料")
        elif money < MIN_MONEY:
            r["exclude"].append(f"20 日均成交金額 {money / 1e8:.2f} 億 < 0.3 億")
        r["stage1"] = not r["exclude"]
        rows.append(r)
    print()

    df = pd.DataFrame(rows)
    s1 = df[df["stage1"]].copy()

    # 第二階段：同產業百分位（0–100，越好越高）
    for key, label, dim, w, higher in INDICATORS:
        s1[f"p_{key}"] = s1.groupby("industry")[key].rank(pct=True, ascending=higher) * 100

    def dim_score(row, dim, weights=None):
        tot = ws = 0.0
        for key, label, d, w, higher in INDICATORS:
            if d != dim:
                continue
            w = (weights or {}).get(key, w)
            p = row.get(f"p_{key}")
            if p is None or pd.isna(p):
                continue
            tot += p * w
            ws += w
        return tot / ws if ws else None

    for dim in DIMENSIONS:
        s1[dim] = s1.apply(lambda r: dim_score(r, dim), axis=1)

    def total(row):
        tot = ws = 0.0
        for dim, w in DIMENSIONS.items():
            if row[dim] is not None and not pd.isna(row[dim]):
                tot += row[dim] * w
                ws += w
        return tot / ws if ws else None

    s1["總分"] = s1.apply(total, axis=1)
    s1["穩健價值分數"] = s1[["財務穩健", "價值評估"]].mean(axis=1, skipna=True)

    # 第三階段：波動率百分位（母體 = 通過第一階段的股票）
    s1["vol_pct"] = s1["volatility_60d"].rank(pct=True) * 100
    for i, r in s1.iterrows():
        if pd.notna(r["vol_pct"]) and r["vol_pct"] > VOL_EXCLUDE:
            s1.at[i, "exclude"] = r["exclude"] + [f"波動率 {r['volatility_60d']:.1f}%（第 {r['vol_pct']:.0f} 百分位）"]
        elif pd.notna(r["vol_pct"]) and r["vol_pct"] > VOL_WARN:
            s1.at[i, "warn"] = r["warn"] + [f"波動率偏高 {r['volatility_60d']:.1f}%（第 {r['vol_pct']:.0f} 百分位）"]
    s1["stage3"] = s1["exclude"].apply(lambda x: not x)

    # 第四階段：總分排序
    final = s1[s1["stage3"]].sort_values("總分", ascending=False)
    final["rank"] = range(1, len(final) + 1)
    top = final.head(3)

    # 輸出
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "picks")
    os.makedirs(out_dir, exist_ok=True)
    tag = pick.isoformat()

    all_rows = df.merge(s1[["stock_id"] + list(DIMENSIONS) + ["總分", "穩健價值分數", "vol_pct", "stage3", "exclude", "warn"]
                           + [f"p_{k}" for k, *_ in INDICATORS]],
                        on="stock_id", how="left", suffixes=("_s1", ""))
    all_rows["exclude"] = all_rows["exclude"].where(all_rows["exclude"].notna(), all_rows["exclude_s1"])
    all_rows["warn"] = all_rows["warn"].where(all_rows["warn"].notna(), all_rows["warn_s1"])
    all_rows = all_rows.merge(final[["stock_id", "rank"]], on="stock_id", how="left").sort_values(["rank", "stock_id"])
    for col in ("exclude", "warn", "na"):
        all_rows[col] = all_rows[col].apply(lambda x: "；".join(x) if isinstance(x, list) else "")
    all_rows.drop(columns=["exclude_s1", "warn_s1", "missing"], errors="ignore") \
            .to_csv(os.path.join(out_dir, f"scores_{tag}.csv"), index=False, encoding="utf-8-sig")

    def reason(r):
        best = sorted(((r[d], d) for d in DIMENSIONS if pd.notna(r[d])), reverse=True)
        parts = [f"總分 {r['總分']:.1f}（第 {int(r['rank'])} 名）",
                 "構面分數：" + "、".join(f"{d} {r[d]:.0f}" for d in DIMENSIONS if pd.notna(r[d])),
                 f"最強構面：{best[0][1]}"]
        top_ind = sorted(((r[f"p_{k}"], lab, r[k]) for k, lab, *_ in INDICATORS if pd.notna(r.get(f"p_{k}"))),
                         reverse=True)[:3]
        parts.append("同產業（" + r["industry"] + "）領先指標：" +
                     "、".join(f"{lab} {v:.2f}（第 {p:.0f} 百分位）" for p, lab, v in top_ind))
        if r["warn"]:
            parts.append("風險提醒：" + "；".join(r["warn"]))
        return "；".join(parts)

    picks = []
    for _, r in top.iterrows():
        picks.append({
            "rank": int(r["rank"]), "stock_id": r["stock_id"], "name": r["name"], "industry": r["industry"],
            "total_score": round(r["總分"], 2),
            "scores": {d: (round(r[d], 2) if pd.notna(r[d]) else None) for d in DIMENSIONS},
            "stable_value_score": round(r["穩健價值分數"], 2) if pd.notna(r["穩健價值分數"]) else None,
            "volatility_60d": round(r["volatility_60d"], 2) if pd.notna(r["volatility_60d"]) else None,
            "reference_close": r["last_close"], "reference_close_date": r["last_close_date"],
            "pick_date_close": None,
            "reason": reason(r),
            "mops_news": f"https://mops.twse.com.tw/mops/#/web/t05st01?companyId={r['stock_id']}",
        })

    result = {
        "pick_date": tag, "universe": etf_id, "fiscal_years": [end_year - N_YEARS + 1, end_year],
        "rules": {"min_avg_money_20d": MIN_MONEY, "vol_exclude_pct": VOL_EXCLUDE, "vol_warn_pct": VOL_WARN,
                  "weights": {d: w for d, w in DIMENSIONS.items()},
                  "indicator_weights": {lab: w for _, lab, _, w, _ in INDICATORS}},
        "counts": {"universe": len(df), "stage1_passed": int(df["stage1"].sum()),
                   "stage3_passed": int(s1["stage3"].sum())},
        "picks": picks,
        "note": "選股日收盤價（pick_date_close）於收盤後執行 --fill-close 補上；重大訊息請點 mops_news 人工檢查選股日前 30 日。",
    }
    path = os.path.join(out_dir, f"picks_{tag}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 螢幕輸出
    print(f"\n第一階段通過 {result['counts']['stage1_passed']} / {len(df)} 檔，第三階段通過 {result['counts']['stage3_passed']} 檔")
    ex = df[~df["stage1"]]
    if len(ex):
        print("\n第一階段排除：")
        for _, r in ex.iterrows():
            print(f"  {r['stock_id']} {r['name']}：{'；'.join(r['exclude'])}")
    ex3 = s1[~s1["stage3"]]
    if len(ex3):
        print("\n第三階段排除：")
        for _, r in ex3.iterrows():
            print(f"  {r['stock_id']} {r['name']}：{'；'.join(r['exclude'])}")
    print("\n總分前 10 名：")
    print(final.head(10)[["rank", "stock_id", "name", "industry", "總分"] + list(DIMENSIONS) + ["穩健價值分數"]]
          .round(1).to_string(index=False))
    print("\n★ 入選三檔")
    for p in picks:
        print(f"  {p['rank']}. {p['stock_id']} {p['name']}（參考收盤 {p['reference_close']}，{p['reference_close_date']}）")
        print(f"     {p['reason']}")
        print(f"     重大訊息檢查：{p['mops_news']}")
    print(f"\n已存檔：{path}")


def fill_close(pick: date):
    """收盤後補上選股日當天收盤價"""
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "picks")
    path = os.path.join(out_dir, f"picks_{pick.isoformat()}.json")
    with open(path, encoding="utf-8") as f:
        result = json.load(f)
    for p in result["picks"]:
        rows = fetch("TaiwanStockPrice", p["stock_id"], pick.isoformat(), pick.isoformat())
        p["pick_date_close"] = float(rows[0]["close"]) if rows else None
        print(f"{p['stock_id']} {p['name']} {pick} 收盤 {p['pick_date_close']}")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default="2026-11-09")
    ap.add_argument("--etf", default="0050@2026-10-16")
    ap.add_argument("--fill-close", action="store_true", help="收盤後補選股日收盤價")
    a = ap.parse_args()
    d = datetime.strptime(a.date, "%Y-%m-%d").date()
    fill_close(d) if a.fill_close else run(d, a.etf)
