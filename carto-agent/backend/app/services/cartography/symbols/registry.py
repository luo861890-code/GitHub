# -*- coding: utf-8 -*-
"""SymbolRegistry：统一制图符号注册表（颜色/线宽/填充/优先级/尺度范围/形状）

所有要素符号从注册表取，LLM 不得随机生成颜色。每个符号含 symbol_id / geometry /
color / width / casing / priority / scale_range / shape（点符号形状语义）。
颜色统一取自《cartographic_standards》国标式色系，保持单一来源。
"""
from typing import Any, Dict, Optional

from app.core.cartographic_standards import GB_COLORS


def _sym(
    symbol_id: str,
    geometry: str,
    color_key: str,
    width: float,
    priority: int,
    scale_range: list,
    casing: Optional[str] = None,
    shape: str = "",
) -> Dict[str, Any]:
    """构造符号记录，颜色从国标色系取。"""
    return {
        "symbol_id": symbol_id,
        "geometry": geometry,
        "color": GB_COLORS.get(color_key, "#888888"),
        "color_key": color_key,
        "width": width,
        "casing": casing,
        "priority": priority,
        "scale_range": scale_range,
        "shape": shape,
    }


SYMBOLS: Dict[str, Dict[str, Any]] = {
    # 行政
    "boundary.province": _sym("boundary.province", "line", "boundary_national", 1.2, 90, [25000, 1000000]),
    "boundary.city": _sym("boundary.city", "line", "boundary_city", 3.0, 95, [25000, 1000000]),
    "boundary.district": _sym("boundary.district", "line", "boundary_district", 1.2, 85, [25000, 1000000]),
    # 交通
    "road.motorway": _sym("road.motorway", "line", "road_motorway", 4.0, 80, [25000, 1000000], casing="#7C2D12"),
    "road.trunk": _sym("road.trunk", "line", "road_trunk", 3.2, 75, [25000, 1000000], casing="#92400E"),
    "road.primary": _sym("road.primary", "line", "road_primary", 2.5, 70, [25000, 500000]),
    "road.secondary": _sym("road.secondary", "line", "road_secondary", 2.0, 60, [25000, 250000]),
    "road.minor": _sym("road.minor", "line", "road_minor", 1.0, 40, [25000, 100000]),
    "railway.main": _sym("railway.main", "line", "railway", 2.0, 80, [25000, 1000000]),
    "metro.line": _sym("metro.line", "line", "metro", 2.5, 80, [25000, 1000000]),
    "bridge.major": _sym("bridge.major", "line", "road_motorway", 3.0, 90, [25000, 1000000]),
    "hub.transport": _sym("hub.transport", "point", "transport_hub", 2.0, 70, [25000, 1000000], shape="square"),
    # 水系 / 自然
    "water.river": _sym("water.river", "line", "water_line", 1.8, 50, [25000, 1000000]),
    "water.lake": _sym("water.lake", "polygon", "water_contour", 0.8, 45, [25000, 1000000]),
    # 旅游 / 地势
    "poi.attraction": _sym("poi.attraction", "point", "core_landmark", 1.0, 50, [25000, 500000], shape="star"),
    "terrain.contour": _sym("terrain.contour", "line", "contour_index", 1.0, 30, [25000, 500000]),
    "terrain.peak": _sym("terrain.peak", "point", "peak", 1.0, 40, [25000, 500000], shape="triangle"),
}


def get_symbol(symbol_id: str) -> Optional[Dict[str, Any]]:
    """按 symbol_id 取符号；不存在返回 None（不自动生成）"""
    s = SYMBOLS.get(symbol_id)
    return dict(s) if s else None


def resolve_symbol(category: str, feature_class: str = "") -> Optional[Dict[str, Any]]:
    """按 (category, feature_class) 解析符号；无匹配返回 None，禁止 LLM 随机生成"""
    mapping = {
        ("admin", "boundary"): "boundary.district",
        ("road", "motorway"): "road.motorway",
        ("road", "trunk"): "road.trunk",
        ("road", "primary"): "road.primary",
        ("road", "secondary"): "road.secondary",
        ("road", "minor"): "road.minor",
        ("railway", "main"): "railway.main",
        ("metro", "line"): "metro.line",
        ("bridge", "major"): "bridge.major",
        ("hub", "transport"): "hub.transport",
        ("water", "river"): "water.river",
        ("water", "lake"): "water.lake",
        ("poi", "attraction"): "poi.attraction",
        ("terrain", "contour"): "terrain.contour",
        ("terrain", "peak"): "terrain.peak",
    }
    sid = mapping.get((category, feature_class))
    return get_symbol(sid) if sid else None


def resolve_by_category(category: str, geometry: str = "") -> Optional[Dict[str, Any]]:
    """按 CartographicProfile 的 LAYER_CATEGORY 类别解析符号。

    geometry 取值：polyline/line → 线符号；polygon/area → 面符号；
    circleMarker/marker/point → 点符号。
    无匹配返回 None（禁止随机配色）。
    """
    mapping = {
        "admin_boundary": "boundary.city",
        "district_boundary": "boundary.district",
        "street_boundary": "boundary.district",
        "motorway": "road.motorway",
        "trunk_road": "road.trunk",
        "primary_road": "road.primary",
        "secondary_road": "road.secondary",
        "minor_road": "road.minor",
        "metro": "metro.line",
        "railway": "railway.main",
        "bridge": "bridge.major",
        "transit_station": "hub.transport",
        "major_water": None,   # 水系按几何类型细分（线=河流，面=湖泊）
        "minor_water": "water.river",
        "core_poi": "poi.attraction",
        "normal_poi": "poi.attraction",
        "service_poi": "poi.attraction",
        "contour_major": "terrain.contour",
        "contour_minor": "terrain.contour",
        "peak": "terrain.peak",
    }
    sid = mapping.get(category)
    if category in ("major_water",):
        if geometry in ("polygon", "area"):
            sid = "water.lake"
        else:
            sid = "water.river"
    return get_symbol(sid) if sid else None


def list_symbols() -> Dict[str, Dict[str, Any]]:
    return {k: dict(v) for k, v in SYMBOLS.items()}
