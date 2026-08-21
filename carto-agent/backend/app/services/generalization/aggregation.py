# -*- coding: utf-8 -*-
"""Aggregation：同名线合并（linemerge）+ POI 网格聚类（真实聚合）"""
from typing import Dict, List, Tuple

from app.core.crs_manager import CRSManager


class Aggregation:
    """要素聚合（同名合并 / 点聚类）"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def merge_linestrings_by_name(
        self,
        geometries: List[Dict],
        names: List[str],
    ) -> List[Dict]:
        """同名 LineString 合并为完整线（真实 linemerge，非简单拼接）"""
        from shapely.geometry import LineString
        from shapely.ops import linemerge

        grouped: Dict[str, List[Dict]] = {}
        for geom, name in zip(geometries, names):
            grouped.setdefault(name, []).append(geom)

        merged = []
        for name, geoms in grouped.items():
            if len(geoms) <= 1:
                merged.extend(geoms)
                continue
            lines = []
            for g in geoms:
                coords = g.get("coordinates", [])
                if len(coords) >= 2:
                    lines.append(LineString([(c[0], c[1]) for c in coords]))
            try:
                m = linemerge(lines)
                if m.geom_type == "LineString":
                    merged.append({"type": "LineString", "coordinates": [list(c) for c in m.coords]})
                elif m.geom_type == "MultiLineString":
                    merged.extend(
                        {"type": "LineString", "coordinates": [list(c) for c in part.coords]}
                        for part in m.geoms
                    )
                else:
                    merged.extend(geoms)
            except Exception:
                merged.extend(geoms)
        return merged

    def cluster_points(
        self,
        lonlat_points: List[Tuple[float, float]],
        distance_m: float,
    ) -> List[dict]:
        """点聚类：投影坐标下按距离聚合，返回 cluster 质心（真实聚合，非随机删点）"""
        if not lonlat_points:
            return []
        proj = self.crs.to_projected(lonlat_points)
        import math
        clusters: List[dict] = []
        for p, src in zip(proj, lonlat_points):
            placed = False
            for c in clusters:
                if math.hypot(p[0] - c["x"], p[1] - c["y"]) <= distance_m:
                    c["x"] = (c["x"] * c["n"] + p[0]) / (c["n"] + 1)
                    c["y"] = (c["y"] * c["n"] + p[1]) / (c["n"] + 1)
                    c["n"] += 1
                    c["members"].append(src)
                    placed = True
                    break
            if not placed:
                clusters.append({"x": p[0], "y": p[1], "n": 1, "members": [src]})
        result = []
        for c in clusters:
            centroid_lonlat = self.crs.from_projected([(c["x"], c["y"])])[0]
            result.append({
                "centroid": list(centroid_lonlat),
                "member_count": c["n"],
                "members": c["members"],
            })
        return result
