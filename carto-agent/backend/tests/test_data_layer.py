# -*- coding: utf-8 -*-
"""数据质量层 + 多源融合层 + 米制几何简化 测试"""
from app.services.data_quality import DataQualityEngine
from app.services.data_fusion import DataFusionEngine
from app.utils.geo_simplify import simplify_coords_meters


def test_data_quality_report_structure():
    """DataQualityEngine 输出机器可读 DataQualityReport"""
    map_data = {
        "map_id": "test", "name": "测试地图",
        "metadata": {"坐标系": "CGCS2000", "数据来源": "OSM", "出版日期": "2026"},
        "layers": [
            {"name": "道路", "type": "polyline",
             "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
             "properties": [{"name": "武汉长江大桥"}]},
            {"name": "湖泊", "type": "polygon",
             "coordinates": [[[30.55, 114.30], [30.56, 114.30], [30.56, 114.31], [30.55, 114.30]]],
             "properties": [{"name": "东湖"}]},
        ],
    }
    report = DataQualityEngine().check_map(map_data, expected_layers=["道路", "湖泊"])
    for key in ("dataset", "feature_count", "invalid_geometry", "duplicate",
                "missing_attributes", "crs", "source", "quality_score", "status"):
        assert key in report
    assert 0 <= report["quality_score"] <= 100
    assert report["status"] in ("PASS", "WARNING", "FAIL")
    assert report["missing_layers"] == []


def test_data_quality_detects_issues():
    """能检出非法坐标 / 空图层 / 缺名称"""
    map_data = {
        "name": "有问题", "map_id": "bad",
        "metadata": {},
        "layers": [
            {"name": "道路", "type": "circleMarker",
             "coordinates": [[200.0, 500.0]], "properties": [{}]},
            {"name": "空层", "type": "polyline", "coordinates": [], "properties": []},
        ],
    }
    report = DataQualityEngine().check_map(map_data)
    assert report["out_of_range_coords"] >= 1
    assert report["missing_attributes"] >= 1
    assert report["crs"] is None
    assert report["quality_score"] < 80


def test_data_fusion_source_priority():
    """来源优先级 + 置信度 + 名称规范化"""
    fusion = DataFusionEngine()
    assert fusion.source_priority("Official Government") > fusion.source_priority("OSM")
    assert fusion.normalize_name("武汉長江大桥") == "武汉长江大桥"
    conf = fusion.assign_confidence("DataV GeoAtlas", True)
    assert conf >= 0.8
    # 富集图层：写入 source/confidence
    layers = [{"name": "景点", "type": "circleMarker", "coordinates": [[30.5, 114.3]],
               "properties": [{"name": "黄鹤楼"}]}]
    enriched = fusion.enrich_layers(layers, "OSM")
    assert enriched[0]["properties"][0]["source"] == "OSM"
    assert "confidence" in enriched[0]["properties"][0]


def test_simplify_meters_reduces_points():
    """米制简化：在等距投影下按米数容差减少点，且保持端点"""
    # 一条带高频微弯的线（约 5km 长，带 1m 抖动）
    line = [(114.30, 30.55)]
    for i in range(1, 40):
        lng = 114.30 + i * 0.0005
        lat = 30.55 + (0.000005 if i % 2 else -0.000005)
        line.append((lng, lat))
    line.append((114.32, 30.55))
    simple = simplify_coords_meters(line, tolerance_m=20.0)
    assert len(simple) < len(line)
    # 端点保持不变
    assert abs(simple[0][0] - line[0][0]) < 1e-5
    assert abs(simple[-1][0] - line[-1][0]) < 1e-5
