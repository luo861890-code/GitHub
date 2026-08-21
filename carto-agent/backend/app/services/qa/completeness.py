# -*- coding: utf-8 -*-
"""B. 数据数量与完整性（100 分）：覆盖/密度/冗余/信息有效率"""
from typing import Any, Dict, List, Tuple

from .metrics import THEMATIC_EXPECTED


class Completeness:
    """B 项：数据数量与完整性 100 分（数量≠质量，按 Coverage×Accuracy×Relevance）"""

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        layers = map_data.get("layers", [])
        map_type = map_data.get("map_type", "")
        detail: List[str] = []
        total = 0

        # ---- B1 要素覆盖 30：点/线/面/注记 + 专题关键图层 ----
        types = {l.get("type") for l in layers}
        coverage = 30
        for t, loss in (("point", 6), ("polyline", 6), ("polygon", 6), ("textLabel", 6)):
            has = bool(types & {
                "point": {"circleMarker", "marker", "point"},
                "polyline": {"polyline", "line"},
                "polygon": {"polygon", "area"},
                "textLabel": {"textLabel", "label"},
            }[t])
            if not has:
                coverage -= loss
        layer_names = " ".join(l.get("name", "") for l in layers)
        expected = THEMATIC_EXPECTED.get(map_type, [])
        missing_key = [k for k in expected if k not in layer_names]
        if missing_key:
            coverage -= min(12, 3 * len(missing_key))
            issues["C1"].append(f"B1 覆盖：缺少关键要素 {missing_key}")
        total += max(0, coverage)

        # ---- B2 数据密度合理性 30：要素数/市域面积 ----
        total_feats = sum(len(l.get("coordinates") or []) + len(l.get("features") or [])
                          for l in layers)
        density_per_100 = total_feats / 85.69 if total_feats else 0
        if density_per_100 == 0:
            density = 0
            issues["C1"].append("B2 密度：地图无要素")
        elif density_per_100 > 800:
            density = 12
            issues["C1"].append(f"B2 密度：载负量过高（约 {density_per_100:.0f} 要素/100km²）")
        elif density_per_100 > 400:
            density = 20
            issues["C2"].append(f"B2 密度：偏高（约 {density_per_100:.0f} 要素/100km²）")
        elif density_per_100 >= 15:
            density = 30
        else:
            density = 18
            issues["C2"].append(f"B2 密度：要素偏少（约 {density_per_100:.0f} 要素/100km²）")
        total += density

        # ---- B3 冗余率 20：重复图层名/重复点 ----
        names: Dict[str, int] = {}
        for l in layers:
            names[l.get("name", "")] = names.get(l.get("name", ""), 0) + 1
        dup_names = sum(1 for n, c in names.items() if n and c > 1)
        red_score = max(0, 20 - 5 * dup_names)
        if dup_names:
            issues["C2"].append(f"B3 冗余：{dup_names} 个图层名称重复")
        total += red_score

        # ---- B4 信息有效率 20：相关要素占比（以关键图层覆盖近似） ----
        effective = 20 if not missing_key else max(0, 20 - 3 * len(missing_key))
        total += effective

        detail.append(f"B1覆盖 {max(0, coverage)}/30 · B2密度 {density}/30 · B3冗余 {red_score}/20 · "
                      f"B4有效率 {effective}/20")
        return min(total, 100), detail
