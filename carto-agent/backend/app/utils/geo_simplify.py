# -*- coding: utf-8 -*-
"""米制几何简化：经纬度 → 局部等距投影 → 米制 Douglas-Peucker → 回投影

解决“直接在经纬度上以度值近似米数”的单位体系问题。
对武汉范围（跨约 1.5° 经度）误差可忽略；对多城市扩展可替换为严格 UTM/CGCS2000 投影。
"""
from typing import List, Tuple

# 地球半径（米），等距投影近似
METERS_PER_DEG_LAT = 110_540.0
METERS_PER_DEG_LNG_EQ = 111_320.0


def _lonlat_to_meters(coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """[lng, lat] -> 局部等距投影米制坐标（以平均纬度为基准）"""
    if not coords:
        return []
    lats = [c[1] for c in coords]
    lat0 = sum(lats) / len(lats)
    import math
    kx = METERS_PER_DEG_LNG_EQ * math.cos(math.radians(lat0))
    return [(c[0] * kx, c[1] * METERS_PER_DEG_LAT) for c in coords]


def _meters_to_lonlat(coords: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """米制坐标 -> [lng, lat]"""
    if not coords:
        return []
    import math
    lat0 = sum(c[1] for c in coords) / len(coords) / METERS_PER_DEG_LAT
    kx = METERS_PER_DEG_LNG_EQ * math.cos(math.radians(lat0))
    return [(c[0] / kx, c[1] / METERS_PER_DEG_LAT) for c in coords]


def simplify_meters(
    coords: List[Tuple[float, float]],
    tolerance_m: float,
    preserve_topology: bool = True,
) -> List[Tuple[float, float]]:
    """对 [lng, lat] 坐标序列做米制 Douglas-Peucker 简化"""
    if len(coords) < 3:
        return list(coords)
    try:
        from shapely.geometry import LineString
    except ImportError:
        return list(coords)
    meters = _lonlat_to_meters(coords)
    line = LineString(meters)
    simple = line.simplify(tolerance_m, preserve_topology=preserve_topology)
    return _meters_to_lonlat(list(simple.coords))


# 别名：脚本侧更直白的命名
simplify_coords_meters = simplify_meters


def simplify_geometry_meters(
    geom: dict,
    tolerance_m: float,
    preserve_topology: bool = True,
) -> dict:
    """对 GeoJSON geometry 做米制简化（LineString/Polygon/MultiPolygon）"""
    try:
        from shapely.geometry import shape, mapping
    except ImportError:
        return geom
    gtype = geom.get("type", "")
    if gtype not in ("LineString", "Polygon", "MultiPolygon", "MultiLineString"):
        return geom
    try:
        g = shape(geom)
        if g.is_empty:
            return geom
        # 重投影到局部等距米制
        simple = _simplify_shapely_meters(g, tolerance_m, preserve_topology)
        return mapping(simple)
    except Exception:
        return geom


def _simplify_shapely_meters(g, tolerance_m: float, preserve_topology: bool = True):
    """在局部等距米制下简化 shapely 几何"""
    from shapely.geometry import LineString, Polygon, MultiPolygon, MultiLineString
    from shapely.ops import transform
    import math
    import functools

    bounds = g.bounds
    lat0 = (bounds[1] + bounds[3]) / 2
    kx = METERS_PER_DEG_LNG_EQ * math.cos(math.radians(lat0))

    def to_meters(x, y, z=None):
        return (x * kx, y * METERS_PER_DEG_LAT)

    def to_deg(x, y, z=None):
        return (x / kx, y / METERS_PER_DEG_LAT)

    g_m = transform(to_meters, g)
    g_s = g_m.simplify(tolerance_m, preserve_topology=preserve_topology)
    return transform(to_deg, g_s)
