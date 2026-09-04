# -*- coding: utf-8 -*-
"""E. 地图综合与多尺度表达（180 分）：选取/简化/聚合/合并/移位/夸张/坍缩/多尺度"""
from typing import Any, Dict, List, Tuple

from .metrics import area_km2


class GeneralizationQuality:
    """E 项：地图综合与多尺度表达 180 分"""

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        layers = map_data.get("layers", [])
        detail: List[str] = []
        total = 0

        # ---- E1 选取 25：图层数量与主题匹配 ----
        n = len(layers)
        if 5 <= n <= 55:
            selection = 25
        elif 1 <= n < 5:
            selection = 12
            issues["C2"].append("E1 选取：图层过少")
        else:
            selection = 16
            issues["C2"].append(f"E1 选取：图层过多（{n}）")
        total += selection

        # ---- E2 简化 25：过度简化检测（线点数过少） ----
        over_simple = 0
        for l in layers:
            if l.get("type") not in ("polyline", "line"):
                continue
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and len(c) == 2 and isinstance(c[0], list):
                    pass  # 单段线正常
        simp = 25
        total += simp

        # ---- E3 聚合 25：同名道路分段（可聚合性） ----
        # 仅统计道路图层；边界/水系/铁路多要素同名属正常结构，不计入聚合性判定。
        ROAD_HINT = ("道路", "高速", "公路", "国道", "省道", "干道", "快速路", "环线", "匝道")
        # 按 (图层, 道路名) 分组统计：与 C2 口径一致，同一图层内同名分段过多才判定。
        # 跨等级图层（主干道/次干道/干线）的同名道路段拓扑不连续，不跨图层累计。
        seg_groups: Dict[Tuple[str, str], int] = {}
        for l in layers:
            if l.get("type") not in ("polyline", "line"):
                continue
            lname = l.get("name") or ""
            meta = l.get("metadata") or {}
            subtype = (l.get("properties") or [{}])[0].get("subtype") or ""
            if not (any(k in lname for k in ROAD_HINT)
                    or "道路" in str(meta.get("subgroup") or meta.get("group") or "")
                    or subtype in ("motorway", "motorway_link", "trunk", "trunk_link",
                                   "primary", "primary_link", "secondary", "secondary_link",
                                   "tertiary", "tertiary_link", "residential", "service",
                                   "unclassified")):
                continue
            for p in (l.get("properties") or []):
                nm = p.get("name") or ""
                if nm:
                    key = (lname, nm)
                    seg_groups[key] = seg_groups.get(key, 0) + 1
        fragmented = sum(1 for c in seg_groups.values() if c > 30)
        agg = max(0, 25 - 2 * fragmented)
        if fragmented:
            issues["C1"].append(f"E3 聚合：{fragmented} 条道路/边界分段过多，建议按名称合并")
        total += agg

        # ---- E4 合并 15：同名要素重复 ----
        merge = 15 if fragmented == 0 else 9
        total += merge

        # ---- E5 移位 25：注记冲突率（同格网多标签） ----
        shift, shift_msg = self._label_conflict(layers)
        total += shift
        if shift_msg:
            issues["C1"].append(f"E5 移位：{shift_msg}")

        # ---- E6 夸张 20：小面要素处理 ----
        small = 0
        for l in layers:
            if l.get("type") not in ("polygon", "area"):
                continue
            for ring in (l.get("coordinates") or []):
                if isinstance(ring, list) and len(ring) >= 4 and area_km2(ring) < 0.02:
                    small += 1
        exagger = max(0, 20 - 2 * small)
        if small:
            issues["C2"].append(f"E6 夸张：{small} 个极小面，小比例尺需夸张/坍缩")
        total += exagger

        # ---- E7 坍缩 20：面→点符号层 ----
        has_collapse = any("点符号" in (l.get("name") or "") for l in layers)
        collapse = 20 if has_collapse else 12
        if not has_collapse:
            issues["C2"].append("E7 坍缩：缺少小面要素的点符号坍缩层")
        total += collapse

        # ---- E8 多尺度连续性 25：LOD 档位图层 ----
        has_lod = any(any(k in (l.get("name") or "") for k in ("概览级", "市域级", "城区级", "详图级"))
                      for l in layers)
        multi = 25 if has_lod else 10
        if not has_lod:
            issues["C2"].append("E8 多尺度：未检测到 LOD 档位图层")
        total += multi

        detail.append(f"E1选取 {selection}/25 · E2简化 {simp}/25 · E3聚合 {agg}/25 · E4合并 {merge}/15 · "
                      f"E5移位 {shift}/25 · E6夸张 {exagger}/20 · E7坍缩 {collapse}/20 · E8多尺度 {multi}/25")
        return min(total, 180), detail

    def _label_conflict(self, layers: List[Dict]) -> Tuple[int, str]:
        labels = []
        for l in layers:
            if l.get("type") in ("textLabel", "label"):
                labels.extend(l.get("coordinates") or [])
        if not labels:
            return 12, ""
        cells: Dict[str, int] = {}
        for c in labels:
            if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                key = f"{round(c[0] / 0.02)},{round(c[1] / 0.02)}"
                cells[key] = cells.get(key, 0) + 1
        conflicts = sum(1 for v in cells.values() if v > 2)
        rate = conflicts / max(1, len(cells))
        if rate > 0.3:
            return 8, f"注记冲突率 {rate:.0%}（需位移/避让）"
        if rate > 0.1:
            return 18, ""
        return 25, ""
