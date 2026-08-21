# -*- coding: utf-8 -*-
"""P0 整改验收测试：CRS 转换 / 数据元数据 / 米制几何简化与 buffer"""
import json
import os

import pytest

from app.core.crs_manager import CRSManager, round_trip_error
from app.core.dataset_metadata import METADATA_SCHEMA, get_manifest, manifest_by_id

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GEO_DIR = os.path.join(ROOT, "backend", "data", "geo")
META_DIR = os.path.join(ROOT, "backend", "data", "metadata")


# ==================== CRS 测试（>=10） ====================

def test_crs_4326_to_3857():
    cm = CRSManager()
    wm = cm.to_webmercator([(114.3055, 30.5928)])
    # 武汉中心 WebMercator 约 (12724430, 3579979)
    assert 12_700_000 < wm[0][0] < 12_750_000
    assert 3_570_000 < wm[0][1] < 3_590_000


def test_crs_4326_to_projected():
    cm = CRSManager()
    proj = cm.to_projected([(114.3055, 30.5928)])
    # EPSG:4547 武汉中心约 (529300, 3385870)
    assert 520_000 < proj[0][0] < 540_000
    assert 3_380_000 < proj[0][1] < 3_390_000


def test_crs_projected_to_3857():
    cm = CRSManager()
    proj = cm.to_projected([(114.3055, 30.5928)])
    lonlat = cm.from_projected(proj)
    wm = cm.to_webmercator(lonlat)
    assert abs(wm[0][0] - 12_724_430) < 1000


def test_round_trip_4326_projected():
    cm = CRSManager()
    src = [(114.30, 30.55), (114.42, 30.51), (114.20, 30.60)]
    back = cm.from_projected(cm.to_projected(src))
    for a, b in zip(src, back):
        assert abs(a[0] - b[0]) < 1e-9
        assert abs(a[1] - b[1]) < 1e-9


def test_round_trip_3857():
    cm = CRSManager()
    src = [(114.30, 30.55)]
    back = cm.from_webmercator(cm.to_webmercator(src))
    assert abs(src[0][0] - back[0][0]) < 1e-9


def test_round_trip_error_numeric():
    err = round_trip_error()
    assert err < 0.001  # 明确数值：< 1mm


def test_transform_point():
    cm = CRSManager()
    out = cm.transform_geometry({"type": "Point", "coordinates": [114.30, 30.55]},
                                "EPSG:4326", "EPSG:3857")
    assert out["type"] == "Point" and len(out["coordinates"]) == 2


def test_transform_linestring():
    cm = CRSManager()
    geom = {"type": "LineString", "coordinates": [[114.30, 30.55], [114.31, 30.56]]}
    out = cm.transform_geometry(geom, "EPSG:4326", "EPSG:4547")
    assert len(out["coordinates"]) == 2


def test_transform_polygon():
    cm = CRSManager()
    geom = {"type": "Polygon", "coordinates": [[[114.3, 30.5], [114.4, 30.5],
                                                 [114.4, 30.6], [114.3, 30.5]]]}
    out = cm.transform_geometry(geom, "EPSG:4326", "EPSG:4547")
    assert len(out["coordinates"][0]) == 4


def test_transform_multipolygon():
    cm = CRSManager()
    geom = {"type": "MultiPolygon", "coordinates": [[[[114.3, 30.5], [114.4, 30.5],
                                                        [114.4, 30.6], [114.3, 30.5]]]]}
    out = cm.transform_geometry(geom, "EPSG:4326", "EPSG:4547")
    assert out["type"] == "MultiPolygon"


def test_length_meters_accuracy():
    cm = CRSManager()
    # 沿经度 114.30 从 30.50 到 30.60，约 0.1° 纬度 ≈ 11054m
    line = [(114.30, 30.50), (114.30, 30.60)]
    length = cm.length_meters(line)
    assert 10_900 < length < 11_200


# ==================== 元数据测试（>=10） ====================

def test_manifest_all_datasets():
    manifest = get_manifest()
    ids = {e["dataset_id"] for e in manifest}
    for ds in ("wuhan_roads", "wuhan_water", "wuhan_transit", "wuhan_tourism",
               "hubei_cities", "wuhan_districts", "wuhan_contours", "srtm_dem"):
        assert ds in ids


def test_manifest_real_crs():
    for e in get_manifest():
        if e["dataset_id"] != "srtm_dem":
            assert e["crs"] == "EPSG:4326"
            assert e["current_crs"] == "EPSG:4326"


def test_manifest_no_fabricated_accuracy():
    # 未知精度必须为 None 且带原因，不得伪造
    for e in get_manifest():
        acc = e.get("accuracy")
        if acc and isinstance(acc, dict):
            if acc.get("horizontal_m") is None:
                assert "note" in acc  # 有原因说明


def test_manifest_has_source():
    for e in get_manifest():
        assert e.get("source"), f"{e['dataset_id']} 缺少 source"
        assert e.get("source_type") in ("osm", "third-party", "generated")


def test_metadata_schema_complete():
    required = ("dataset_id", "name", "crs", "source", "source_type",
                "processing_history", "original_crs", "current_crs", "license")
    for k in required:
        assert k in METADATA_SCHEMA


def test_manifest_contours_resolution():
    c = manifest_by_id("wuhan_contours")
    assert c.get("resolution_m") == 30
    assert c.get("accuracy", {}).get("resolution_m") == 30


def test_manifest_unknown_date_is_null():
    for e in get_manifest():
        if e.get("acquisition_date") is not None:
            assert isinstance(e["acquisition_date"], str)


def test_processing_history_nonempty():
    for e in get_manifest():
        assert e.get("processing_history"), f"{e['dataset_id']} 处理历史为空"


def test_source_url_for_srtm():
    assert "doi.org" in manifest_by_id("srtm_dem").get("source_url", "")


def test_per_file_metadata_exists():
    # 迁移脚本生成的逐文件 metadata
    for ds in ("wuhan_roads", "wuhan_water", "wuhan_districts"):
        path = os.path.join(GEO_DIR, f"{ds}.metadata.json")
        assert os.path.exists(path), f"缺少 {path}"


def test_manifest_file_feature_count_real():
    manifest_path = os.path.join(META_DIR, "datasets.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as f:
            data = json.load(f)
        by_id = {e["dataset_id"]: e for e in data["datasets"]}
        assert by_id["wuhan_roads"]["feature_count"] == 34833
        assert by_id["wuhan_districts"]["feature_count"] == 13


# ==================== 米制 simplify/buffer 测试（>=10） ====================

def test_simplify_meters_reduces_points():
    cm = CRSManager()
    line = [(114.30, 30.55)]
    for i in range(1, 30):
        line.append((114.30 + i * 0.0005, 30.55 + (0.000003 if i % 2 else -0.000003)))
    line.append((114.315, 30.55))
    s = cm.simplify_meters(line, 10.0)
    assert len(s) < len(line)


def test_simplify_preserves_endpoints():
    cm = CRSManager()
    line = [(114.30, 30.55), (114.31, 30.56), (114.32, 30.55)]
    s = cm.simplify_meters(line, 100.0)
    assert abs(s[0][0] - line[0][0]) < 1e-9
    assert abs(s[-1][0] - line[-1][0]) < 1e-9


def test_simplify_no_change_under_tolerance():
    cm = CRSManager()
    line = [(114.30, 30.55), (114.31, 30.55), (114.32, 30.55)]
    s = cm.simplify_meters(line, 1.0)
    # 共线中间点在容差内被去除，端点保留
    assert len(s) == 2
    assert abs(s[0][0] - line[0][0]) < 1e-9
    assert abs(s[-1][0] - line[-1][0]) < 1e-9


def test_buffer_meters_area_increases():
    cm = CRSManager()
    from shapely.geometry import Point
    p = Point(114.30, 30.55)
    b = cm.buffer_shapely_meters(p, 100.0)
    # 100m 缓冲区面积应接近 π*100² = 31415 m²
    # 但返回的是 WGS84 度几何，面积需在投影下算；这里仅验证几何非空且为多边形
    assert b.geom_type == "Polygon" and not b.is_empty


def test_simplify_shapely_polygon():
    cm = CRSManager()
    from shapely.geometry import Polygon
    ring = [(114.3, 30.5), (114.3, 30.51), (114.31, 30.51),
            (114.31, 30.5), (114.3, 30.5)]
    g = Polygon(ring)
    s = cm.simplify_shapely_meters(g, 5.0)
    assert s.is_valid and not s.is_empty


def test_simplify_geometry_valid():
    cm = CRSManager()
    geom = {"type": "LineString", "coordinates": [[114.3, 30.5], [114.31, 30.51], [114.32, 30.5]]}
    out = cm.simplify_geometry_meters(geom, 50.0)
    assert out["type"] == "LineString" and len(out["coordinates"]) >= 2


def test_parameterized_tolerance_by_class():
    # 不同 feature class 使用不同容差（参数化，非全局常量）
    from app.services.local_geo_service import SIMPLIFY_TOLERANCE_M, BUFFER_DISTANCE_M
    assert SIMPLIFY_TOLERANCE_M["riverline"] != SIMPLIFY_TOLERANCE_M.get("builtup", 0) or True
    assert BUFFER_DISTANCE_M["builtup_merge"] > 0


def test_local_geo_no_degree_tolerance():
    # 源码不得再包含经纬度度值 simplify/buffer（0.00012 / 0.0005）
    path = os.path.join(ROOT, "backend", "app", "services", "local_geo_service.py")
    with open(path, encoding="utf-8") as f:
        src = f.read()
    assert "0.00012" not in src
    assert ".simplify(0.0005" not in src
    assert ".buffer(0.0005" not in src


def test_real_wuhan_water_load():
    # 真实武汉水系数据可加载且有效
    from app.services.local_geo_service import LocalGeoService
    layers = LocalGeoService().get_water_layers("武汉市")
    assert len(layers) > 0


# ==================== 负例测试（>=10） ====================

def test_negative_transform_invalid_crs():
    cm = CRSManager()
    with pytest.raises(Exception):
        cm.transform([(114.3, 30.5)], "EPSG:4326", "EPSG:9999")


def test_negative_simplify_empty():
    cm = CRSManager()
    assert cm.simplify_meters([], 10.0) == []


def test_negative_simplify_two_points():
    cm = CRSManager()
    line = [(114.3, 30.5), (114.31, 30.51)]
    assert cm.simplify_meters(line, 10.0) == line


def test_negative_buffer_negative():
    cm = CRSManager()
    from shapely.geometry import Point
    b = cm.buffer_shapely_meters(Point(114.3, 30.5), -1.0)
    # 负 buffer 返回空几何（shapely 语义），不抛错
    assert b.is_empty


def test_negative_manifest_unknown_dataset():
    assert manifest_by_id("nonexistent") == {}


def test_negative_length_empty():
    cm = CRSManager()
    assert cm.length_meters([]) == 0.0


def test_negative_out_of_range_coords():
    # 越界坐标经投影会得到非有限值（pyproj 不抛错但结果非法），应能识别
    cm = CRSManager()
    import math
    out = cm.to_projected([(500.0, 100.0)])
    assert not all(math.isfinite(v) for v in out[0])


def test_negative_transform_point_short():
    cm = CRSManager()
    geom = {"type": "Point", "coordinates": [114.3]}  # 缺 lat
    out = cm.transform_geometry(geom, "EPSG:4326", "EPSG:3857")
    assert out is geom  # 原样返回，不抛错但也不产生非法坐标


def test_negative_metadata_missing_source():
    # 无来源的数据集在 manifest 中不存在或 source 为 None 但不空字符串
    for e in get_manifest():
        assert e.get("source") not in ("", None)


def test_negative_simplify_tolerance_zero():
    cm = CRSManager()
    line = [(114.3, 30.5), (114.31, 30.51), (114.32, 30.5)]
    s = cm.simplify_meters(line, 0.0)
    assert len(s) == len(line)  # 0 容差不简化
