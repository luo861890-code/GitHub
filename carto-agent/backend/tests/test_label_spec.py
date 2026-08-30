# -*- coding: utf-8 -*-
"""地图注记规范（Label Specification）落地测试：优先级/字体层级/字色/尺度范围/字向/质量指标"""
import math

from app.core.label_spec import (
    LABEL_STYLE, P0, P1, P2, P3, make_label_meta, priority_label, scale_range_for,
    style_for,
)
from app.services.label.engine import LabelEngine
from app.services.label.metrics import compute_metrics
from app.services.map_service import MapService


# ==================== 优先级分级（规范 §二） ====================

def test_priority_levels_ordered():
    assert P0 > P1 > P2 > P3
    assert (P0, P1, P2, P3) == (100, 80, 50, 20)


def test_priority_label_names():
    assert priority_label(P0) == "P0"
    assert priority_label(P1) == "P1"
    assert priority_label(P2) == "P2"
    assert priority_label(P3) == "P3"


def test_layer_priority_mapping():
    ms = MapService(persist_path=":memory:")
    assert ms._label_priority_value("市级名称标注", {"name": "武汉市"}) == P0
    assert ms._label_priority_value("水系注记", {"name": "长江"}) == P0
    assert ms._label_priority_value("交通枢纽", {"name": "武汉站"}) == P0
    assert ms._label_priority_value("区县名称标注", {"name": "武昌区"}) == P1
    assert ms._label_priority_value("道路注记", {"name": "沪渝高速", "layer": "道路-高速公路主线"}) == P1
    assert ms._label_priority_value("水系注记", {"name": "东湖"}) == P1
    assert ms._label_priority_value("道路注记", {"name": "某次干道", "layer": "道路-城市次干道"}) == P2
    assert ms._label_priority_value("水系注记", {"name": "某小湖"}) == P2
    assert ms._label_priority_value("普通要素", {"name": "某点"}) == P3


def test_lake_min_zoom_by_area():
    ms = MapService(persist_path=":memory:")
    assert ms._label_min_zoom("水系注记", {"name": "梁子湖", "area_km2": 159}) == 7   # ≥100km²
    assert ms._label_min_zoom("水系注记", {"name": "东湖", "area_km2": 33}) == 8     # ≥30km²
    assert ms._label_min_zoom("水系注记", {"name": "某中型湖", "area_km2": 12}) == 10  # ≥5km²
    assert ms._label_min_zoom("水系注记", {"name": "某小湖", "area_km2": 2}) == 12     # <5km²
    assert ms._label_min_zoom("水系注记", {"name": "汤逊湖"}) == 8                    # 无面积按名单


def test_lake_priority_by_area():
    ms = MapService(persist_path=":memory:")
    assert ms._label_priority_value("水系注记", {"name": "东湖", "area_km2": 33}) == P1
    assert ms._label_priority_value("水系注记", {"name": "某小湖", "area_km2": 2}) == P2


# ==================== 字体层级（规范 §十六） ====================

def test_font_hierarchy_sizes_and_weights():
    # P0 粗宋体 > P1 宋体 > P2 宋体 > P3 细等线（《地图文字注记规范》§一 居民地分级）
    assert LABEL_STYLE[P0]["size"] > LABEL_STYLE[P1]["size"] > LABEL_STYLE[P2]["size"] > LABEL_STYLE[P3]["size"]
    assert LABEL_STYLE[P0]["weight"] > LABEL_STYLE[P1]["weight"] > LABEL_STYLE[P2]["weight"] > LABEL_STYLE[P3]["weight"]
    assert LABEL_STYLE[P0]["font"] == "rough_song"   # 粗宋体（首都/省级/市名）
    assert LABEL_STYLE[P1]["font"] == "song"         # 宋体
    assert LABEL_STYLE[P2]["font"] == "song"
    assert LABEL_STYLE[P3]["font"] == "thin"         # 细等线（乡镇/村庄/普通 POI）


def test_style_for_same_level_consistent():
    a = style_for(P1)
    b = style_for(P1)
    assert a == b  # 同一等级字体/字号/字色完全一致
    assert style_for(9999) == style_for(P3)  # 未知等级回退 P3


def test_feature_color_override():
    meta = make_label_meta("l1", "长江", "water", P0, "line", 7, "water")
    assert meta["color"] == "#2E6FA3"  # 水系注记深蓝（规范 §二）
    assert meta["font"] == "rough_song"  # 屏幕图保持正体（用户偏好横向为主）
    assert meta["halo"] is True        # 水系注记白色描边，保证水面/陆地交界可读
    meta2 = make_label_meta("l2", "武汉市", "admin", P0, "point", 7, "admin")
    assert meta2["color"] == "#1F2937"
    assert meta2["halo"] is False


def test_residence_label_levels():
    # 居民地分级（规范 §一）：地级市 16 > 区县 14 > 乡镇 12 > 村庄 10
    from app.core.label_spec import (
        RESIDENCE_LABEL_BY_LEVEL, residence_label_style, make_residence_label_meta,
    )
    assert RESIDENCE_LABEL_BY_LEVEL["city"]["size"] == 16
    assert RESIDENCE_LABEL_BY_LEVEL["district"]["size"] == 14
    assert RESIDENCE_LABEL_BY_LEVEL["town"]["size"] == 12
    assert RESIDENCE_LABEL_BY_LEVEL["village"]["size"] == 10
    assert residence_label_style("town")["font"] == "thin"   # 乡镇=细等线
    assert residence_label_style("city")["font"] == "song"   # 地级市=宋体
    meta = make_residence_label_meta("r1", "某村", "village")
    assert meta["fontSize"] == 10
    assert meta["feature_type"] == "admin"


# ==================== 尺度范围（规范 §十） ====================

def test_scale_range_by_min_zoom():
    assert scale_range_for(6) == [1000000, 25000]   # 市名全尺度
    assert scale_range_for(8) == [1000000, 25000]   # 区名/大湖 1:100万 起
    assert scale_range_for(10) == [100000, 25000]   # 地标/主干道 1:10万 起
    assert scale_range_for(14) == [25000, 25000]    # 支路 1:2.5万


def test_label_meta_has_full_fields():
    meta = make_label_meta("lb_1", "武汉站", "transport_hub", P0, "point", 7, "transport")
    for k in ("label_id", "name", "feature_type", "priority", "anchor",
              "font", "size", "weight", "color", "scale_range", "min_zoom", "visibility"):
        assert k in meta, k
    assert meta["label_id"] == "lb_1"
    assert meta["priority"] == P0
    assert meta["anchor"] == "point"
    assert meta["visibility"] is True


# ==================== 字向（规范 §六） ====================

def test_line_angle_flip_avoids_upside_down():
    le = LabelEngine()
    # 西→东方向线（angle≈90°），应翻转/归一化到 -90~90 之间可读
    res = le.place_line_label(
        [(30.5, 114.0), (30.5, 114.1), (30.5, 114.2)],
        "长江", "transport", (1680, 950),
        bounds=(29.0, 113.0, 31.0, 115.0),
    )
    assert res["placed"] is True
    assert -90 <= res["angle"] <= 90


def test_line_angle_smooth_window():
    le = LabelEngine()
    # 折角线：中点前后存在折角，取 ±2 平滑窗口后方向接近整体主方向
    line = [(30.5, 114.0), (30.5, 114.1), (30.6, 114.2), (30.7, 114.3), (30.8, 114.4)]
    res = le.place_line_label(
        line, "某道路", "transport", (1680, 950),
        bounds=(29.0, 113.0, 31.0, 115.0),
    )
    assert res["placed"] is True
    assert -90 <= res["angle"] <= 90


# ==================== 质量指标（规范 §二十四） ====================

def test_metrics_include_priority_preservation():
    le = LabelEngine()
    le.place_point_label(100, 100, 80, 16, "武汉站", "admin", (30.6, 114.4))
    m = compute_metrics(
        le.placed, le.suppressed, important_total=1,
        total_by_priority={100: 1}, out_of_bounds_count=0, total_labels=1,
    )
    assert m["priority_preservation"] == 1.0  # P0 全保留
    assert m["out_of_bounds_rate"] == 0.0


def test_metrics_out_of_bounds_rate():
    m = compute_metrics([], [], 0, total_by_priority={}, out_of_bounds_count=5, total_labels=100)
    assert m["out_of_bounds_rate"] == 0.05
    assert m["important_label_recall"] >= 0
