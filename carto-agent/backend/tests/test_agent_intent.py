# -*- coding: utf-8 -*-
"""智能体意图识别测试（关键词/问句优先逻辑）。"""
import pytest

from app.services.agent_service import AgentService


def _agent():
    a = AgentService.__new__(AgentService)
    a.llm_service = None
    return a


@pytest.mark.parametrize("message,expected", [
    ("什么是专题地图？", "question"),
    ("武汉市一共有多少个行政区？", "question"),
    ("武汉有哪些区？", "question"),
    ("地图制图有哪些基本原则？", "question"),
    ("生成一份武汉市交通图", "map_generation"),
    ("画一张武汉市旅游图", "map_generation"),
    ("武汉市交通图", "map_generation"),
    ("把道路改成红色", "map_modification"),
    ("添加一个医院图层", "map_modification"),
])
def test_detect_intent(message, expected):
    assert _agent()._detect_intent(message, []) == expected


# ============ QGIS 式注记图层解析 ============

_ANNOTATION_LAYERS = [
    {"id": "l1", "name": "湖泊注记", "type": "textLabel"},
    {"id": "l2", "name": "河流注记", "type": "textLabel"},
    {"id": "l3", "name": "道路注记", "type": "textLabel"},
    {"id": "l4", "name": "湖泊", "type": "polygon"},
    {"id": "l5", "name": "主要河流", "type": "polyline"},
]


def test_find_layers_by_keyword_annotation_exact():
    """'湖泊注记'精确命中湖泊注记图层（不再退到水系注记）"""
    a = _agent()
    hits = a._find_layers_by_keyword("把湖泊注记改成横向排布", _ANNOTATION_LAYERS)
    assert [l["id"] for l in hits] == ["l1"]


def test_find_layers_by_keyword_annotation_alias():
    """'湖注记'别名命中湖泊注记图层"""
    a = _agent()
    hits = a._find_layers_by_keyword("湖注记竖排", _ANNOTATION_LAYERS)
    assert [l["id"] for l in hits] == ["l1"]


def test_find_layers_by_keyword_annotation_fallback_merged():
    """湖泊注记图层缺失时回退到兼容的'水系注记'图层"""
    a = _agent()
    layers = [l for l in _ANNOTATION_LAYERS if l["name"] != "湖泊注记"]
    layers.append({"id": "l9", "name": "水系注记", "type": "textLabel"})
    hits = a._find_layers_by_keyword("湖泊注记改成蓝色", layers)
    assert [l["id"] for l in hits] == ["l9"]


def test_find_layers_by_keyword_annotation_missing_no_unrelated():
    """明确提到'道路注记'但地图没有该图层 → 不扩大到河流/湖泊注记"""
    a = _agent()
    layers = [l for l in _ANNOTATION_LAYERS if l["name"] not in ("道路注记", "湖泊注记")]
    hits = a._find_layers_by_keyword("把道路注记改成红色", layers)
    assert hits == []


def test_keyword_style_parse_text_direction():
    """关键词降级解析：横向/竖排 → textDirection"""
    a = _agent()
    parsed = a._parse_modification_with_keywords(
        "把湖泊注记改成竖排", {"layers": _ANNOTATION_LAYERS}
    )
    assert parsed is not None
    assert parsed["action"] == "update_style"
    assert parsed["params"]["layer_ids"] == ["l1"]
    assert parsed["params"]["style"]["textDirection"] == "vertical"

    parsed2 = a._parse_modification_with_keywords(
        "湖泊注记改成横向排布", {"layers": _ANNOTATION_LAYERS}
    )
    assert parsed2["params"]["style"]["textDirection"] == "horizontal"
