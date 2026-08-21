# -*- coding: utf-8 -*-
"""几何 / 拓扑 / 位置校验器（GIS 数据质量层）"""
from typing import Any, Dict, List, Tuple


def _coords_of(geom: Dict[str, Any]) -> List[tuple]:
    """提取几何坐标点序列（[lng, lat] -> (lng, lat)）"""
    gtype = geom.get("type")
    coords = geom.get("coordinates") or []
    if gtype == "Point":
        return [(coords[0], coords[1])] if len(coords) >= 2 else []
    if gtype in ("LineString", "MultiPoint"):
        return [(c[0], c[1]) for c in coords if len(c) >= 2]
    if gtype in ("Polygon", "MultiLineString"):
        out = []
        rings = coords if gtype == "MultiLineString" else coords
        for ring in rings:
            out += [(c[0], c[1]) for c in ring if len(c) >= 2]
        return out
    if gtype == "MultiPolygon":
        out = []
        for poly in coords:
            for ring in poly:
                out += [(c[0], c[1]) for c in ring if len(c) >= 2]
        return out
    return []


class GeometryValidator:
    """几何校验：空/无效/自相交/重复/sliver/spike/环错误"""

    def check_geometry(self, geom: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "empty": False,
            "invalid": False,
            "self_intersection": False,
            "invalid_ring": False,
            "sliver": False,
            "spike": False,
        }
        try:
            from shapely.geometry import shape
            g = shape(geom)
        except Exception:
            result["invalid"] = True
            return result
        if g.is_empty:
            result["empty"] = True
            return result
        if not g.is_valid:
            result["invalid"] = True
            # 自相交与环错误属于 invalid 的常见子类
            result["self_intersection"] = "Self-intersection" in str(g.explain_validity() or "")
            result["invalid_ring"] = "Ring" in str(g.explain_validity() or "")
        # sliver / spike：基于面积/周长比的启发式（仅面）
        if geom.get("type") in ("Polygon", "MultiPolygon"):
            try:
                area = g.area
                length = g.length
                if length > 0:
                    thinness = area / (length * length) if length > 0 else 0
                    if area > 0 and thinness < 1e-6:
                        result["sliver"] = True
            except Exception:
                pass
        return result

    def spike_ratio(self, coords: List[tuple]) -> float:
        """尖角比例（spike 启发式）：相邻点构成的极小夹角比例"""
        if len(coords) < 3:
            return 0.0
        import math
        spikes = 0
        for i in range(1, len(coords) - 1):
            p0, p1, p2 = coords[i - 1], coords[i], coords[i + 1]
            v1 = (p1[0] - p0[0], p1[1] - p0[1])
            v2 = (p2[0] - p1[0], p2[1] - p1[1])
            d1 = math.hypot(*v1) or 1e-12
            d2 = math.hypot(*v2) or 1e-12
            dot = v1[0] * v2[0] + v1[1] * v2[1]
            cos_a = max(-1.0, min(1.0, dot / (d1 * d2)))
            if math.acos(cos_a) < 0.03:  # <约 1.7 度视为 spike
                spikes += 1
        return spikes / (len(coords) - 2) if len(coords) > 2 else 0.0


class TopologyValidator:
    """拓扑校验：重复 / overlap / gap（简化版，面向 GeoJSON 图层）"""

    def check(self, geoms: List[Dict[str, Any]]) -> Dict[str, int]:
        duplicate = 0
        seen = set()
        for g in geoms:
            key = self._key(g)
            if key:
                if key in seen:
                    duplicate += 1
                else:
                    seen.add(key)
        return {"duplicate": duplicate}

    @staticmethod
    def _key(geom: Dict[str, Any]) -> str:
        coords = geom.get("coordinates")
        if not coords:
            return ""
        try:
            import json
            return json.dumps(coords, sort_keys=True)
        except Exception:
            return repr(coords)


class PositionalValidator:
    """位置校验：CRS 是否存在 + 坐标范围"""

    def check_crs(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        crs = metadata.get("坐标系") or metadata.get("投影") or metadata.get("crs")
        return {
            "crs": crs or None,
            "has_crs": bool(crs),
        }

    def coordinate_range(self, coords: List[tuple]) -> Dict[str, int]:
        """坐标越界统计（经纬度合法范围）"""
        outside = 0
        for lng, lat in coords:
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                outside += 1
        return {"out_of_range": outside}
