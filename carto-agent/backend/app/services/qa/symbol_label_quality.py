# -*- coding: utf-8 -*-
"""F. 符号系统与视觉层级（100）+ G. 注记与冲突处理（80）"""
from typing import Any, Dict, List, Tuple

from app.services.cartography_validator import CartographyValidator


class SymbolLabelQuality:
    """F+G 项：符号视觉 100 分 + 注记冲突 80 分"""

    def __init__(self):
        self._validator = CartographyValidator()

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        f_score, f_detail = self._symbol_score(map_data, issues)
        g_score, g_detail = self._label_score(map_data, issues)
        detail = f_detail + g_detail
        return f_score + g_score, detail

    def _symbol_score(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        """F 项 100 分：符号规范 35/视觉层级 25/色彩 20/图层关系 20"""
        layers = map_data.get("layers", [])
        detail: List[str] = []
        total = 0

        # 符号规范（复用 CartographyValidator）
        sym_score, sym_issues = self._validator._check_symbol_normativity(map_data)
        symbol = round(35 * sym_score / 100)
        total += symbol
        for i in sym_issues[:2]:
            issues["C2"].append(f"F 符号规范：{i}")

        # 视觉层级：首图层应为面状底图
        hierarchy = 25
        if layers and layers[0].get("type") not in ("polygon", "area"):
            hierarchy = 15
            issues["C2"].append("F 视觉层级：首图层不是面状底图")
        total += hierarchy

        # 色彩：主色 ≤5（规范 §F）
        colors = set()
        for l in layers:
            st = l.get("style") or {}
            for k in ("color", "fillColor"):
                if st.get(k):
                    colors.add(str(st[k]).lower())
        color = 20 if len(colors) <= 8 else 12
        if len(colors) > 8:
            issues["C2"].append(f"F 色彩：使用 {len(colors)} 种颜色，建议主色≤5")
        total += color

        # 图层关系：分组完整
        grouped = sum(1 for l in layers if l.get("group"))
        layer_rel = 20 if layers and grouped >= len(layers) * 0.6 else 10
        if layers and grouped < len(layers) * 0.6:
            issues["C2"].append("F 图层关系：分组信息不完整")
        total += layer_rel

        detail.append(f"F符号 {symbol}/35 · 层级 {hierarchy}/25 · 色彩 {color}/20 · 图层关系 {layer_rel}/20")
        return min(total, 100), detail

    def _label_score(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        """G 项 80 分：注记冲突率 + 注记完整性"""
        layers = map_data.get("layers", [])
        detail: List[str] = []

        labels = []
        for l in layers:
            if l.get("type") in ("textLabel", "label"):
                labels.extend(l.get("coordinates") or [])
        if not labels:
            issues["C2"].append("G 注记：无注记图层")
            return 30, ["G注记 30/80（无注记）"]

        # 碰撞率：同 0.02° 格网 >2 标签
        cells: Dict[str, int] = {}
        for c in labels:
            if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                key = f"{round(c[0] / 0.02)},{round(c[1] / 0.02)}"
                cells[key] = cells.get(key, 0) + 1
        conflicts = sum(1 for v in cells.values() if v > 2)
        rate = conflicts / max(1, len(cells))
        # 规范 §G：目标碰撞率 <3%，优秀 <1%
        if rate < 0.01:
            collision = 40
        elif rate < 0.03:
            collision = 34
        elif rate < 0.1:
            collision = 26
            issues["C1"].append(f"G 注记：碰撞率 {rate:.0%}（目标 <3%）")
        else:
            collision = 16
            issues["C1"].append(f"G 注记：碰撞率 {rate:.0%}（需 LabelEngine 避让）")

        # 完整性：注记要素有名称
        no_name = 0
        for l in layers:
            if l.get("type") in ("textLabel", "label"):
                no_name += sum(1 for p in (l.get("properties") or []) if not (p.get("name") or ""))
        completeness = 40 if no_name == 0 else max(0, 40 - 2 * no_name)
        detail.append(f"G碰撞 {collision}/40 · 完整 {completeness}/40")
        return min(collision + completeness, 80), detail
