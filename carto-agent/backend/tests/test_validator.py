# -*- coding: utf-8 -*-
"""制图规范校验测试（计划 3.1：7 维评分）"""
from app.services.cartography_validator import CartographyValidator


MAP = {
    "name": "武汉市交通图",
    "map_type": "traffic",
    "metadata": {"投影": "Web墨卡托", "编制单位": "CartoAgent", "数据来源": "OSM"},
    "legend": {"items": [{"label": "道路", "type": "line", "color": "#3388ff"}]},
    "layers": [
        {"id": "l1", "type": "polyline", "name": "道路", "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
         "style": {"color": "#d97706", "weight": 4}},
        {"id": "l2", "type": "textLabel", "name": "地标名称", "coordinates": [[30.59, 114.30]],
         "style": {"fontSize": 12}},
    ],
}


def test_seven_dimension_report():
    report = CartographyValidator().validate(MAP)
    assert "score" in report
    assert 0 <= report["score"] <= 100
    checks = report["passed_checks"] + report["failed_checks"]
    joined = " ".join(checks)
    for dim in ("拓扑", "符号", "注记", "载负量", "投影", "整饰", "数据"):
        assert dim in joined


def test_missing_decoration_flagged():
    bad = {**MAP, "legend": {"items": []}, "name": ""}
    report = CartographyValidator().validate(bad)
    assert any("整饰" in c for c in report["failed_checks"])
