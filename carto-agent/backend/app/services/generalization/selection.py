# -*- coding: utf-8 -*-
"""Selection：按要素重要性 + 尺度预算选取（真实选择，非随机、非删数据）"""
from typing import Dict, List, Tuple

from .scale_rules import ScaleRule


# 道路等级权重（class → importance 基础分）
ROAD_CLASS_WEIGHT: Dict[str, float] = {
    "motorway": 1.0, "motorway_link": 0.85,
    "trunk": 0.9, "trunk_link": 0.75,
    "primary": 0.8, "primary_link": 0.65,
    "secondary": 0.6, "secondary_link": 0.5,
    "tertiary": 0.4, "tertiary_link": 0.35,
    "residential": 0.2, "service": 0.15, "unclassified": 0.15, "other": 0.1,
}


def road_importance(feature_class: str, length_m: float, connectivity: int) -> float:
    """道路重要性：等级 + 长度 + 连通性"""
    cls = feature_class.replace("道路-", "").strip()
    w_class = ROAD_CLASS_WEIGHT.get(cls, 0.3)
    w_length = min(0.3, length_m / 50_000.0)  # 50km 道路长度项封顶
    w_connectivity = min(0.3, connectivity / 20.0)
    return round(w_class * 0.5 + w_length + w_connectivity, 4)


class Selection:
    """要素选取：按 importance 排序 + 尺度预算保留"""

    def __init__(self, scale_rule: ScaleRule):
        self.rule = scale_rule

    def select_features(
        self,
        items: List[dict],
        budget: int,
        importance_key: str = "importance",
    ) -> List[dict]:
        """按 importance 降序保留 budget 个；budget<=0 表示全保留"""
        if budget <= 0 or budget >= len(items):
            return items
        ranked = sorted(items, key=lambda x: x.get(importance_key, 0.0), reverse=True)
        return ranked[:budget]

    def select_pois(self, pois: List[dict], budget: int) -> Tuple[List[dict], List[dict]]:
        """POI 选择：保留重要 POI，返回 (保留, 移除)。移除不删除，标记由调用方降级/聚合。"""
        if budget <= 0 or budget >= len(pois):
            return pois, []
        ranked = sorted(pois, key=lambda p: p.get("importance", 0.0), reverse=True)
        return ranked[:budget], ranked[budget:]

    def budget_for_scale(self, feature_class: str, total: int) -> int:
        """按比例尺给出要素预算（图上可承载量）"""
        # 基于尺度：比例尺越大，可承载越多；此处用简化经验预算
        scale = self.rule.scale_denominator
        if feature_class in ("motorway", "trunk_road", "railway", "metro"):
            return total  # 骨架要素不裁剪
        if feature_class in ("minor_road", "service_poi"):
            if scale >= 1_000_000:
                return 0
            if scale >= 500_000:
                return int(total * 0.1)
            if scale >= 250_000:
                return int(total * 0.4)
            if scale >= 100_000:
                return int(total * 0.7)
            if scale >= 50_000:
                return int(total * 0.9)
            return total
        if feature_class in ("normal_poi", "core_poi"):
            if scale >= 500_000:
                return int(total * 0.5)
            if scale >= 100_000:
                return int(total * 0.8)
            return total
        return total
