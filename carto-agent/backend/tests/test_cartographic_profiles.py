# -*- coding: utf-8 -*-
"""四类地图 Cartographic Profile 测试（《武汉四类专题地图数据规范》）"""
from app.core.cartographic_profiles import (
    PROFILES,
    get_profile,
    get_tourism_level,
    is_major_bridge,
    scale_for_zoom,
    scale_state,
)


def test_four_profiles_defined():
    """四套 Profile 齐全且约束完整"""
    for t in ("administrative", "traffic", "tourism", "terrain"):
        p = get_profile(t)
        assert p.required, f"{t} 缺少 required_layers"
        assert p.forbidden, f"{t} 缺少 forbidden_layers"
        assert p.theme_importance
        assert "scale_rules" in p.to_dict()


def test_scale_matrix():
    """尺度约束矩阵：关键要素随尺度显隐"""
    assert scale_for_zoom(8) == "1_1M"
    assert scale_for_zoom(10) == "1_250K"
    assert scale_for_zoom(12) == "1_100K"
    assert scale_for_zoom(15) == "1_25K"
    # 街道界小比例尺隐藏、大比例尺显示
    assert scale_state("street_boundary", 8) == "hide"
    assert scale_state("street_boundary", 15) == "show"
    # 支路小比例尺隐藏
    assert scale_state("minor_road", 8) == "hide"
    assert scale_state("minor_road", 15) == "show"
    # 市界始终显示
    assert scale_state("admin_boundary", 8) == "show"


def test_tourism_poi_levels():
    """旅游 POI 分级：核心>文化>普通>服务"""
    assert get_tourism_level("核心景点")[0] == "P0"
    assert get_tourism_level("博物馆")[0] == "P1"
    assert get_tourism_level("历史遗迹")[0] == "P1"
    assert get_tourism_level("公园绿地")[0] == "P2"
    assert get_tourism_level("旅游服务")[0] == "P3"
    # importance 排序：P0 > P1 > P3
    assert get_tourism_level("核心景点")[1] > get_tourism_level("公园绿地")[1] > get_tourism_level("旅游服务")[1]


def test_major_bridge_detection():
    """主要桥梁识别"""
    assert is_major_bridge("武汉长江大桥")
    assert is_major_bridge("杨泗港大桥")
    assert not is_major_bridge("长丰桥路")
    assert not is_major_bridge("")


def test_apply_profile_filter_and_extract():
    """generate_map 应用 Profile：过滤禁止图层 + 提取桥梁 + POI 分级"""
    from app.services.map_service import MapService
    ms = MapService(persist_path="")
    layers = [
        {"id": "l1", "type": "polyline", "name": "道路-高速公路主线",
         "coordinates": [[[30.55, 114.30], [30.56, 114.32]]],
         "properties": [{"name": "武汉长江大桥"}], "style": {}, "group": "路网"},
        {"id": "l2", "type": "circleMarker", "name": "银行",
         "coordinates": [[30.59, 114.30]], "properties": [{"name": "中国银行"}], "style": {}, "group": "POI"},
        {"id": "l3", "type": "circleMarker", "name": "博物馆",
         "coordinates": [[30.56, 114.36]], "properties": [{"name": "湖北省博物馆"}], "style": {}, "group": "POI"},
    ]
    # 交通图：银行被禁，提取桥梁
    traffic = ms._apply_cartographic_profile("traffic", layers, 12)
    names = [l.get("name") for l in traffic]
    assert "银行" not in names
    assert "主要桥梁" in names
    bridge = next(l for l in traffic if l.get("name") == "主要桥梁")
    assert bridge["properties"][0]["name"] == "武汉长江大桥"
    # 旅游图：银行被禁，博物馆 importance 分级
    tourism = ms._apply_cartographic_profile("tourism", layers, 12)
    museum = next(l for l in tourism if l.get("name") == "博物馆")
    assert museum["properties"][0]["importance"] > 0.8
    assert museum["properties"][0]["poi_level"] == "P1"
