# -*- coding: utf-8 -*-
"""Displacement：平行/近距线要素在投影坐标下的垂直位移（真实几何偏移，非 z-index）"""
import math
from typing import List, Optional, Tuple

from app.core.crs_manager import CRSManager


class Displacement:
    """符号冲突位移：检测近距平行线，次要线沿法向平移"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def _normal_direction(self, line: List[Tuple[float, float]]) -> Tuple[float, float]:
        """线主方向法向量（投影坐标）"""
        if len(line) < 2:
            return (0.0, 1.0)
        dx = line[-1][0] - line[0][0]
        dy = line[-1][1] - line[0][1]
        length = math.hypot(dx, dy) or 1e-12
        return (-dy / length, dx / length)  # 垂直法向

    def _distance_between(self, a: List[Tuple[float, float]], b: List[Tuple[float, float]]) -> float:
        """两线最近距离（投影坐标，简化用中点距离）"""
        from shapely.geometry import LineString
        return LineString(a).distance(LineString(b))

    def displace(
        self,
        primary: List[Tuple[float, float]],
        secondary: List[Tuple[float, float]],
        distance_m: float,
    ) -> List[Tuple[float, float]]:
        """次要线沿主方向法向平移 distance_m（WGS84 输入/输出）"""
        primary_proj = self.crs.to_projected(primary)
        secondary_proj = self.crs.to_projected(secondary)
        nx, ny = self._normal_direction(primary_proj)
        displaced = [(x + nx * distance_m, y + ny * distance_m) for x, y in secondary_proj]
        return self.crs.from_projected(displaced)

    def resolve_parallel(
        self,
        lines: List[dict],
        distance_m: float,
    ) -> List[dict]:
        """对一组线做平行冲突消解：主要素不动，次要要素位移"""
        # 按 importance 降序（主要素在前）
        ordered = sorted(lines, key=lambda l: l.get("importance", 0.5), reverse=True)
        out = []
        for line in ordered:
            lonlat = [(c[0], c[1]) for c in line.get("coordinates", [])]
            displaced = list(lonlat)
            for kept in out:
                kept_lonlat = [(c[0], c[1]) for c in kept.get("coordinates", [])]
                try:
                    if self._distance_between(
                        self.crs.to_projected(lonlat),
                        self.crs.to_projected(kept_lonlat),
                    ) < distance_m:
                        displaced = self.displace(kept_lonlat, lonlat, distance_m)
                        break
                except Exception:
                    continue
            line["coordinates"] = displaced
            out.append(line)
        return out
