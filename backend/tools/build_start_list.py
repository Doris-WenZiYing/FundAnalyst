"""
build_start_list.py — 由「期末成分股名單」反推「研究開始日的成分股名單」

為什麼需要：0050 每季換股。用期末名單回測年初開始的績效，會納入「漲了之後才被加入」的股票，
報酬率會被高估（look-ahead / survivorship bias）。論文做法是用投資開始前的名單。

做法：從期末名單開始，依時間倒序把每次審核「撤銷」——刪掉當次納入的、加回當次刪除的，
只撤銷 effective 日期在 start 之後（含）的異動。

用法（在 backend/ 底下）：
    python tools/build_start_list.py 0050 2026-01-01
會讀取 data/etf_constituents.json 裡日期最新的 "0050@日期" 當作期末名單，
寫回：
    "0050"            → 研究開始日名單（排序、篩選預設用這份）
    "0050@<期末日期>"  → 期末名單（保留做對照）
"""

import argparse
import json
import os
import sys

BASE      = os.path.join(os.path.dirname(__file__), "..", "data")
DATA_PATH = os.path.join(BASE, "etf_constituents.json")


def rebuild(end_list, changes, start):
    """end_list：[{stock_id, name, weight}]；回傳 (start_list, applied_reviews)"""
    current = {c["stock_id"]: dict(c) for c in end_list}
    applied = []
    for ch in sorted(changes, key=lambda c: c["effective"], reverse=True):
        if ch["effective"] < start:
            continue
        for sid, _ in ch["added"]:
            if sid not in current:
                raise ValueError(f"{ch['review']} 納入的 {sid} 不在名單裡，期末名單或異動資料有誤")
            del current[sid]
        for sid, name in ch["removed"]:
            current[sid] = {"stock_id": sid, "name": name, "weight": None}
        applied.append(ch["review"])
    # 年初權重未知（名單是反推的），統一清空，避免誤用期末權重
    out = [{"stock_id": c["stock_id"], "name": c["name"], "weight": None} for c in current.values()]
    return sorted(out, key=lambda c: c["stock_id"]), applied


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("etf_id")
    p.add_argument("start", help="研究開始日，例如 2026-01-01")
    p.add_argument("--data", default=DATA_PATH)
    p.add_argument("--changes", default=None)
    a = p.parse_args(argv)

    changes_path = a.changes or os.path.join(BASE, f"index_changes_{a.etf_id}.json")
    with open(a.data, encoding="utf-8") as f:
        data = json.load(f)
    with open(changes_path, encoding="utf-8") as f:
        changes = json.load(f)["changes"]

    # 期末名單 = 日期最新的「代號@日期」；沒有的話退回「代號」（舊版匯入方式）
    dated = [k for k in data if k.startswith(f"{a.etf_id}@") and data[k].get("as_of")]
    end_key = max(dated, key=lambda k: data[k]["as_of"]) if dated else a.etf_id
    if end_key not in data:
        sys.exit(f"找不到 {a.etf_id} 的名單，請先用 import_constituents.py 匯入")
    end = data[end_key]
    if not end.get("as_of"):
        sys.exit("期末名單沒有 as_of 日期，請先用 import_constituents.py --as-of 匯入")

    try:
        start_list, applied = rebuild(end["constituents"], changes, a.start)
    except ValueError as e:
        sys.exit(f"{e}\n（使用的期末名單：{end_key}，{len(end['constituents'])} 檔。請確認匯入的 CSV 是完整名單）")
    base_name = end["name"].split("（")[0]

    if end_key != f"{a.etf_id}@{end['as_of']}":
        data.pop(end_key, None)               # 舊版格式（存在「代號」底下）搬到「代號@日期」
    data[f"{a.etf_id}@{end['as_of']}"] = {**end, "name": f"{base_name}（{end['as_of']} 期末名單，僅供對照）",
                                          "benchmark_id": a.etf_id}
    data[a.etf_id] = {
        "name":         base_name,
        "as_of":        a.start,
        "source":       f"由 {end['as_of']} 名單反推（撤銷 {'、'.join(applied)}）",
        "benchmark_id": a.etf_id,
        "constituents": start_list,
    }
    with open(a.data, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    end_ids, start_ids = {c["stock_id"] for c in end["constituents"]}, {c["stock_id"] for c in start_list}
    print(f"年初名單 {len(start_list)} 檔（撤銷：{'、'.join(applied)}）")
    print("期末有、年初沒有：", sorted(end_ids - start_ids))
    print("年初有、期末沒有：", sorted(start_ids - end_ids))


if __name__ == "__main__":
    main()
