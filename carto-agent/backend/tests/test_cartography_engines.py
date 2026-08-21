# -*- coding: utf-8 -*-
"""收尾包 A/C：SymbolRegistry / LayoutEngine / LabelEngine 独立测试（不生成真实地图）"""
import math

from app.services.cartography.layout import LayoutEngine
from app.services.cartography.symbols.registry import (
    SYMBOLS, get_symbol, list_symbols, resolve_by_category, resolve_symbol,
)
from app.services.label.engine import CollisionGrid, LabelEngine
from app.services.label.metrics import compute_metrics
from app.services.map_service import MapService


# ==================== SymbolRegistry ====================

def test_symbols_all_have_required_keys():
    required = {"symbol_id", "geometry", "color", "width", "priority", "scale_range"}
    for sid, s in SYMBOLS.items():
        assert s["symbol_id"] == sid
        assert required <= set(s.keys()), sid
        assert s["geometry"] in ("line", "point", "polygon")
        assert s["scale_range"][0] <= s["scale_range"][1]


def test_get_symbol_unknown_returns_none():
    assert get_symbol("nonexistent.symbol") is None


def test_resolve_symbol_known_mapping():
    assert resolve_symbol("road", "motorway")["symbol_id"] == "road.motorway"
    assert resolve_symbol("water", "lake")["symbol_id"] == "water.lake"


def test_resolve_symbol_unknown_returns_none():
    assert resolve_symbol("road", "unknown_class") is None
    assert resolve_symbol("llm_random", "whatever") is None


def test_resolve_by_category_line_vs_polygon_water():
    assert resolve_by_category("major_water", "polygon")["symbol_id"] == "water.lake"
    assert resolve_by_category("major_water", "polyline")["symbol_id"] == "water.river"


def test_resolve_by_category_road_and_admin():
    assert resolve_by_category("motorway")["symbol_id"] == "road.motorway"
    assert resolve_by_category("district_boundary")["symbol_id"] == "boundary.district"
    assert resolve_by_category("contour_major")["symbol_id"] == "terrain.contour"


def test_resolve_by_category_unknown_returns_none():
    assert resolve_by_category("unknown") is None


def test_list_symbols_is_copy():
    syms = list_symbols()
    syms["road.motorway"]["color"] = "#000000"
    assert SYMBOLS["road.motorway"]["color"] != "#000000"


# ==================== LayoutEngine ====================

def test_layout_plan_has_all_slots():
    plan = LayoutEngine().plan("武汉市交通图", "traffic")
    slots = plan["layout"]
    for key in ("title", "legend", "scale_bar", "north_arrow", "source", "crs", "made_at"):
        assert key in slots
        assert "x" in slots[key] and "y" in slots[key]


def test_layout_plan_no_legend_skips_slot():
    plan = LayoutEngine().plan("测试", "traffic", has_legend=False)
    assert "legend" not in plan["layout"]


def test_layout_validation_passes_for_default():
    plan = LayoutEngine().plan("武汉市行政区划图", "administrative")
    assert LayoutEngine().validate(plan)["valid"] is True


def test_layout_conflict_avoidance_offsets():
    # legend 与 title 冲突时 legend 应下移（offset 机制）
    plan = LayoutEngine().plan("测试", "traffic")
    title_y = plan["layout"]["title"]["y"]
    legend_y = plan["layout"]["legend"]["y"]
    assert legend_y >= title_y


def test_layout_decoration_order_complete():
    plan = LayoutEngine().plan("测试", "traffic")
    assert len(plan["decoration_order"]) == 7
    assert plan["decoration_order"][0] == "title"


# ==================== LabelEngine ====================

def test_point_label_placed_without_collision():
    le = LabelEngine()
    res = le.place_point_label(100, 100, 80, 16, "黄鹤楼", "core_poi", (30.54, 114.30))
    assert res["placed"] is True
    assert len(le.placed) == 1


def test_point_label_suppressed_on_collision_low_priority():
    le = LabelEngine()
    # 同一锚点放置 9 个低优先级标签占满全部候选位，第 10 个被抑制
    for i in range(9):
        le.place_point_label(100, 100, 80, 16, f"L{i}", "normal", (30.54, 114.30))
    res = le.place_point_label(100, 100, 80, 16, "B", "normal", (30.54, 114.30))
    assert res["placed"] is False
    assert res["suppressed"] is True


def test_high_priority_label_not_suppressed():
    le = LabelEngine()
    le.place_point_label(100, 100, 80, 16, "低", "normal", (30.54, 114.30))
    res = le.place_point_label(100, 100, 80, 16, "武汉市", "admin", (30.54, 114.31))
    assert res["placed"] is True


def test_line_label_angle_computed():
    le = LabelEngine()
    line = [(30.5, 114.0), (30.5, 114.2), (30.5, 114.4)]
    res = le.place_line_label(line, "解放大道", "transport", (1680, 950))
    assert res["placed"] is True
    assert abs(abs(res["angle"]) - 90.0) < 5.0  # 东西向线 → 接近水平旋转角


def test_line_label_out_of_bounds():
    le = LabelEngine()
    # 视口范围（bounds）外的不放置：线在视口外
    line = [(31.5, 114.0), (31.5, 114.1)]
    res = le.place_line_label(
        line, "越界", "transport", (1680, 950),
        bounds=(29.0, 113.0, 31.0, 115.0),
    )
    assert res["placed"] is False
    assert res["reason"] == "out_of_bounds"


def test_line_label_inside_bounds_placed():
    le = LabelEngine()
    line = [(30.5, 114.0), (30.5, 114.1)]
    res = le.place_line_label(
        line, "解放大道", "transport", (1680, 950),
        bounds=(29.0, 113.0, 31.0, 115.0),
    )
    assert res["placed"] is True


def test_collision_grid_detects_overlap():
    g = CollisionGrid(cell=40)
    g.add(100, 100, 80, 16, {"name": "A"})
    assert g.conflict(100, 100, 80, 16) is True
    assert g.conflict(500, 500, 80, 16) is False


def test_label_metrics_fields():
    le = LabelEngine()
    le.place_point_label(100, 100, 80, 16, "A", "admin", (30.5, 114.3))
    le.place_point_label(100, 100, 80, 16, "B", "normal", (30.5, 114.31))
    m = compute_metrics(le.placed, le.suppressed, important_total=1)
    for k in ("label_count", "important_label_recall", "label_overlap_rate", "label_density"):
        assert k in m


# ==================== MapService 渲染链接入 ====================

def test_apply_symbol_registry_attaches_symbol_id():
    ms = MapService(persist_path=":memory:")
    layers = [{
        "id": "l1", "type": "polyline", "name": "道路-高速公路主线",
        "coordinates": [], "properties": [],
        "style": {"color": "#3388ff", "opacity": 0.9},
    }]
    out = ms._apply_symbol_registry(layers)
    assert out[0]["symbol_id"] == "road.motorway"
    assert out[0]["style"]["color"] == "#C2410C"
    assert out[0]["group"] == "道路"


def test_apply_symbol_registry_preserves_theme_opacity():
    ms = MapService(persist_path=":memory:")
    layers = [{
        "id": "l1", "type": "polyline", "name": "道路-城市干线主干道",
        "coordinates": [], "properties": [],
        "style": {"color": "#D97706", "weight": 1.76, "opacity": 0.38},
    }]
    out = ms._apply_symbol_registry(layers)
    # 主题弱化宽度（1.76 非通用默认值）保留，透明度保留
    assert out[0]["style"]["weight"] == 1.76
    assert out[0]["style"]["opacity"] == 0.38


def test_apply_label_engine_suppresses_and_adds_road_labels():
    ms = MapService(persist_path=":memory:")
    layers = [
        {
            "id": "l1", "type": "textLabel", "name": "普通要素注记",
            # 同 0.02° 格网放 3 个普通注记 → 第 3 个被格网容量抑制
            "coordinates": [[30.5000, 114.3000], [30.5001, 114.3001], [30.5002, 114.3002]],
            "properties": [{"name": "A"}, {"name": "B"}, {"name": "C"}],
            "style": {},
        },
        {
            "id": "l2", "type": "polyline", "name": "道路-城市主干道",
            "coordinates": [[[30.50, 114.30], [30.52, 114.33], [30.54, 114.36]]],
            "properties": [{"name": "解放大道", "subtype": "primary"}],
            "style": {},
        },
    ]
    metrics = ms._apply_label_engine("traffic", layers, 12)
    assert metrics["applied"] is True
    assert metrics["suppressed_count"] >= 1
    assert any(l.get("name") == "道路注记" for l in layers)


def test_classify_layer_group():
    ms = MapService(persist_path=":memory:")
    assert ms._classify_layer_group({"name": "道路-城市次干道"}) == "道路"
    assert ms._classify_layer_group({"name": "区县政区"}) == "行政区划"
    assert ms._classify_layer_group({"name": "主要河流"}) == "水系"
    assert ms._classify_layer_group({"name": "湖泊"}) == "水系"
    assert ms._classify_layer_group({"name": "等高线（计曲线）"}) == "地形地貌"
    assert ms._classify_layer_group({"name": "山峰注记", "type": "textLabel"}) == "注记"
    assert ms._classify_layer_group({"name": "陆地底图", "type": "polygon"}) == "底图"
