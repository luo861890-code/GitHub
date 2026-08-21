# -*- coding: utf-8 -*-
"""评分聚合：十项指标按四类地图专项权重加权，输出等级/状态/问题分级。"""
from typing import Any, Dict, List, Tuple

from .metrics import DIMENSIONS, GRADE_BANDS, MAP_TYPE_WEIGHTS, grade_of, status_of
from .data_quality import DataQuality
from .completeness import Completeness
from .topology_quality import TopologyQuality
from .temporal_source_quality import TemporalSourceQuality
from .generalization_quality import GeneralizationQuality
from .symbol_label_quality import SymbolLabelQuality
from .layout_thematic_fact import LayoutThematicFact


class MapQAService:
    """自动地图验收：十项指标（A-J）→ 专项权重 → 1000 分制 → 等级/状态"""

    # 十项检查器
    EVALUATORS: Dict[str, Any] = {
        "data_quality": DataQuality(),
        "completeness": Completeness(),
        "topology": TopologyQuality(),
        "multi_source": TemporalSourceQuality(),
        "generalization": GeneralizationQuality(),
        "symbol_visual": SymbolLabelQuality(),
        "label": SymbolLabelQuality(),
        "thematic": LayoutThematicFact(),
        "layout": LayoutThematicFact(),
        "fact": LayoutThematicFact(),
    }

    # 分组执行（避免同一检查器重复运行）
    GROUPS: List[Tuple[str, Any]] = [
        ("data_quality", DataQuality()),
        ("completeness", Completeness()),
        ("topology", TopologyQuality()),
        ("multi_source", TemporalSourceQuality()),
        ("generalization", GeneralizationQuality()),
        ("symbol_label", SymbolLabelQuality()),
        ("layout_thematic_fact", LayoutThematicFact()),
    ]

    def generate_report(self, map_data: Dict[str, Any]) -> Dict[str, Any]:
        """生成 1000 分制验收报告（V1.0 规范）"""
        issues: Dict[str, List[str]] = {"C0": [], "C1": [], "C2": [], "C3": []}
        map_type = map_data.get("map_type", "")

        # 逐组执行检查，收集各维度得分
        raw_scores: Dict[str, int] = {}
        details: Dict[str, List[str]] = {}
        for name, evaluator in self.GROUPS:
            if name == "symbol_label":
                # 符号视觉（F）与注记（G）分别评估，避免“余数拆分”失真
                f_score, f_detail = evaluator._symbol_score(map_data, issues)
                g_score, g_detail = evaluator._label_score(map_data, issues)
                raw_scores["symbol_visual"] = min(f_score, 100)
                raw_scores["label"] = min(g_score, 80)
                details["symbol_visual"] = f_detail[:1]
                details["label"] = g_detail[:1]
            elif name == "layout_thematic_fact":
                # 专题（H）/整饰（I）/事实（J）分别评估，避免余数拆分失真
                h_score, h_detail = evaluator._thematic(map_data, issues)
                i_score, i_detail = evaluator._layout(map_data, issues)
                j_score, j_detail = evaluator._fact(map_data, issues)
                raw_scores["thematic"] = min(h_score, 70)
                raw_scores["layout"] = min(i_score, 50)
                raw_scores["fact"] = min(j_score, 40)
                details["thematic"] = h_detail[:1]
                details["layout"] = i_detail[:1]
                details["fact"] = j_detail[:1]
            else:
                score, d = evaluator.evaluate(map_data, issues)
                raw_scores[name] = score
                details[name] = d

        # 专项权重加权（规范 §21）：score/max 比例 × 权重
        weights = MAP_TYPE_WEIGHTS.get(map_type, {
            k: 0.1 for k in DIMENSIONS
        })
        weight_sum = sum(weights.values()) or 1.0
        weighted_total = 0.0
        dimension_scores: Dict[str, Dict[str, Any]] = {}
        for dim, cfg in DIMENSIONS.items():
            score = min(raw_scores.get(dim, 0), cfg["max"])
            w = weights.get(dim, 0.0)
            ratio = score / cfg["max"] if cfg["max"] else 0
            weighted_total += ratio * w * 1000 / weight_sum
            dimension_scores[dim] = {
                "name": cfg["name"],
                "score": score,
                "max": cfg["max"],
                "weight": round(w, 2),
                "issues": details.get(dim, []),
            }

        total = round(weighted_total)
        critical = len(issues["C0"])
        # 致命错误门槛：任一 Critical → 总分 ≤599（规范 §三）
        if critical > 0:
            total = min(total, 599)
        grade = grade_of(total)
        status = status_of(total, critical, map_type)

        # 缺失要素（B1 覆盖检查的问题归纳）
        missing = [i.split("：", 1)[-1] for i in issues["C1"] if "缺少关键要素" in i or "行政区事实错误" in i]

        return {
            "map_id": map_data.get("map_id", ""),
            "map_name": map_data.get("name", ""),
            "map_type": map_type,
            "region": map_data.get("region", ""),
            "scale": map_data.get("zoom", None),
            "crs": (map_data.get("metadata") or {}).get("坐标系") or "未声明",
            "total_score": total,
            "grade": grade,
            "status": status,
            "critical_errors": critical,
            "major_errors": len(issues["C1"]),
            "minor_errors": len(issues["C2"]),
            "dimensions": dimension_scores,
            "issues": {
                "critical": issues["C0"],
                "major": issues["C1"],
                "minor": issues["C2"],
                "suggestion": issues["C3"],
            },
            "missing_features": missing,
            "priority": self._build_priority(issues, missing),
            "thresholds": {
                "min_pass": 850 if map_type != "tourism" else 800,
            },
        }

    def _build_priority(self, issues: Dict[str, List[str]], missing: List[str]) -> List[str]:
        priority = [f"C0 {i}" for i in issues.get("C0", [])]
        priority += [f"缺失 {m}" for m in missing]
        priority += [f"C1 {i}" for i in issues.get("C1", [])]
        priority += [f"C2 {i}" for i in issues.get("C2", [])]
        return priority
