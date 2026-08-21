# -*- coding: utf-8 -*-
"""研究基线升级测试（计划 §10-16、§22）：
六维任务书置信度 / Planner 完整规划 / 工具契约 / 六层评估 / KG 决策关系。
"""
from app.services.task_parser import SixDimParser
from app.services.cartographic_planner import KGPriorPlanner
from app.services.tool_registry import (
    ToolRegistry,
    OSMFetchTool,
    SimplifyGeometryTool,
)
from app.services.cartography_validator import CartographyValidator
from app.core import kg_ontology


def test_six_dim_task_book_with_confidence():
    """六维任务书：降级解析也要带 confidence / inferred / clarification"""
    parser = SixDimParser(llm_service=None)  # 强制规则降级
    task = parser.parse("给我做一张武汉市交通图，给普通人看，重点突出地铁")
    book = task.to_task_book()
    # 六维齐全
    for dim in ("theme", "region", "temporal", "cartographic_method", "audience", "symbol_expression"):
        assert dim in book
        assert "value" in book[dim]
        assert "confidence" in book[dim]
        assert "inferred" in book[dim]
    # 用户明确给出的维度置信度较高
    assert book["region"]["value"] == "武汉市"
    assert book["theme"]["value"] == "交通"
    assert book["region"]["confidence"] >= 0.9
    assert book["audience"]["value"] == "public"
    assert book["audience"]["inferred"] is True  # 公众为默认推断
    assert "clarification_required" in book
    assert "reasoning_summary" in book


def test_planner_full_structure():
    """Planner 输出完整规划结构（map_spec / projection / generalization / ...）"""
    planner = KGPriorPlanner(kg_service=None, llm_service=None)
    plan = planner.plan(None, "traffic", "武汉市")
    d = plan.to_dict()
    assert d["task_id"].startswith("task_traffic_")
    for key in ("map_spec", "knowledge_refs", "data_plan", "projection_plan",
                "generalization_plan", "symbol_plan", "annotation_plan",
                "layout_plan", "render_plan", "validation_plan", "export_plan"):
        assert key in d
    assert d["map_spec"]["map_type"] == "traffic"
    assert d["projection_plan"]["projection"] == "cgcs2000_gk"  # 武汉市 -> 高斯克吕格
    assert d["generalization_plan"]["lod_bands"]
    assert d["validation_plan"]["layers"]
    assert "png" in d["export_plan"]["formats"]
    # KG 不可用时仍保留来源记录
    assert d["knowledge_refs"] == []


def test_tool_contract_exposed():
    """工具契约：preconditions / postconditions / retryable / provenance"""
    reg = ToolRegistry()
    reg.register(OSMFetchTool(None))
    reg.register(SimplifyGeometryTool())
    contracts = reg.list_tool_contracts()
    names = {c["name"] for c in contracts}
    assert "osm_fetch" in names
    assert "simplify_geometry" in names
    simp = next(c for c in contracts if c["name"] == "simplify_geometry")
    assert "geometry_valid=true" in simp["postconditions"]
    assert "feature_count_same_or_lower=true" in simp["postconditions"]
    assert simp["retryable"] is True
    assert simp["provenance"] is True
    # LLM 工具描述也暴露契约
    llm_defs = reg.get_tool_definitions_for_llm()
    assert all("preconditions" in x for x in llm_defs)


def test_validator_six_dimensions():
    """六层评估：validate 输出 dimensions 汇总"""
    MAP = {
        "name": "武汉市交通图",
        "map_type": "traffic",
        "metadata": {"投影": "Web墨卡托", "编制单位": "CartoAgent", "数据来源": "OSM"},
        "legend": {"items": [{"label": "道路", "type": "line", "color": "#3388ff"}]},
        "layers": [
            {"id": "l1", "type": "polyline", "name": "道路",
             "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
             "style": {"color": "#d97706", "weight": 4}},
        ],
    }
    report = CartographyValidator().validate(MAP)
    assert "check_scores" in report
    assert "dimensions" in report
    scores = report["dimensions"]["scores"]
    for dim in ("data", "spatial", "cartography", "visual"):
        assert dim in scores
        assert "score" in scores[dim]
        assert "name" in scores[dim]
    assert 0 <= scores["cartography"]["score"] <= 100


def test_kg_ontology_decision_seeds():
    """KG 本体：MapCase / Dataset 类与决策关系种子"""
    summary = kg_ontology.get_ontology_summary()
    assert "MapCase" in summary["classes"]
    assert "Dataset" in summary["classes"]
    # 决策关系种子
    rel_types = {r["type"] for r in kg_ontology.ONTOLOGY_RELATIONS}
    assert "CONTROLS" in rel_types       # Scale -> Generalization
    assert "SIMILAR_TO" in rel_types     # MapCase -> MapCase
    assert "SUITABLE_FOR" in rel_types   # Data -> Symbol
    # Dataset 节点
    dataset_names = {n["name"] for n in kg_ontology.ONTOLOGY_NODES if n.get("label") == "Dataset"}
    assert "srtm_dem_dataset" in dataset_names
    case_names = {n["name"] for n in kg_ontology.ONTOLOGY_NODES if n.get("label") == "MapCase"}
    assert "case_traffic_wuhan_public" in case_names
