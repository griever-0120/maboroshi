#!/usr/bin/env python3
"""GeoHex v3 エンコーダ。circle-map.html 内のJS実装の移植。

コード文字列がJS実装と完全一致することを前提とするため、
丸め・分岐はJSの挙動(Math.round = floor(x+0.5) など)に合わせている。
"""
import math

BASE = 20037508.34
K = math.tan(math.pi / 6)
CODE_SYMBOLS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _js_round(v):
    return math.floor(v + 0.5)


def calc_hex_size(level):
    return BASE / math.pow(3, level + 3)


def loc2xy(lon, lat):
    x = lon * BASE / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180) * BASE / 180
    return x, y


def xy2loc(x, y):
    lon = x / BASE * 180
    lat = 180 / math.pi * (math.atan(math.exp(y / BASE * math.pi)) * 2 - math.pi / 2)
    return lon, lat


def adjust_xy(x, y, level):
    max_steps = math.pow(3, level + 2)
    steps = abs(x - y)
    if steps == max_steps and x > y:
        return y, x
    if steps > max_steps:
        dif = steps - max_steps
        dif_x = math.floor(dif / 2)
        dif_y = dif - dif_x
        if x > y:
            return y + dif_y + dif_x, x - dif_x - dif_y
        if y > x:
            return y - dif_y - dif_x, x + dif_x + dif_y
    return x, y


def get_xy_by_location(lat, lon, level):
    size = calc_hex_size(level)
    unit_x = 6 * size
    unit_y = 6 * size * K
    mx, my = loc2xy(lon, lat)
    pos_x = (mx + my / K) / unit_x
    pos_y = (my - K * mx) / unit_y
    x0 = math.floor(pos_x)
    y0 = math.floor(pos_y)
    xq = pos_x - x0
    yq = pos_y - y0
    x = _js_round(pos_x)
    y = _js_round(pos_y)
    if yq > -xq + 1:
        if yq < 2 * xq and yq > 0.5 * xq:
            x = x0 + 1
            y = y0 + 1
    elif yq < -xq + 1:
        if yq > 2 * xq - 1 and yq < 0.5 * xq + 0.5:
            x = x0
            y = y0
    return adjust_xy(x, y, level)


def get_cell_center(x, y, level):
    """セル中心の (lat, lon) を返す。"""
    size = calc_hex_size(level)
    unit_x = 6 * size
    unit_y = 6 * size * K
    lat_m = (K * x * unit_x + y * unit_y) / 2
    lon_m = (lat_m - y * unit_y) / K
    lon, lat = xy2loc(lon_m, lat_m)
    return lat, lon


def get_code(x, y, loc_x, level):
    code3x = []
    code3y = []
    mod_x = x
    mod_y = y
    for i in range(level + 3):
        pow3 = math.pow(3, level + 2 - i)
        half = math.ceil(pow3 / 2)
        if mod_x >= half:
            code3x.append(2)
            mod_x -= pow3
        elif mod_x <= -half:
            code3x.append(0)
            mod_x += pow3
        else:
            code3x.append(1)
        if mod_y >= half:
            code3y.append(2)
            mod_y -= pow3
        elif mod_y <= -half:
            code3y.append(0)
            mod_y += pow3
        else:
            code3y.append(1)
        if i == 2 and (loc_x == -180 or loc_x >= 0):
            if (code3x[0] == 2 and code3y[0] == 1
                    and code3x[1] == code3y[1] and code3x[2] == code3y[2]):
                code3x[0] = 1
                code3y[0] = 2
            elif (code3x[0] == 1 and code3y[0] == 0
                    and code3x[1] == code3y[1] and code3x[2] == code3y[2]):
                code3x[0] = 0
                code3y[0] = 1
    code = "".join(str(cx * 3 + cy) for cx, cy in zip(code3x, code3y))
    head = int(code[:3])
    tail = code[3:]
    return CODE_SYMBOLS[head // 30] + CODE_SYMBOLS[head % 30] + tail


def encode(lat, lon, level):
    """(コード文字列, セル中心lat, セル中心lon) を返す。"""
    x, y = get_xy_by_location(lat, lon, level)
    center_lat, center_lon = get_cell_center(x, y, level)
    code = get_code(x, y, center_lon, level)
    return code, center_lat, center_lon
