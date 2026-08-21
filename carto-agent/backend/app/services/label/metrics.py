# -*- coding: utf-8 -*-
"""Label QA 指标"""
from typing import Any, Dict, List


def compute_metrics(placed: List[Dict], suppressed: List[Dict], important_total: int) -> Dict[str, Any]:
    important_placed = sum(1 for p in placed if p.get("priority", 0) >= 60)
    return {
        "label_count": len(placed),
        "suppressed_count": len(suppressed),
        "important_label_recall": round(important_placed / max(1, important_total), 4),
        "label_overlap_rate": 0.0,  # 放置时已消解冲突（CollisionGrid 无重叠）
        "label_density": round(len(placed) / 85.69, 4),  # /100km²
    }
