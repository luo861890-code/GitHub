# -*- coding: utf-8 -*-
"""本地地理数据优化：米制 Douglas-Peucker 几何简化（视觉无损，减小数据体量）

在局部等距投影下按米制 tolerance 简化（WGS84 → 投影 → 米制简化 → 回投影），
避免直接在经纬度上以度值近似米数。容差按要素类型与尺度设置。
"""
import json
import os

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.utils.geo_simplify import simplify_coords_meters, simplify_geometry_meters

GEO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo")

# (文件名, 简化容差(米)) —— 按要素类型与尺度设置
PLANS = [
    ("wuhan_roads.geojson", 20.0),
    # 水系用更小容差（10m）：保留自然河湖微弯，避免"笔直长段"假象
    ("wuhan_water.geojson", 10.0),
    ("wuhan_transit.geojson", 20.0),
    ("hubei_cities.geojson", 30.0),
    ("wuhan_districts.geojson", 30.0),
]


def simplify_coords(coords, tol):
    """对 [lng,lat] 点序列做米制 Douglas-Peucker 简化"""
    return simplify_coords_meters(coords, tol, preserve_topology=True)


def simplify_geometry(geom, tol):
    """对 GeoJSON 几何做米制简化"""
    return simplify_geometry_meters(geom, tol, preserve_topology=True)


def main():
    total_before = 0
    total_after = 0
    for fname, tol in PLANS:
        path = os.path.join(GEO, fname)
        if not os.path.exists(path):
            print(f"跳过（不存在）: {fname}")
            continue
        d = json.load(open(path, encoding="utf-8"))
        feats = d.get("features", [])
        before = os.path.getsize(path)
        for f in feats:
            g = f.get("geometry") or {}
            gtype = g.get("type", "")
            if gtype in ("LineString", "Polygon", "MultiPolygon"):
                f["geometry"] = simplify_geometry(g, tol)
        out = os.path.join(GEO, fname)
        with open(out, "w", encoding="utf-8") as fh:
            json.dump({"type": "FeatureCollection", "features": feats}, fh, ensure_ascii=False)
        after = os.path.getsize(out)
        total_before += before
        total_after += after
        print(f"{fname}: {before/1e6:.1f}MB -> {after/1e6:.1f}MB ({100*(1-after/before):.0f}% 减小)")
    print(f"合计: {total_before/1e6:.1f}MB -> {total_after/1e6:.1f}MB")


if __name__ == "__main__":
    main()
