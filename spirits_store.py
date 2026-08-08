#!/usr/bin/env python3
"""精霊データの日別CSVと集計ファイル(all.csv / dates.json)の共通処理。

ディレクトリ構成:
  spirits-data/YYYYMM/YYYYMMDD.csv  日別データ(日付,名前,緯度,経度)
  spirits-data/all.csv              集計(アドレス,名前,緯度,経度,出現回数,最新出現日)
  spirits-data/dates.json           存在する日付の降順配列("YYYY/MM/DD")
"""
import csv
import json
import os
import re

import geohex

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "spirits-data")
DAILY_HEADER = ["日付", "名前", "緯度", "経度"]
ELEMENT_NAMES = ["炎の精霊", "水の精霊", "風の精霊", "大地の精霊"]
ALL_HEADER = ["アドレス", "緯度", "経度", "最新の出現日", "炎", "水", "風", "大地"]
GEOHEX_LEVEL = 6


def daily_path(date_str):
    """"2026/04/12" → spirits-data/202604/20260412.csv"""
    ymd = date_str.replace("/", "")
    if not re.fullmatch(r"\d{8}", ymd):
        raise ValueError(f"不正な日付: {date_str}")
    return os.path.join(DATA_DIR, ymd[:6], ymd + ".csv")


def load_daily(date_str):
    """日別CSVのレコードをリストで返す(ヘッダー行は除く)。無ければ空リスト。"""
    rows = []
    try:
        with open(daily_path(date_str), newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    rows.append(row)
    except FileNotFoundError:
        pass
    return rows


def save_daily(date_str, rows):
    path = daily_path(date_str)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(DAILY_HEADER)
        writer.writerows(rows)


def list_dates():
    """日別CSVが存在する日付("YYYY/MM/DD")を昇順で返す。"""
    dates = []
    if not os.path.isdir(DATA_DIR):
        return dates
    for month_dir in os.listdir(DATA_DIR):
        if not re.fullmatch(r"\d{6}", month_dir):
            continue
        for name in os.listdir(os.path.join(DATA_DIR, month_dir)):
            m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})\.csv", name)
            if m:
                dates.append(f"{m.group(1)}/{m.group(2)}/{m.group(3)}")
    return sorted(dates)


def rebuild_all():
    """全日別CSVから all.csv と dates.json を再生成する。

    集計単位は GeoHex Lv6 アドレス(1セル1行)。緯度経度はセル中心。
    炎・水・風・大地の各列に精霊ごとの出現回数を持つ。
    戻り値: (全レコード数, all.csv の行数)
    """
    dates = list_dates()
    agg = {}  # code -> [center_lat, center_lon, {名前: 回数}, latest_date]
    total = 0
    for date_str in dates:
        for row in load_daily(date_str):
            if len(row) < 4:
                continue
            try:
                lat, lng = float(row[2]), float(row[3])
            except ValueError:
                continue
            total += 1
            code, clat, clon = geohex.encode(lat, lng, GEOHEX_LEVEL)
            if code not in agg:
                agg[code] = [clat, clon, {}, row[0]]
            cell = agg[code]
            cell[2][row[1]] = cell[2].get(row[1], 0) + 1
            if row[0] > cell[3]:
                cell[3] = row[0]

    with open(os.path.join(DATA_DIR, "all.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(ALL_HEADER)
        for code, (clat, clon, counts, latest) in sorted(agg.items()):
            writer.writerow([code, f"{clat:.6f}", f"{clon:.6f}", latest]
                            + [counts.get(n, 0) for n in ELEMENT_NAMES])

    with open(os.path.join(DATA_DIR, "dates.json"), "w", encoding="utf-8") as f:
        json.dump(list(reversed(dates)), f, ensure_ascii=False, indent=0)
        f.write("\n")

    return total, len(agg)
