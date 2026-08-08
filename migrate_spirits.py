#!/usr/bin/env python3
"""spirits.csv を spirits-data/ の日別CSVに分割移行し、all.csv / dates.json を生成する。

一回限りの移行スクリプト。冪等(再実行すると同じ結果に上書き)。
"""
import csv
import sys
from collections import defaultdict

import spirits_store

SOURCE = "spirits.csv"


def main():
    by_date = defaultdict(list)
    total = 0
    with open(SOURCE, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if not row:
                continue
            if len(row) < 4:
                print(f"不正な行をスキップ: {row}", file=sys.stderr)
                continue
            by_date[row[0]].append(row)
            total += 1

    for date_str, rows in sorted(by_date.items()):
        spirits_store.save_daily(date_str, rows)
    print(f"日別CSV: {len(by_date)} ファイルに {total} 件を分割")

    agg_total, all_rows = spirits_store.rebuild_all()

    # 整合性チェック
    ok = True
    if agg_total != total:
        print(f"NG: 日別CSVの合計 {agg_total} 件 != 元データ {total} 件", file=sys.stderr)
        ok = False
    daily_total = sum(len(spirits_store.load_daily(d)) for d in spirits_store.list_dates())
    if daily_total != total:
        print(f"NG: 再読込した日別CSVの合計 {daily_total} 件 != 元データ {total} 件", file=sys.stderr)
        ok = False
    count_sum = 0
    with open(spirits_store.DATA_DIR + "/all.csv", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            count_sum += int(row[4])
    if count_sum != total:
        print(f"NG: all.csv の出現回数合計 {count_sum} 件 != 元データ {total} 件", file=sys.stderr)
        ok = False

    print(f"all.csv: {all_rows} 行(出現回数合計 {count_sum} 件)")
    print("整合性チェック: " + ("OK" if ok else "NG"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
