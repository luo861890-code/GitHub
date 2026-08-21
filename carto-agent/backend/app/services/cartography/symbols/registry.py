# -*- coding: utf-8 -*-
"""SymbolRegistry：统一制图符号注册表（颜色/线宽/填充/优先级/尺度范围）

所有要素符号从注册表取，LLM 不得随机生成颜色。每个符号含 symbol_id / geometry /
color / width / casing / priority / scale_range。
"""
from typing import Any, Dict, Optional


SYMBOLS: Dict[str, Dict[str, Any]] = {
    # 行政
    "boundary.province": {"symbol_id": "boundary.province", "geometry": "line",
                          "color": "#000000", "width": 1.2, "casing": None, "priority": 90,
                          "scale_range": [25000, 1000000]},
    "boundary.city": {"symbol_id": "boundary.city", "geometry": "line",
                      "color": "#E03131", "width": 3.0, "casing": None, "priority": 95,
                      "scale_range": [25000, 1000000]},
    "boundary.district": {"symbol_id": "boundary.district", "geometry": "line",
                          "color": "#8A8A8A", "width": 1.2, "casing": None, "priority": 85,
                          "scale_range": [25000, 1000000]},
    # 交通
    "road.motorway": {"symbol_id": "road.motorway", "geometry": "line",
                      "color": "#C2410C", "width": 4.0, "casing": "#7C2D12", "priority": 80,
                      "scale_range": [25000, 1000000]},
    "road.trunk": {"symbol_id": "road.trunk", "geometry": "line",
                   "color": "#D97706", "width": 3.2, "casing": "#92400E", "priority": 75,
                   "scale_range": [25000, 1000000]},
    "road.primary": {"symbol_id": "road.primary", "geometry": "line",
                     "color": "#94A3B8", "width": 2.5, "casing": None, "priority": 70,
                     "scale_range": [25000, 500000]},
    "road.secondary": {"symbol_id": "road.secondary", "geometry": "line",
                       "color": "#B9C4D0", "width": 2.0, "casing": None, "priority": 60,
                       "scale_range": [25000, 250000]},
    "road.minor": {"symbol_id": "road.minor", "geometry": "line",
                   "color": "#D3DBE3", "width": 1.0, "casing": None, "priority": 40,
                   "scale_range": [25000, 100000]},
    "railway.main": {"symbol_id": "railway.main", "geometry": "line",
                     "color": "#555555", "width": 2.0, "casing": None, "priority": 80,
                     "scale_range": [25000, 1000000]},
    "metro.line": {"symbol_id": "metro.line", "geometry": "line",
                   "color": "#0066CC", "width": 2.5, "casing": None, "priority": 80,
                   "scale_range": [25000, 1000000]},
    "bridge.major": {"symbol_id": "bridge.major", "geometry": "line",
                     "color": "#1E40AF", "width": 3.0, "casing": None, "priority": 90,
                     "scale_range": [25000, 1000000]},
    "hub.transport": {"symbol_id": "hub.transport", "geometry": "point",
                      "color": "#D97706", "width": 2.0, "casing": None, "priority": 70,
                      "scale_range": [25000, 1000000]},
    # 水系 / 自然
    "water.river": {"symbol_id": "water.river", "geometry": "line",
                    "color": "#2F7FD0", "width": 1.8, "casing": None, "priority": 50,
                    "scale_range": [25000, 1000000]},
    "water.lake": {"symbol_id": "water.lake", "geometry": "polygon",
                   "color": "#1E90FF", "width": 0.8, "casing": None, "priority": 45,
                   "scale_range": [25000, 1000000]},
    # 旅游 / 地势
    "poi.attraction": {"symbol_id": "poi.attraction", "geometry": "point",
                       "color": "#DC2626", "width": 1.0, "casing": None, "priority": 50,
                       "scale_range": [25000, 500000]},
    "terrain.contour": {"symbol_id": "terrain.contour", "geometry": "line",
                        "color": "#7A5230", "width": 1.0, "casing": None, "priority": 30,
                        "scale_range": [25000, 500000]},
    "terrain.peak": {"symbol_id": "terrain.peak", "geometry": "point",
                     "color": "#7A5230", "width": 1.0, "casing": None, "priority": 40,
                     "scale_range": [25000, 500000]},
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
