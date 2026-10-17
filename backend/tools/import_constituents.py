"""
import_constituents.py — 把 ETF 成分股 CSV 匯入 data/etf_constituents.json

用法（在 backend/ 底下執行）：
    python tools/import_constituents.py 0050 "元大台灣50" path/to/0050.csv --as-of 2026-10-08

CSV 格式（第一列是標題，欄名中英文都可以）：
    代號,名稱,權重
    2330,台積電,55.12
    2454,聯發科,4.31
    ...

權重可省略或留空；有 % 符號也沒關係。
可以從元大投信官網或玩股網的成分股表格複製到 Excel，另存成 CSV（UTF-8）。

研究設計採「固定成分股」（論文 3.5.1），所以匯入一次、記下 as_of 日期即可，
不需要每天更新。
"""

import argparse
import csv
import json
import os
import sys

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "etf_constituents.json")

ID_KEYS     = {"代號", "股票代號", "證券代號", "stock_id", "code"}
NAME_KEYS   = {"名稱", "股票名稱", "證券名稱", "name"}
WEIGHT_KEYS = {"權重", "持股權重", "比例", "weight"}


def _pick(row: dict, keys: set):
    for k, v in row.items():
        if k and k.strip().lower() in {x.lower() for x in keys}:
            return (v or "").strip()
    return ""


def parse_csv(path: str) -> list:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        sid = _pick(row, ID_KEYS)
        if not sid:
            continue
        sid = sid.split(".")[0].strip()           # 2330.TW → 2330
        w   = _pick(row, WEIGHT_KEYS).replace("%", "").replace(",", "")
        out.append({
            "stock_id": sid,
            "name":     _pick(row, NAME_KEYS),
            "weight":   float(w) if w else None,
        })
    return out


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("etf_id")
    p.add_argument("etf_name")
    p.add_argument("csv_path")
    p.add_argument("--as-of", default=None, help="成分股名單日期，例如 2026-10-08")
    p.add_argument("--data", default=DATA_PATH)
    a = p.parse_args(argv)

    constituents = parse_csv(a.csv_path)
    if not constituents:
        sys.exit("CSV 裡沒有讀到任何股票代號，請確認標題列有「代號」欄")

    data = {}
    if os.path.exists(a.data):
        with open(a.data, encoding="utf-8") as f:
            data = json.load(f)

    data[a.etf_id] = {
        "name":         a.etf_name,
        "as_of":        a.as_of,
        "source":       os.path.basename(a.csv_path),
        "constituents": constituents,
    }
    with open(a.data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"已匯入 {a.etf_id} {a.etf_name}：{len(constituents)} 檔")


if __name__ == "__main__":
    main()
