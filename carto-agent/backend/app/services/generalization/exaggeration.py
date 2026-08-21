# -*- coding: utf-8 -*-
"""Exaggeration：小但重要要素的最小面积保护（不删除、标记夸张，可选最小尺寸表达）"""
from typing import Dict

from app.core.crs_manager import CRSManager


class Exaggeration:
    """小行政区/小面保护"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def min_area_protect(
        self,
        geom: Dict,
        min_area_m2: float,
    ) -> Dict:
        """面积小于阈值时返回保护标记（不删除，交由渲染层最小尺寸表达）"""
        from shapely.geometry import shape
        g = shape(geom)
        area = self.crs.area_meters2(g) if not g.is_empty else 0.0
        return {
            "exaggerated": area < min_area_m2,
            "area_m2": area,
            "min_area_m2": min_area_m2,
            "keep": True,  # 合法行政区不删除
        }
