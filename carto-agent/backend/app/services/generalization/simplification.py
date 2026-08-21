# -*- coding: utf-8 -*-
"""Simplification：米制 Douglas-Peucker，tolerance 由 ScaleRule 动态给出"""
from typing import Dict, List, Optional, Tuple

from app.core.crs_manager import CRSManager


class Simplification:
    """几何简化（在投影 CRS 中，容差按比例尺与要素类别动态）"""

    def __init__(self, crs_manager: Optional[CRSManager] = None):
        self.crs = crs_manager or CRSManager()

    def simplify_linestring(
        self,
        lonlat: List[Tuple[float, float]],
        tolerance_m: float,
    ) -> List[Tuple[float, float]]:
        return self.crs.simplify_meters(lonlat, tolerance_m, preserve_topology=True)

    def simplify_geometry(
        self,
        geom: Dict,
        tolerance_m: float,
    ) -> Dict:
        return self.crs.simplify_geometry_meters(geom, tolerance_m, preserve_topology=True)

    def length_change(self, before: List[Tuple[float, float]], after: List[Tuple[float, float]]) -> float:
        """长度变化率（-1 ~ +∞，负表示缩短）"""
        b = self.crs.length_meters(before)
        a = self.crs.length_meters(after)
        if b == 0:
            return 0.0
        return (a - b) / b
