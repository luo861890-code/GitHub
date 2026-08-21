# -*- coding: utf-8 -*-
"""收尾包 C/D：QA 精度修复 + 管线修复（props/coords 同步、连接范围、terrain 道路过滤）"""
import os

from app.services.generalization.engine import GeneralizationEngine
from app.services.qa.data_quality import DataQuality
from app.services.qa.generalization_quality import GeneralizationQuality
from app.services.qa.layout_thematic_fact import LayoutThematicFact
from app.services.qa.map_score import MapQAService
from app.services.qa.topology_quality import TopologyQuality
from app.services.map_service import MapService


# ==================== A2 属性精度 ====================

def test_a2_counts_subtype_as_complete():
    qa = DataQuality()
    issues = {"C0": [], "C1": [], "C2": [], "C3": []}
    md = {"layers": [
        {"type": "polyline", "name": "支流溪流",
         "coordinates": [[[30.5, 114.3], [30.51, 114.31]]],
         "properties": [{"subtype": "stream"}]},
        {"type": "circleMarker", "name": "景点",
         "coordinates": [[30.5, 114.3]],
         "properties": [{"name": "黄鹤楼", "category": "attraction"}]},
    ]}
    score = qa._attribute_score(md, issues)
    assert score == 40


def test_a2_penalizes_truly_empty_props():
    qa = DataQuality()
    issues = {"C0": [], "C1": [], "C2": [], "C3": []}
    md = {"layers": [
        {"type": "circleMarker", "name": "未知点",
         "coordinates": [[30.5, 114.3], [30.51, 114.31]],
         "properties": [{}, {}]},
    ]}
    score = qa._attribute_score(md, issues)
    assert score < 40


# ==================== C2 / E3 仅统计道路 ====================

def _road_and_boundary_map():
    boundary = {
        "type": "polyline", "name": "湖北周边城市边界",
        "coordinates": [[[30.5, 114.0], [30.6, 114.1]]] * 50,
        "properties": [{"name": "湖北省周边城市边界"}] * 50,
    }
    road = {
        "type": "polyline", "name": "道路-城市次干道",
        "coordinates": [[[30.5, 114.0], [30.6, 114.1]]] * 40,
        "properties": [{"name": "解放大道", "subtype": "secondary"}] * 40,
    }
    return {"layers": [boundary, road]}


def test_c2_only_counts_road_layers():
    qa = TopologyQuality()
    issues = {"C0": [], "C1": [], "C2": [], "C3": []}
    score, detail = qa.evaluate(_road_and_boundary_map(), issues)
    # 边界 50 段不计入；道路 40 段计入 → 扣 3*1
    assert "C2路网 27/30" in detail[0]
    # C1=30（无区县政区层时给满分） C2=27 C3=12（无点图层） C4=20
    assert score == 30 + 27 + 12 + 20


def test_e3_only_counts_road_layers():
    qa = GeneralizationQuality()
    issues = {"C0": [], "C1": [], "C2": [], "C3": []}
    score, detail = qa.evaluate(_road_and_boundary_map(), issues)
    assert "E3聚合" in detail[0]
    # 仅道路 40 段计入聚合 → E3=23/25（25-2*1）；边界 50 段不参与
    assert "E3聚合 23/25" in detail[0]


# ==================== J 事实：长江要素级判断 ====================

def test_fact_traffic_changjiang_feature_level():
    qa = LayoutThematicFact()
    issues = {"C0": [], "C1": [], "C2": [], "C3": []}
    md = {
        "map_type": "traffic",
        "layers": [
            {"name": "轨道交通线路", "type": "polyline"},
            {"name": "主要河流", "type": "polyline",
             "properties": [{"name": "长江"}]},
        ],
        "metadata": {"审图号": "x", "编制单位": "y"},
    }
    score, _ = qa._fact(md, issues)
    assert score == 40  # 25 + 15，长江存在


# ==================== 报告拆分真实化 ====================

def test_report_fact_matches_direct_evaluation():
    service = MapQAService()
    md = {
        "map_type": "traffic",
        "name": "武汉市交通图",
        "layers": [
            {"name": "轨道交通线路", "type": "polyline"},
            {"name": "主要河流", "type": "polyline",
             "properties": [{"name": "长江"}]},
        ],
        "metadata": {"审图号": "x", "编制单位": "y", "数据来源": "s",
                     "坐标系": "WGS84", "比例尺": "1:100000", "指北针": "y",
                     "图廓": "y", "经纬网": "y", "出版日期": "d", "制图时间": "d"},
        "legend": {"items": [{"label": "x"}]},
        "zoom": 12,
    }
    report = service.generate_report(md)
    fact = report["dimensions"]["fact"]["score"]
    assert fact >= 30  # 不再是余数拆分后的 12-27 区间


# ==================== props/coords 同步 ====================

def test_generalize_roads_keeps_props_synced():
    eng = GeneralizationEngine()
    layer = {
        "name": "道路-城市次干道", "type": "polyline",
        "coordinates": [
            [[30.5, 114.3], [30.51, 114.31]],
            [[30.51, 114.31], [30.52, 114.32]],
            [[30.5, 114.3], [30.51, 114.31]],  # exact duplicate
        ],
        "properties": [
            {"name": "解放大道", "subtype": "secondary"},
            {"name": "解放大道", "subtype": "secondary"},
            {"name": "解放大道", "subtype": "secondary"},
        ],
    }
    result = eng.generalize("traffic", [layer], 100_000)
    out = result["layers"][0]
    assert len(out["coordinates"]) == len(out["properties"])
    assert out["coordinates"]


def test_engine_pipeline_props_sync():
    eng = GeneralizationEngine()
    layers = [{
        "name": "道路-城市次干道", "type": "polyline",
        "coordinates": [
            [[30.5, 114.3], [30.51, 114.31]],
            [[30.5, 114.3], [30.51, 114.31]],
        ],
        "properties": [{"name": "解放大道"}, {"name": "解放大道"}],
    }]
    result = eng.generalize("traffic", layers, 100_000)
    for l in result["layers"]:
        if l.get("type") == "polyline":
            assert len(l.get("coordinates") or []) == len(l.get("properties") or [])


# ==================== 连接：无名称/等高线不合并 ====================

def test_connect_skips_unnamed_and_contours():
    ms = MapService(persist_path=":memory:")
    layers = [
        {
            "name": "支流溪流", "type": "polyline",
            "coordinates": [
                [[30.5, 114.3], [30.51, 114.31]],
                [[30.52, 114.32], [30.53, 114.33]],
            ],
            "properties": [{"subtype": "stream"}, {"subtype": "stream"}],
        },
        {
            "name": "等高线（首曲线）", "type": "polyline",
            "coordinates": [
                [[30.5, 114.3], [30.51, 114.31]],
                [[30.52, 114.32], [30.53, 114.33]],
            ],
            "properties": [{"ele": 40, "subtype": "contour"}, {"ele": 60, "subtype": "contour"}],
        },
    ]
    out = ms._connect_polylines_by_name(layers)
    for l in out:
        assert len(l["coordinates"]) == 2  # 不合并
        assert "merged" not in l["properties"][0]


def test_connect_merges_same_named_road():
    ms = MapService(persist_path=":memory:")
    layers = [{
        "name": "道路-城市主干道", "type": "polyline",
        "coordinates": [
            [[30.59, 114.30], [30.60, 114.31]],
            [[30.600001, 114.310001], [30.61, 114.32]],
        ],
        "properties": [{"name": "主路"}, {"name": "主路"}],
    }]
    out = ms._connect_polylines_by_name(layers)
    assert len(out[0]["coordinates"]) == 1
    assert out[0]["properties"][0]["merged"] is True


# ==================== terrain 道路过滤 ====================

def test_terrain_road_filter_keeps_motorway_trunk():
    from app.services.local_geo_service import LocalGeoService
    layers = LocalGeoService().get_roads_layers("武汉市")
    filtered = [
        l for l in layers
        if ((l.get("properties") or [{}])[0].get("subtype") in ("motorway", "trunk")
            or any(k in (l.get("name") or "") for k in ("高速公路", "城市干线")))
    ]
    assert filtered
    for l in filtered:
        sub = (l.get("properties") or [{}])[0].get("subtype")
        assert sub in ("motorway", "trunk")
