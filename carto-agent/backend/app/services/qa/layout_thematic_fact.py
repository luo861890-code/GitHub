# -*- coding: utf-8 -*-
"""H. 专题信息质量（70）+ I. 整饰与版式（50）+ J. 事实与语义（40）"""
from typing import Any, Dict, List, Tuple

from .metrics import DECORATION_ITEMS, WUHAN_DISTRICTS, THEMATIC_EXPECTED


class LayoutThematicFact:
    """H+I+J 项：专题 70 分 + 整饰 50 分 + 事实 40 分"""

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        h, hd = self._thematic(map_data, issues)
        i, id_ = self._layout(map_data, issues)
        j, jd = self._fact(map_data, issues)
        return h + i + j, hd + id_ + jd

    def _thematic(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        """H 项 70 分：专题逻辑 25/覆盖 25/一致性 20"""
        map_type = map_data.get("map_type", "")
        layer_names = " ".join(l.get("name", "") for l in map_data.get("layers", []))
        detail: List[str] = []
        total = 0

        logic = 25
        if map_type == "administrative" and "重点地标" in layer_names:
            logic = 18
            issues["C2"].append("H 专题：行政图混入重点地标图层")
        total += logic

        expected = THEMATIC_EXPECTED.get(map_type, [])
        found = sum(1 for k in expected if k in layer_names)
        cover = round(25 * found / max(1, len(expected)))
        total += cover

        consistency = 20
        total += consistency
        detail.append(f"H专题逻辑 {logic}/25 · 覆盖 {cover}/25 · 一致性 {consistency}/20")
        return min(total, 70), detail

    def _layout(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        """I 项 50 分：10 项整饰各 5 分"""
        meta = map_data.get("metadata") or {}
        name = map_data.get("name", "")
        legend = (map_data.get("legend") or {}).get("items") or []
        layer_names = " ".join(l.get("name", "") for l in map_data.get("layers", []))
        checks = {
            "title": bool(name),
            "legend": bool(legend),
            "scale_bar": bool(meta.get("比例尺") or "比例尺" in layer_names),
            "north_arrow": "指北针" in layer_names,
            "frame": bool(meta.get("图廓") or meta.get("幅面")),
            "graticule": bool(meta.get("经纬网") or meta.get("经纬度")),
            "source": bool(meta.get("数据来源") or meta.get("资料来源")),
            "time": bool(meta.get("出版日期") or meta.get("制图时间")),
            "crs": bool(meta.get("坐标系") or meta.get("投影")),
            "made_at": bool(meta.get("制图时间") or meta.get("出版日期")),
        }
        total = 0
        for key, label in DECORATION_ITEMS:
            if checks.get(key):
                total += 5
            else:
                issues["C2"].append(f"I 整饰：缺少{label}")
        return min(total, 50), [f"I整饰 {total}/50"]

    def _fact(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        """J 项 40 分：事实正确 25/官方一致 15"""
        map_type = map_data.get("map_type", "")
        meta = map_data.get("metadata") or {}
        layer_names = " ".join(l.get("name", "") for l in map_data.get("layers", []))
        detail: List[str] = []

        fact = 25
        if map_type == "administrative":
            district_layer = next((l for l in map_data.get("layers", [])
                                   if l.get("name") == "区县名称标注"), None)
            if district_layer:
                names = {p.get("name") for p in (district_layer.get("properties") or [])}
                wrong = names - WUHAN_DISTRICTS
                miss = WUHAN_DISTRICTS - names
                if wrong or miss:
                    fact = 8
                    issues["C0"].append(f"J 事实：区名错误（多余 {sorted(wrong)[:3]}，缺失 {sorted(miss)[:3]}）")
        elif map_type == "traffic":
            if "轨道交通" not in layer_names and "地铁" not in layer_names:
                issues["C1"].append("J 事实：交通图缺少轨道交通（武汉关键事实要素）")
                fact -= 8
            if "长江" not in layer_names:
                issues["C2"].append("J 事实：交通图未标注长江")
                fact -= 4
        total = max(0, fact)

        official = 15
        if not meta.get("审图号"):
            official -= 8
            issues["C2"].append("J 官方一致：缺少审图号")
        if not meta.get("编制单位"):
            official -= 4
        total += max(0, official)

        detail.append(f"J事实 {max(0, fact)}/25 · 官方一致 {max(0, official)}/15")
        return min(total, 40), detail
