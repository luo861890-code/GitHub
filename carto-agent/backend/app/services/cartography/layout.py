# -*- coding: utf-8 -*-
"""LayoutEngine：自动版式（标题/图例/比例尺/指北针/来源/坐标系/时间）"""
from typing import Any, Dict


# 版式网格（A4 横向，单位：画布相对坐标 0-100）
LAYOUT_SLOTS: Dict[str, Dict[str, Any]] = {
    "title": {"x": 50, "y": 4, "anchor": "center", "avoid": ["legend"]},
    "legend": {"x": 86, "y": 55, "anchor": "right", "avoid": ["title", "north"]},
    "scale_bar": {"x": 14, "y": 90, "anchor": "left", "avoid": ["source"]},
    "north_arrow": {"x": 90, "y": 10, "anchor": "right", "avoid": ["title"]},
    "source": {"x": 86, "y": 92, "anchor": "right", "avoid": ["scale_bar"]},
    "crs": {"x": 14, "y": 94, "anchor": "left", "avoid": ["scale_bar"]},
    "made_at": {"x": 50, "y": 96, "anchor": "center", "avoid": []},
}


class LayoutEngine:
    """版式规划：分配各要素位置，冲突则按优先级调整"""

    def plan(
        self,
        map_name: str,
        map_type: str,
        has_legend: bool = True,
        has_scale_bar: bool = True,
    ) -> Dict[str, Any]:
        used: Dict[str, Any] = {}
        for slot, cfg in LAYOUT_SLOTS.items():
            if slot == "legend" and not has_legend:
                continue
            if slot == "scale_bar" and not has_scale_bar:
                continue
            # 冲突避免：若有要素占据被 avoid 槽位，则当前槽位微移
            offset = 0
            for avoided in cfg.get("avoid", []):
                if avoided in used:
                    offset += 6
            used[slot] = {"x": cfg["x"], "y": cfg["y"] + offset, "anchor": cfg["anchor"]}
        return {
            "map_name": map_name,
            "map_type": map_type,
            "layout": used,
            "decoration_order": ["title", "legend", "scale_bar", "north_arrow", "source", "crs", "made_at"],
        }

    def validate(self, layout: Dict[str, Any], canvas: tuple = (1680, 950)) -> Dict[str, Any]:
        """版式校验：标题不靠边、图例不压主图（以 8% 边距为界）"""
        issues = []
        title = layout.get("layout", {}).get("title", {})
        if title.get("y", 0) < 2:
            issues.append("title_too_close_to_edge")
        legend = layout.get("layout", {}).get("legend", {})
        if legend.get("x", 0) > 92:
            issues.append("legend_may_overlap_other_decorations")
        return {"valid": len(issues) == 0, "issues": issues}
