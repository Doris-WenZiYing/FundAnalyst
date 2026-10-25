"""
verify_data.py — 把系統算出的數字印出來，方便跟外部網站人工比對

用法（在 backend/ 底下）：
    python tools/verify_data.py 2330 2317 0050 --start 2026-01-01 --end 2026-10-16
    python tools/verify_data.py 2330 2881 --fin 2025

股價比對：
  - 「Yahoo 還原」的期間報酬 ≈ 股票網站的「含息報酬」
  - 「FinMind 收盤」的期間報酬 ≈ Yahoo 股市頁面上顯示的漲跌幅（未含息）
財報比對（--fin 年份）：
  - 跟 Goodinfo / 財報狗的年度 ROE、EPS、毛利率比對
  - ROE、ROA 這裡用「平均權益／平均總資產」計算，各網站算法不同，差 1～2 個百分點屬正常
  - 也會印出 --fin 隔年 1/1 前最後一個交易日的本益比、股價淨值比、殖利率
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from stock_data import _fetch_yahoo, _fetch_finmind          # noqa: E402
from financials import get_fundamentals, get_valuation        # noqa: E402


def _ret(s):
    if s is None or len(s) < 2:
        return "—"
    return (f"{s.index[0].date()} {s.iloc[0]:>9.2f} → {s.index[-1].date()} {s.iloc[-1]:>9.2f}"
            f"   {(s.iloc[-1] / s.iloc[0] - 1) * 100:+7.2f}%")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("stock_ids", nargs="+")
    p.add_argument("--start", default=None)
    p.add_argument("--end", default=None)
    p.add_argument("--fin", type=int, default=None, help="財報最後一年，例如 2025")
    a = p.parse_args()

    if a.start and a.end:
        print(f"\n股價（{a.start} ～ {a.end}）")
        for sid in a.stock_ids:
            print(f"\n[{sid}]")
            print("  Yahoo 還原   ", _ret(_fetch_yahoo(sid, a.start, a.end)))
            print("  FinMind 收盤 ", _ret(_fetch_finmind("TaiwanStockPrice", sid, a.start, a.end)))

    if a.fin:
        print(f"\n財報（{a.fin - 4}～{a.fin}）")
        for sid in a.stock_ids:
            f = get_fundamentals(sid, a.fin)
            print(f"\n[{sid}]", "抓不到財報" if not f else
                  f"金融股={f['is_financial']}  累計數格式={f['cumulative']}")
            if not f:
                continue
            cols = [("ROE%", "roe"), ("ROA%", "roa"), ("EPS", "eps"), ("毛利%", "gross_margin"),
                    ("營益%", "operating_margin"), ("淨利%", "net_margin"), ("負債%", "debt_ratio"),
                    ("流動%", "current_ratio"), ("營收成長%", "revenue_growth"), ("EPS成長%", "eps_growth")]
            fmt = lambda v: f"{v:>9.2f}" if v is not None else "        —"
            print("  年度 " + "".join(f"{c:>9}" for c, _ in cols))
            for i, y in enumerate(f["years"]):
                print(f"  {y} " + "".join(fmt(f.get(k, [None] * 5)[i]) for _, k in cols))
            v = get_valuation(sid, f"{a.fin + 1}-01-01")
            if v:
                print(f"  {v['date']} 本益比 {v['per']}  股價淨值比 {v['pbr']}  殖利率 {v['dividend_yield']}%")

    if not (a.start and a.end) and not a.fin:
        p.error("請至少給 --start/--end 或 --fin")


if __name__ == "__main__":
    main()
