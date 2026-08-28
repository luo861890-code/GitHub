"""QGIS 式图层目录测试：注记图层拆分 / 分组 / 自然语言注记解析"""
from app.core.layer_catalog import (
    ANNOTATION_LAYERS,
    annotation_category,
    annotation_feature_type,
    is_annotation_layer,
    layer_group,
    resolve_annotation_target,
    split_water_labels,
)


# ============ 注记图层定义 ============

def test_annotation_layers_complete():
    """注记类别齐全：湖泊/河流/水库/道路/轨道/山峰/政区/地标 各占一个图层"""
    names = {cfg["name"] for cfg in ANNOTATION_LAYERS.values()}
    assert "湖泊注记" in names
    assert "河流注记" in names
    assert "道路注记" in names
    assert "轨道注记" in names
    assert "山峰注记" in names
    assert "区县名称标注" in names
    assert "市级名称标注" in names
    assert "地标名称" in names


def test_annotation_category_inference():
    assert annotation_category("湖泊注记") == "lake"
    assert annotation_category("河流注记") == "river"
    assert annotation_category("水库注记") == "reservoir"
    assert annotation_category("道路注记") == "road"
    assert annotation_category("山峰注记") == "peak"
    assert annotation_feature_type("河流注记") == "water"
    assert annotation_feature_type("道路注记") == "transport"
    assert annotation_feature_type("区县名称标注") == "admin"
    assert annotation_feature_type("地标名称") == "poi"


def test_is_annotation_layer():
    assert is_annotation_layer({"name": "湖泊注记", "type": "textLabel"}) is True
    assert is_annotation_layer({"name": "水系注记", "type": "label"}) is True
    assert is_annotation_layer({"name": "区县名称标注", "type": "textLabel"}) is True
    assert is_annotation_layer({"name": "湖泊", "type": "polygon"}) is False
    assert is_annotation_layer({"name": "主要河流", "type": "polyline"}) is False


# ============ 分组（QGIS 图层树） ============

def test_layer_group_annotation_first():
    """注记图层一律归入"注记"组（不被"水系"等关键词抢先归类）"""
    assert layer_group({"name": "水系注记", "type": "textLabel"}) == "注记"
    assert layer_group({"name": "湖泊注记", "type": "textLabel"}) == "注记"
    assert layer_group({"name": "河流注记", "type": "label"}) == "注记"
    assert layer_group({"name": "区县名称标注", "type": "textLabel"}) == "注记"
    assert layer_group({"name": "道路注记", "type": "textLabel"}) == "注记"
    assert layer_group({"name": "山峰注记", "type": "textLabel"}) == "注记"


def test_layer_group_feature_layers():
    assert layer_group({"name": "陆地底图", "type": "polygon"}) == "底图"
    assert layer_group({"name": "区县政区"}) == "行政区划"
    assert layer_group({"name": "主要河流"}) == "水系"
    assert layer_group({"name": "湖泊"}) == "水系"
    assert layer_group({"name": "水库"}) == "水系"
    assert layer_group({"name": "道路-高速公路主线"}) == "道路"
    assert layer_group({"name": "铁路"}) == "轨道交通"
    assert layer_group({"name": "等高线（计曲线）"}) == "地形地貌"
    assert layer_group({"name": "山峰"}) == "地形地貌"


# ============ 自然语言 → 注记图层解析 ============

def test_resolve_annotation_target():
    assert resolve_annotation_target("把湖泊注记改成横向") == "湖泊注记"
    assert resolve_annotation_target("湖注记竖排") == "湖泊注记"
    assert resolve_annotation_target("湖泊名加粗") == "湖泊注记"
    assert resolve_annotation_target("河流注记换颜色") == "河流注记"
    assert resolve_annotation_target("道路名改成红色") == "道路注记"
    assert resolve_annotation_target("山峰注记改字号") == "山峰注记"
    assert resolve_annotation_target("区名标注改成黑色") == "区县名称标注"
    assert resolve_annotation_target("地标名称放大") == "地标名称"
    assert resolve_annotation_target("把道路图层加宽") is None  # 非注记意图


# ============ 水系注记拆分 ============

def test_split_water_labels():
    labels = [
        {"name": "长江", "rotation": 30},
        {"name": "东湖", "area_km2": 33.0},
        {"name": "梅店水库"},
        {"name": "汤逊湖"},
        {"name": "府河"},
    ]
    s = split_water_labels(labels)
    assert {l["name"] for l in s["river"]} == {"长江", "府河"}
    assert {l["name"] for l in s["lake"]} == {"东湖", "汤逊湖"}
    assert {l["name"] for l in s["reservoir"]} == {"梅店水库"}


def test_split_water_labels_area_fallback():
    """带 area_km2 的无名水体 → 湖泊注记（面状水体）"""
    s = split_water_labels([{"name": "", "area_km2": 5.0}])
    assert len(s["lake"]) == 1
