# -*- coding: utf-8 -*-
"""1000 分制地图质量验收模型测试（计划：四类地图自动验图）"""
import json
import os

from app.services.map_qa_service import MapQAService
from app.services.qa.metrics import WUHAN_DISTRICT_COUNT


def _load_fixture(map_type: str) -> dict:
    """从 data/maps 中取某类型最新一张地图（真实数据验收）"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    index_path = os.path.join(root, "data", "maps.json")
    with open(index_path, "r", encoding="utf-8") as f:
        index = json.load(f)
    maps = list(index.values()) if isinstance(index, dict) else index
    candidates = [m for m in maps if m.get("map_type") == map_type]
    if not candidates:
        # 索引中无该类型地图（被归档/覆盖）时实时生成，保证测试自足、不依赖外部数据状态
        from app.services.map_service import MapService
        ms = MapService(persist_path=os.path.join(root, "data", "maps.json"))
        zoom = {"administrative": 10, "traffic": 12, "tourism": 12, "terrain": 11}.get(map_type, 12)
        md = ms.generate_map(map_type, "武汉市", zoom=zoom)
        ms.flush()
        return md
    latest = max(candidates, key=lambda m: m.get("created_at", 0))
    with open(os.path.join(root, "data", "maps", f"{latest['map_id']}.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def test_report_structure_on_four_types():
    """四类真实武汉地图均可生成完整验收报告"""
    qa = MapQAService()
    for map_type in ("administrative", "traffic", "tourism", "terrain"):
        map_data = _load_fixture(map_type)
        assert map_data, f"缺少 {map_type} 地图数据"
        report = qa.generate_report(map_data)
        assert 0 <= report["total_score"] <= 1000
        assert report["grade"] in ("S", "A", "B", "C", "D", "E")
        assert report["status"] in ("PASS", "CONDITIONAL_PASS", "REWORK", "FAIL")
        for dim in ("data_quality", "completeness", "topology", "multi_source",
                    "generalization", "symbol_visual", "label", "thematic", "layout", "fact"):
            assert dim in report["dimensions"]
            d = report["dimensions"][dim]
            assert 0 <= d["score"] <= d["max"]
        assert "issues" in report and "critical" in report["issues"]
        assert "critical_errors" in report and "major_errors" in report and "minor_errors" in report
        assert "missing_features" in report
        assert "priority" in report


def test_admin_district_count_critical():
    """行政区数量与 13 区不符 → 致命错误门槛（总分 ≤599）"""
    map_data = _load_fixture("administrative")
    assert map_data
    # 篡改区县政区唯一区名数量（将半数面重名），触发 Critical
    for layer in map_data.get("layers", []):
        if layer.get("name") == "区县政区":
            feats = layer.get("features") or []
            for i, f in enumerate(feats):
                if i % 2 == 0:
                    props = dict(f.get("properties") or {})
                    props["name"] = "江岸区"
                    f["properties"] = props
            break
    report = MapQAService().generate_report(map_data)
    assert report["critical_errors"] >= 1
    assert report["total_score"] <= 599


def test_layout_and_fact_dimensions():
    """整饰/事实维度应有明确得分与问题"""
    map_data = _load_fixture("traffic")
    assert map_data
    report = MapQAService().generate_report(map_data)
    layout = report["dimensions"]["layout"]
    fact = report["dimensions"]["fact"]
    # 至少标题/图例/坐标系/来源存在（10 项整饰各 5 分）
    assert layout["score"] >= 20
    assert fact["score"] >= 0
    # 交通图缺轨道交通时应报 Major
    layer_names = " ".join(l.get("name", "") for l in map_data.get("layers", []))
    if "轨道交通" not in layer_names and "地铁" not in layer_names:
        assert any("轨道交通" in i for i in report["issues"]["major"])
