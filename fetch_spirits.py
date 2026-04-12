#!/usr/bin/env python3
import re
import json
import csv
import sys
import os
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

URL = os.environ.get("SPIRITS_URL")
if not URL:
    print("環境変数 SPIRITS_URL が設定されていません", file=sys.stderr)
    sys.exit(1)
OUTPUT = "spirits.csv"
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

def load_existing(path):
    """既存CSVのレコードをリストで返す（ヘッダー行は除く）"""
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # ヘッダースキップ
            for row in reader:
                if row:
                    rows.append(row)
    except FileNotFoundError:
        pass
    return rows

def save_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["日付", "名前", "緯度", "経度"])
        writer.writerows(rows)

def main():
    print(f"取得中: {URL}")
    html = fetch_page(URL)
    spots = extract_flat_spots(html)
    print(f"スポット数: {len(spots)}")

    existing_rows = load_existing(OUTPUT)
    print(f"既存レコード数: {len(existing_rows)}")

    existing_keys = {tuple(r) for r in existing_rows}

    # 「出現なし」の (日付, 緯度, 経度) を収集
    none_keys = set()
    for spot in spots:
        lat = spot.get("lat")
        lng = spot.get("lng")
        start_time = spot.get("start_time")
        date_str = to_date(start_time) if start_time else ""
        names = [c.get("name", "") for c in spot.get("contents", [])]
        if "出現なし" in names:
            none_keys.add((date_str, str(lat), str(lng)))

    # 既存レコードから「出現なし」に該当する行を削除
    filtered_rows = [
        r for r in existing_rows
        if (r[0], r[2], r[3]) not in none_keys
    ]
    deleted = len(existing_rows) - len(filtered_rows)

    # 新規レコードを追記
    new_rows = []
    current_keys = {tuple(r) for r in filtered_rows}
    for spot in spots:
        lat = spot.get("lat")
        lng = spot.get("lng")
        start_time = spot.get("start_time")
        date_str = to_date(start_time) if start_time else ""
        for content in spot.get("contents", []):
            name = content.get("name", "")
            if name in TARGET_NAMES:
                key = (date_str, name, str(lat), str(lng))
                if key not in current_keys:
                    new_rows.append([date_str, name, lat, lng])
                    current_keys.add(key)

    new_rows.sort(key=lambda r: (r[0], r[1]))
    all_rows = filtered_rows + new_rows
    save_csv(OUTPUT, all_rows)

    if deleted:
        print(f"削除（出現なし）: {deleted} 件")
    print(f"新規追記: {len(new_rows)} 件 → {OUTPUT}（合計 {len(all_rows)} 件）")
    for r in new_rows[:5]:
        print(" ", ",".join(str(x) for x in r))
    if len(new_rows) > 5:
        print(f"  ... 他 {len(new_rows)-5} 件")
    if not new_rows:
        print("  （新規データなし）")

if __name__ == "__main__":
    main()
