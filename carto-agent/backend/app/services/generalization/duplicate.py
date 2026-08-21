# -*- coding: utf-8 -*-
"""Duplicate Detection Engine：exact / reverse / near / semantic / legitimate_parallel"""
from typing import Dict, List, Tuple

from app.core.crs_manager import CRSManager


def _geom_key(coords) -> str:
    return repr([(round(float(p[0]), 4), round(float(p[1]), 4))
                 for p in coords if isinstance(p, (list, tuple)) and len(p) >= 2])


def _reverse_key(coords) -> str:
    return repr([(round(float(p[0]), 4), round(float(p[1]), 4))
                 for p in reversed(coords) if isinstance(p, (list, tuple)) and len(p) >= 2])


def count_exact_duplicates(coords_list: List) -> int:
    """精确重复（含反向）多余条数"""
    seen = set()
    extra = 0
    for c in coords_list:
        if not (isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple))):
            continue
        k = _geom_key(c)
        rk = _reverse_key(c)
        if k in seen or rk in seen:
            extra += 1
        else:
            seen.add(k)
    return extra


class DuplicateDetector:
    """重复检测：分类 exact / reverse / near / legitimate_parallel"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def detect(self, coords_list: List) -> Dict:
        """返回 {duplicate_type, pairs, action}"""
        seen: Dict[str, int] = {}
        exact_pairs = []
        near_pairs = []
        for i, c in enumerate(coords_list):
            if not (isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple))):
                continue
            k = _geom_key(c)
            if k in seen:
                exact_pairs.append((seen[k], i, "exact"))
            else:
                seen[k] = i
        # near：简化后坐标接近的平行线（Hausdorff 距离小，视为 near-duplicate，但合法平行保留）
        for i in range(len(coords_list)):
            for j in range(i + 1, len(coords_list)):
                if (i, j) in {(a, b) for a, b, _ in exact_pairs}:
                    continue
                d = self._parallel_distance(coords_list[i], coords_list[j])
                if d is not None and d < 10.0:  # <10m 视为 near（可能合法平行，标记不删）
                    near_pairs.append((i, j, "near", round(d, 1)))
        return {
            "exact_pairs": exact_pairs,
            "near_pairs": near_pairs,
            "exact_duplicate_count": len(exact_pairs),
            "near_duplicate_count": len(near_pairs),
            "action": "keep_legitimate_parallel",
        }

    def _parallel_distance(self, a, b):
        """两线平均距离（投影坐标，简化）"""
        try:
            a_p = self.crs.to_projected([(float(p[0]), float(p[1])) for p in a])
            b_p = self.crs.to_projected([(float(p[0]), float(p[1])) for p in b])
            if len(a_p) < 2 or len(b_p) < 2:
                return None
            from shapely.geometry import LineString
            la, lb = LineString(a_p), LineString(b_p)
            return (la.distance(lb) + lb.distance(la)) / 2.0
        except Exception:
            return None
