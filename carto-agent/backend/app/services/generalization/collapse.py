# -*- coding: utf-8 -*-
"""Collapse：小面要素坍缩为点符号（面积小于阈值时不删除，降维表达）"""
from typing import Dict, Optional

from app.core.crs_manager import CRSManager


class Collapse:
    """面 → 点坍缩"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def should_collapse(self, geom: Dict, min_area_m2: float) -> bool:
        """面积是否小于最小面积阈值（应坍缩为点）"""
        from shapely.geometry import shape
        try:
            g = shape(geom)
            return not g.is_empty and self.crs.area_meters2(g) < min_area_m2
        except Exception:
            return False

    def collapse_to_point(self, geom: Dict) -> Dict:
        """面几何 → 质心点（WGS84）"""
        from shapely.geometry import shape, mapping
        g = shape(geom)
        centroid_proj = self.crs._to_projected_shapely(g).centroid
        lonlat = self.crs.from_projected([(centroid_proj.x, centroid_proj.y)])[0]
        return {"type": "Point", "coordinates": list(lonlat)}

    def area_m2(self, geom: Dict) -> float:
        from shapely.geometry import shape
        return self.crs.area_meters2(shape(geom))
