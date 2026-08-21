# -*- coding: utf-8 -*-
"""D. 多源数据一致性与时效性（80 分）：空间一致/时间一致/来源可信度"""
from typing import Any, Dict, List, Tuple


class TemporalSourceQuality:
    """D 项：多源一致性与时效性 80 分"""

    # 来源可信度五级（规范 §D3）
    SOURCE_RANK = {
        "official": 1.0, "government": 1.0, "professional": 0.9,
        "osm": 0.7, "third-party": 0.5, "unknown": 0.3,
    }

    def evaluate(self, map_data: Dict[str, Any], issues: Dict[str, List[str]]) -> Tuple[int, List[str]]:
        meta = map_data.get("metadata") or {}
        detail: List[str] = []
        total = 0

        # ---- D1 空间一致性 30：所有图层统一坐标基准（metadata 投影/坐标系） ----
        has_crs = bool(meta.get("坐标系") or meta.get("投影"))
        spatial = 30 if has_crs else 12
        if not has_crs:
            issues["C1"].append("D1 空间一致：缺少坐标系/投影声明，多源数据无法统一基准")
        else:
            # 数据源数量越多，越需要显式基准声明（DataV/OSM/SRTM 并存）
            source_text = str(meta.get("数据来源") or meta.get("资料来源") or "")
            n_sources = sum(1 for s in ("DataV", "OSM", "OpenStreetMap", "SRTM", "高德")
                            if s.lower() in source_text.lower())
            if n_sources >= 3:
                spatial = 22
                issues["C2"].append(f"D1 空间一致：检测到 {n_sources} 个数据源，建议补充各源 CRS 元数据")
        total += spatial

        # ---- D2 时间一致性 25：数据时间字段 ----
        has_time = bool(meta.get("出版日期") or meta.get("制图时间") or meta.get("资料截止"))
        time_score = 25 if has_time else 8
        if not has_time:
            issues["C1"].append("D2 时效：缺少数据/制图时间（无法判断时效性）")
        total += time_score

        # ---- D3 来源可信度 25：按数据来源评级 ----
        source_text = str(meta.get("数据来源") or meta.get("资料来源") or "").lower()
        if "datav" in source_text or "民政" in source_text:
            source_score = 25
        elif "osm" in source_text or "openstreetmap" in source_text:
            source_score = 18
            issues["C2"].append("D3 来源可信度：主要依赖 OSM 众包数据，建议补充官方数据源交叉核验")
        else:
            source_score = 10
            issues["C2"].append("D3 来源可信度：数据来源未声明或可信度低")
        total += source_score

        detail.append(f"D1空间 {spatial}/30 · D2时间 {time_score}/25 · D3来源 {source_score}/25")
        return min(total, 80), detail
