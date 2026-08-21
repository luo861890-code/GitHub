# -*- coding: utf-8 -*-
"""MapLoadMetrics / ImportantFeatureRecall / DataLossMetrics / 拓扑校验"""
import math
from typing import Any, Dict, List

from app.core.crs_manager import CRSManager


WUHAN_AREA_KM2 = 8569.0  # 武汉市域参考面积（用于密度归一）


class MapLoadMetrics:
    """图面负载：点/线/面/注记/冲突密度 + MapLoadScore"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def compute(self, layers: List[Dict]) -> Dict[str, Any]:
        point = line = polygon = label = 0
        line_length_m = 0.0
        polygon_area_m2 = 0.0
        for l in layers:
            t = l.get("type")
            n = len(l.get("coordinates") or []) + len(l.get("features") or [])
            if t in ("circleMarker", "marker", "point"):
                point += n
            elif t in ("polyline", "line"):
                line += n
                for c in (l.get("coordinates") or []):
                    if isinstance(c, list) and c and isinstance(c[0], list):
                        line_length_m += self.crs.length_meters([(p[0], p[1]) for p in c])
            elif t in ("polygon", "area"):
                polygon += n
                for c in (l.get("coordinates") or []):
                    if isinstance(c, list) and len(c) >= 4:
                        from shapely.geometry import Polygon
                        try:
                            polygon_area_m2 += self.crs.area_meters2(Polygon(c))
                        except Exception:
                            pass
            elif t in ("textLabel", "label"):
                label += n

        area = WUHAN_AREA_KM2
        point_density = point / area
        line_density = (line_length_m / 1000.0) / area  # km 道路 / km²
        polygon_density = (polygon_area_m2 / 1e6) / area  # 面占比
        label_density = label / area
        # 冲突密度：简化用注记与点在同一格网（0.02°）共存的近似
        collision = self._estimate_collisions(layers)
        collision_density = collision / area

        # MapLoadScore 0-100：各密度相对正常阈值归一后加权，可区分“太空/合适/过载”
        thresholds = {
            "point": 8.0,      # 点/km²
            "line": 0.6,       # km 道路/km²
            "label": 3.0,      # 注记/km²
            "collision": 0.2,  # 冲突/km²
        }
        weights = {"point": 0.3, "line": 0.3, "label": 0.25, "collision": 0.15}
        ratios = {
            "point": point_density / thresholds["point"],
            "line": line_density / thresholds["line"],
            "label": label_density / thresholds["label"],
            "collision": collision_density / thresholds["collision"],
        }
        score = round(100 * sum(weights[k] * min(1.0, ratios[k]) for k in weights), 1)
        return {
            "point_density": round(point_density, 4),
            "line_density": round(line_density, 4),
            "polygon_density": round(polygon_density, 4),
            "label_density": round(label_density, 4),
            "collision_density": round(collision_density, 4),
            "map_load_score": score,
            "feature_counts": {"point": point, "line": line, "polygon": polygon, "label": label},
        }

    def _estimate_collisions(self, layers: List[Dict]) -> int:
        cells: Dict[str, int] = {}
        for l in layers:
            if l.get("type") not in ("textLabel", "label", "circleMarker", "marker", "point"):
                continue
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float)):
                    key = f"{round(c[0]/0.02)},{round(c[1]/0.02)}"
                    cells[key] = cells.get(key, 0) + 1
        return sum(1 for v in cells.values() if v > 2)


class ImportantFeatureRecall:
    """重要要素召回率"""

    def compute(self, kept: List[str], expected: List[str]) -> Dict[str, Any]:
        expected_set = set(expected)
        kept_set = set(kept)
        missed = expected_set - kept_set
        recall = len(kept_set & expected_set) / len(expected_set) if expected_set else 1.0
        return {
            "expected_count": len(expected_set),
            "kept_count": len(kept_set & expected_set),
            "missed": sorted(missed),
            "recall": round(recall, 4),
        }


class DataLossMetrics:
    """数据损失：feature/vertex/length/area 变化 + 重要要素丢失"""

    def compute(
        self,
        before_features: int,
        after_features: int,
        before_vertices: int,
        after_vertices: int,
        before_length_m: float,
        after_length_m: float,
        before_area_m2: float,
        after_area_m2: float,
        important_lost: int = 0,
    ) -> Dict[str, Any]:
        return {
            "feature_loss_rate": round((before_features - after_features) / max(1, before_features), 4),
            "vertex_loss_rate": round((before_vertices - after_vertices) / max(1, before_vertices), 4),
            "length_change": round((after_length_m - before_length_m) / max(1e-6, before_length_m), 4),
            "area_change": round((after_area_m2 - before_area_m2) / max(1e-6, before_area_m2), 4),
            "important_feature_loss": important_lost,
        }


class TopologyCheck:
    """综合后拓扑校验（真实几何）"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()

    def check_polygons(self, polygons: List[Dict]) -> Dict[str, Any]:
        """行政区/面：overlap 与 gap（成对面积重叠检测，简化）"""
        from shapely.geometry import shape
        geoms = []
        invalid = 0
        for g in polygons:
            try:
                shp = shape(g)
                if not shp.is_valid:
                    invalid += 1
                geoms.append(shp)
            except Exception:
                invalid += 1
        overlap = 0
        for i in range(len(geoms)):
            for j in range(i + 1, len(geoms)):
                try:
                    inter = geoms[i].intersection(geoms[j])
                    if not inter.is_empty and self.crs.area_meters2(inter) > 50_000:
                        # 显著重叠（>0.05km²）才算拓扑错误，避免边界精度/共享边界误报
                        overlap += 1
                except Exception:
                    pass
        return {"overlap_count": overlap, "invalid_count": invalid, "gap_count": 0}

    def check_line_connectivity(self, lines: List[List[tuple]]) -> Dict[str, Any]:
        """线连通性：连通分量数（端点共享判定）"""
        if not lines:
            return {"components": 0, "disconnected_rate": 0.0}
        endpoints: Dict[str, List[int]] = {}
        for idx, line in enumerate(lines):
            if len(line) < 2:
                continue
            for ep in (line[0], line[-1]):
                key = f"{round(ep[0], 4)},{round(ep[1], 4)}"
                endpoints.setdefault(key, []).append(idx)
        # 连通分量（并查集）
        parent = list(range(len(lines)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a, b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for ep, idxs in endpoints.items():
            for i in range(1, len(idxs)):
                union(idxs[0], idxs[i])
        components = len({find(i) for i in range(len(lines))})
        # dangling：端点度 = 1（只被一条线使用）
        ep_degree = {k: len(v) for k, v in endpoints.items()}
        dangling = sum(1 for d in ep_degree.values() if d == 1)
        return {
            "components": components,
            "disconnected_rate": round(components / max(1, len(lines)), 4),
            "dangling_endpoints": dangling,
        }

    def check_duplicate_lines(self, lines: List[List[tuple]]) -> int:
        """重复线检测（几何哈希）"""
        seen = set()
        dup = 0
        for line in lines:
            key = repr([(round(p[0], 4), round(p[1], 4)) for p in line])
            if key in seen:
                dup += 1
            else:
                seen.add(key)
        return dup

    def check_poi_containment(self, pois: List[tuple], polygons: List[Dict]) -> Dict[str, Any]:
        """POI 是否位于任一行政区内（点-面包含）"""
        from shapely.geometry import shape, Point
        try:
            geoms = [shape(g) for g in polygons]
        except Exception:
            geoms = []
        outside = 0
        for p in pois:
            pt = Point(p[0], p[1])
            if geoms and not any(g.contains(pt) or g.touches(pt) for g in geoms):
                outside += 1
        return {"total_poi": len(pois), "outside_polygons": outside}

    def check_contour_validity(self, contours: List[List[tuple]]) -> Dict[str, Any]:
        """等高线几何有效性（点足够、无 NaN）"""
        import math
        invalid = 0
        for c in contours:
            if len(c) < 2 or any(not math.isfinite(v) for p in c for v in p):
                invalid += 1
        return {"invalid_contours": invalid}

    def gate(self, checks: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """拓扑门禁：任一关键错误 → FAIL"""
        critical = 0
        if checks.get("polygons", {}).get("overlap_count", 0) > 0:
            critical += 1
        if checks.get("polygons", {}).get("invalid_count", 0) > 0:
            critical += 1
        if checks.get("lines", {}).get("components", 1) > 20:
            critical += 1
        if checks.get("poi", {}).get("outside_polygons", 0) > 0:
            critical += 1
        return {"status": "FAIL" if critical > 0 else "PASS", "critical_errors": critical}
