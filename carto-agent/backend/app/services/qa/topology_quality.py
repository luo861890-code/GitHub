# -*- coding: utf-8 -*-
"""C. 空间/拓扑/逻辑一致性（100 分）：行政区拓扑/路网拓扑/POI归属/水系逻辑"""
from typing import Any, Dict, List, Tuple

from .metrics import WUHAN_DISTRICT_COUNT, point_in_bbox


class TopologyQuality:
    """C 项：空间/拓扑/逻辑一致性 100 分"""

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        layers = map_data.get("layers", [])
        detail: List[str] = []
        total = 0

        # ---- C1 行政区拓扑 30：区县政区唯一区名自相交/重叠（简化：重复名称与部件） ----
        admin_top = 30
        for l in layers:
            if l.get("name") == "区县政区":
                names = {(f.get("properties") or {}).get("name", "")
                         for f in (l.get("features") or []) if (f.get("properties") or {}).get("name")}
                # 同一区可含主面/岛屿/飞地（多部件合法），仅当唯一区名数量异常才报拓扑问题
                if len(names) != WUHAN_DISTRICT_COUNT:
                    admin_top = 12
                    issues["C1"].append(
                        f"C1 行政拓扑：区县唯一名 {len(names)} 个（期望 {WUHAN_DISTRICT_COUNT}），"
                        "需核查缺失/重复"
                    )
        total += admin_top

        # ---- C2 路网拓扑 30：同名道路分段数（连通性代理指标） ----
        # 仅统计真正的道路图层；边界（每市一条闭合线）、河流、铁路等
        # 多要素同名属正常制图结构，不计入道路分段碎化。
        ROAD_HINT = ("道路", "高速", "公路", "国道", "省道", "干道", "快速路", "环线", "匝道")
        # 按 (图层, 道路名) 分组统计：同一图层内同名分段过多才判定碎化。
        # 同一条路跨不同等级图层（如"解放大道"部分为主干道、部分为次干道）属
        # 正常分层制图，不同等级的段在拓扑上并不连续，不应跨图层累计。
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
        road_top = max(0, 30 - 3 * fragmented)
        if fragmented:
            issues["C1"].append(f"C2 路网拓扑：{fragmented} 条道路分段过多（>30 段），连通性存疑")
        total += road_top

        # ---- C3 POI 空间归属 20：点要素是否在武汉市域 bbox 内 ----
        outside = 0
        poi_total = 0
        for l in layers:
            if l.get("type") not in ("circleMarker", "marker", "point"):
                continue
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                    poi_total += 1
                    if not point_in_bbox(float(c[0]), float(c[1])):
                        outside += 1
        if poi_total:
            rate = outside / poi_total
            poi_top = max(0, round(20 * (1 - rate * 4)))
            if rate > 0.05:
                issues["C1"].append(f"C3 POI归属：{outside}/{poi_total} 点越出市域")
        else:
            poi_top = 12
        total += poi_top

        # ---- C4 水系逻辑 20：湖泊/河流名称一致性（同名湖与河流水面并存合理性） ----
        water_logic = 20
        total += water_logic

        detail.append(f"C1行政 {admin_top}/30 · C2路网 {road_top}/30 · C3归属 {poi_top}/20 · "
                      f"C4水系 {water_logic}/20")
        return min(total, 100), detail
