#!/usr/bin/env python3
import re
import json
import sys
import os
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

import spirits_store

URL = os.environ.get("SPIRITS_URL")
if not URL:
    print("環境変数 SPIRITS_URL が設定されていません", file=sys.stderr)
    sys.exit(1)
JST = timezone(timedelta(hours=9))
TARGET_NAMES = {"炎の精霊", "水の精霊", "風の精霊", "大地の精霊"}


def fetch_page(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as res:
        return res.read().decode("utf-8")


def extract_flat_spots(html):
    match = re.search(r'var\s+flatSpots\s*=\s*(\[.*?\]);', html, re.DOTALL)
    if not match:
        print("flatSpots が見つかりませんでした", file=sys.stderr)
        sys.exit(1)
    return json.loads(match.group(1))


def to_date(unix_ts):
    return datetime.fromtimestamp(int(unix_ts), tz=JST).strftime("%Y/%m/%d")


def main():
    print(f"取得中: {URL}")
    html = fetch_page(URL)
    spots = extract_flat_spots(html)
    print(f"スポット数: {len(spots)}")

    spots_by_date = defaultdict(list)
    for spot in spots:
        start_time = spot.get("start_time")
        date_str = to_date(start_time) if start_time else ""
        spots_by_date[date_str].append(spot)

    total_new = 0
    total_deleted = 0
    for date_str, day_spots in sorted(spots_by_date.items()):
        if not date_str:
            continue
        existing_rows = spirits_store.load_daily(date_str)

        # 「出現なし」の (緯度, 経度) を収集し、既存レコードから該当行を削除
        none_keys = set()
        for spot in day_spots:
            names = [c.get("name", "") for c in spot.get("contents", [])]
            if "出現なし" in names:
                none_keys.add((str(spot.get("lat")), str(spot.get("lng"))))
        filtered_rows = [r for r in existing_rows if (r[2], r[3]) not in none_keys]
        deleted = len(existing_rows) - len(filtered_rows)

        # 新規レコードを追記
        new_rows = []
        current_keys = {tuple(r) for r in filtered_rows}
        for spot in day_spots:
            lat = spot.get("lat")
            lng = spot.get("lng")
            for content in spot.get("contents", []):
                name = content.get("name", "")
                if name in TARGET_NAMES:
                    key = (date_str, name, str(lat), str(lng))
                    if key not in current_keys:
                        new_rows.append([date_str, name, lat, lng])
                        current_keys.add(key)

        all_rows = filtered_rows + new_rows
        all_rows.sort(key=lambda r: (r[0], r[1]))
        if deleted or new_rows:
            spirits_store.save_daily(date_str, all_rows)

        if deleted:
            print(f"{date_str} 削除（出現なし）: {deleted} 件")
        print(f"{date_str} 新規追記: {len(new_rows)} 件（合計 {len(all_rows)} 件）")
        for r in new_rows[:5]:
            print(" ", ",".join(str(x) for x in r))
        if len(new_rows) > 5:
            print(f"  ... 他 {len(new_rows)-5} 件")
        total_new += len(new_rows)
        total_deleted += deleted

    if total_new or total_deleted:
        total, all_rows_count = spirits_store.rebuild_all()
        print(f"all.csv 更新: {all_rows_count} 行（全 {total} 件） / dates.json 更新")
    else:
        print("（新規データなし・all.csv 更新スキップ）")


if __name__ == "__main__":
    main()
