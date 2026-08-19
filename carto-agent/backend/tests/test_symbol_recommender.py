# -*- coding: utf-8 -*-
"""符号推荐引擎测试（计划 2.3）"""
from app.services.symbol_recommender import SymbolRecommender


def test_recommend_traffic_road():
    rec = SymbolRecommender().recommend("traffic", element_type="road", scale=100000)
    items = rec["recommendations"]
    assert items
    road = next(i for i in items if i["element"] == "road")
    assert road["symbol_type"] == "LineSymbol"
    assert road["color"] and road["weight"] > 0


def test_recommend_all_elements():
    rec = SymbolRecommender().recommend("tourism")
    assert rec["recommendations"]
    elements = {i["element"] for i in rec["recommendations"]}
    assert "poi" in elements
