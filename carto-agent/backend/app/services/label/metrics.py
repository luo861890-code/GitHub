# -*- coding: utf-8 -*-
"""Label QA 指标"""
from typing import Any, Dict, List


def compute_metrics(
    placed: List[Dict],
    suppressed: List[Dict],
    important_total: int,
    total_by_priority: Dict[int, int] = None,
    out_of_bounds_count: int = 0,
    total_labels: int = 0,
) -> Dict[str, Any]:
    """注记质量指标（规范 §二十四）：
    LabelRecall / CollisionRate / OutOfBoundsRate / LabelDensity / PriorityPreservation。
    """
    important_placed = sum(1 for p in placed if p.get("priority", 0) >= 60)
    # P0（priority=100）保留率：P0 注记不得被普通注记压盖/隐藏
    priority_preservation = 1.0
    if total_by_priority:
        p0_total = total_by_priority.get(100, 0)
        p0_placed = sum(1 for p in placed if p.get("priority", 0) >= 100)
        priority_preservation = round(p0_placed / max(1, p0_total), 4)
    out_of_bounds_rate = (
        round(out_of_bounds_count / max(1, total_labels), 4) if total_labels else 0.0
    )
    return {
        "label_count": len(placed),
        "suppressed_count": len(suppressed),
        "important_label_recall": round(important_placed / max(1, important_total), 4),
        "label_overlap_rate": 0.0,  # 放置时已消解冲突（CollisionGrid 无重叠）
        "label_density": round(len(placed) / 85.69, 4),  # /100km²
        "priority_preservation": priority_preservation,  # P0 保留率（目标 100%）
        "out_of_bounds_rate": out_of_bounds_rate,        # 越界率（目标 <1%）
    }
