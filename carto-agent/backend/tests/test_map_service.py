# -*- coding: utf-8 -*-
"""地图服务单元测试：图层操作、图例过滤、按图懒加载迁移。"""
import json
import os

import pytest

from app.services.map_service import MapService


def _layer_ids(ms):
    return [l.get("id") for l in ms.get_map("map_test_0001").get("layers", [])]


def test_add_layer_direct_data(map_service):
    ms = map_service
    ms.add_layer(
        "map_test_0001", "circleMarker", "分析结果点",
        coordinates=[[30.595, 114.305]],
        properties=[{"name": "p"}],
        style={"color": "#ef4444"},
        group="分析结果",
    )
    last = ms.get_map("map_test_0001")["layers"][-1]
    assert last["coordinates"] == [[30.595, 114.305]]
    assert last["group"] == "分析结果"


def test_duplicate_reorder_group(map_service):
    ms = map_service
    before = len(ms.get_map("map_test_0001")["layers"])
    ms.duplicate_layer("map_test_0001", "layer_road")
    after = len(ms.get_map("map_test_0001")["layers"])
    assert after == before + 1

    ms.reorder_layers("map_test_0001", ["layer_lake", "layer_road"])
    assert ms.get_map("map_test_0001")["layers"][0]["id"] == "layer_lake"

    ms.set_layer_group("map_test_0001", "layer_road", "交通组")
    road = next(l for l in ms.get_map("map_test_0001")["layers"] if l["id"] == "layer_road")
    assert road["group"] == "交通组"


def test_legend_filters_base_layers(map_service):
    ms = map_service
    layers = list(ms.get_map("map_test_0001")["layers"])
    layers.insert(0, {
        "id": "base", "type": "polygon", "name": "陆地底图",
        "coordinates": [[]], "style": {"fillColor": "#f3ead9"},
    })
    layers.insert(1, {
        "id": "ctx", "type": "polygon", "name": "湖北省域",
        "coordinates": [[]], "style": {"fillColor": "#FBF7EF"},
    })
    legend = ms._generate_legend("traffic", layers)
    labels = {item["label"] for item in legend["items"]}
    assert "陆地底图" not in labels
    assert "湖北省域" not in labels
    assert "道路" in labels


def test_lazy_migration(work_tmp_dir):
    """旧版全量 maps.json 应自动迁移为索引 + 每图文件。"""
    full = {
        "map_a": {
            "map_id": "map_a", "name": "A", "map_type": "traffic",
            "center": [30.59, 114.30], "zoom": 12, "theme": "plain",
            "created_at": 1, "layers": [{"id": "l1", "type": "point", "name": "P", "coordinates": [[30.5, 114.3]]}],
        }
    }
    path = os.path.join(work_tmp_dir, "maps.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(full, f, ensure_ascii=False)

    ms = MapService(persist_path=path)
    assert "map_a" in ms.maps
    assert "layers" not in ms.maps["map_a"]
    assert ms.maps["map_a"].get("layer_count") == 1
    assert os.path.exists(os.path.join(work_tmp_dir, "maps", "map_a.json"))
    assert len(ms.get_map("map_a")["layers"]) == 1


def test_delete_map(map_service, work_tmp_dir):
    ms = map_service
    ms.flush()
    assert ms.delete_map("map_test_0001") is True
    assert "map_test_0001" not in ms.maps
    assert not os.path.exists(os.path.join(work_tmp_dir, "maps", "map_test_0001.json"))


def test_apply_style_package(map_service):
    ms = map_service
    ms.rename_layer("map_test_0001", "layer_road", "道路-主干道")
    ms.apply_style_package("map_test_0001", "dark")
    road = next(l for l in ms.get_map("map_test_0001")["layers"] if l["id"] == "layer_road")
    lake = next(l for l in ms.get_map("map_test_0001")["layers"] if l["id"] == "layer_lake")
    assert road["style"]["color"] == "#f59e0b"  # dark 主道路色
    assert lake["style"]["fillColor"] == "#0ea5e9"  # dark 水系填充


def test_connect_polylines_by_name(map_service):
    ms = map_service
    layers = [{
        "id": "r", "type": "polyline", "name": "道路-主干道",
        "coordinates": [
            [[30.59, 114.30], [30.60, 114.31]],
            [[30.600001, 114.310001], [30.61, 114.32]],
        ],
        "properties": [{"name": "主路"}, {"name": "主路"}],
    }]
    out = ms._connect_polylines_by_name(layers)
    assert len(out[0]["coordinates"]) == 1
    assert out[0]["properties"][0]["merged"] is True


def test_poly_area_km2():
    from shapely.geometry import Polygon
    from app.services.local_geo_service import LocalGeoService
    geom = Polygon([(114.30, 30.59), (114.31, 30.59), (114.31, 30.60), (114.30, 30.60)])
    area = LocalGeoService._poly_area_km2(geom)
    assert 0.8 < area < 1.6  # 约 0.01°×0.01°，约 1.1 km²


def test_water_layers_have_area():
    from app.services.local_geo_service import LocalGeoService
    layers = LocalGeoService().get_water_layers("武汉市")
    lake_layers = [l for l in layers if str(l.get("name", "")).startswith("湖泊")]
    assert lake_layers
    for layer in lake_layers[:3]:
        props = layer.get("properties") or []
        assert props
        assert "area_km2" in props[0]
