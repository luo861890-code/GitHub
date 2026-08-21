# -*- coding: utf-8 -*-
"""GeneralizationEngine：按 map_type + scale 对图层执行真实制图综合。

系统图层坐标约定为 [lat, lng]；CRSManager 期望 [lng, lat]，故内部统一转换。
"""
from typing import Any, Dict, List

from app.core.crs_manager import CRSManager
from app.core.cartographic_profiles import LAYER_CATEGORY
from app.core.constants import WUHAN_DISTRICTS

from .scale_rules import get_scale_rule
from .selection import Selection, road_importance
from .simplification import Simplification
from .aggregation import Aggregation
from .displacement import Displacement
from .collapse import Collapse
from .exaggeration import Exaggeration
from .metrics import MapLoadMetrics, ImportantFeatureRecall, DataLossMetrics, TopologyCheck
from .ground_truth import compute_all_recall
from .terrain_scale_rules import contour_interval, select_contours


def _to_lonlat(latlng: List[tuple]) -> List[tuple]:
    """[lat, lng] -> [lng, lat]"""
    return [(c[1], c[0]) for c in latlng]


def _to_latlng(lonlat: List[tuple]) -> List[tuple]:
    """[lng, lat] -> [lat, lng]"""
    return [(c[1], c[0]) for c in lonlat]


class GeneralizationEngine:
    """制图综合引擎：真实 Selection/Simplification/Aggregation/Displacement/Collapse/Exaggeration"""

    def __init__(self, crs_manager: CRSManager = None):
        self.crs = crs_manager or CRSManager()
        self.selection = Selection(None)
        self.simplification = Simplification(self.crs)
        self.aggregation = Aggregation(self.crs)
        self.displacement = Displacement(self.crs)
        self.collapse = Collapse(self.crs)
        self.exaggeration = Exaggeration(self.crs)
        self.load = MapLoadMetrics(self.crs)
        self.recall = ImportantFeatureRecall()
        self.loss = DataLossMetrics()
        self.topology = TopologyCheck(self.crs)
        self._selection_removed = 0  # selection 真实移除数（聚合/坍缩不计入）

    def generalize(
        self,
        map_type: str,
        layers: List[Dict],
        scale_denominator: int,
    ) -> Dict[str, Any]:
        rule = get_scale_rule(scale_denominator)
        self.selection.rule = rule
        self._selection_removed = 0
        before_counts = self._counts(layers)
        out_layers: List[Dict] = []
        for layer in layers:
            cat = LAYER_CATEGORY.get(layer.get("name", ""), "unknown")
            out_layers.append(self._generalize_layer(layer, cat, rule))
        after_counts = self._counts(out_layers)
        recall = compute_all_recall(map_type, out_layers)
        topology_checks = self._topology_checks(map_type, out_layers)
        gate = self.topology.gate(topology_checks)
        metrics = {
            "map_load": self.load.compute(out_layers),
            "data_loss": self.loss.compute(
                before_features=before_counts["features"],
                after_features=before_counts["features"] - self._selection_removed,
                before_vertices=before_counts["vertices"],
                after_vertices=after_counts["vertices"],
                before_length_m=before_counts["length_m"],
                after_length_m=after_counts["length_m"],
                before_area_m2=before_counts["area_m2"],
                after_area_m2=after_counts["area_m2"],
            ),
            "recall": recall,
            "topology": topology_checks,
            "topology_gate": gate,
            "scale": scale_denominator,
            "before_counts": before_counts,
            "after_counts": after_counts,
        }
        return {
            "layers": out_layers,
            "metrics": metrics,
        }

    def _topology_checks(self, map_type: str, layers: List[Dict]) -> Dict[str, Any]:
        """按地图类型执行对应拓扑检查"""
        checks: Dict[str, Any] = {}
        # 行政区：多边形 overlap/validity
        polygons = []
        for l in layers:
            if l.get("name") == "区县政区":
                for f in (l.get("features") or []):
                    g = f.get("geometry")
                    if g:
                        polygons.append(g)
            elif l.get("type") in ("polygon", "area") and "湖泊" in (l.get("name") or ""):
                for c in (l.get("coordinates") or []):
                    if isinstance(c, list) and len(c) >= 4:
                        polygons.append({"type": "Polygon", "coordinates": [[(p[1], p[0]) for p in c]]})
        if polygons:
            checks["polygons"] = self.topology.check_polygons(polygons)

        # 交通：线连通/重复
        if map_type == "traffic":
            lines = []
            for l in layers:
                if l.get("type") == "polyline":
                    for c in (l.get("coordinates") or []):
                        if isinstance(c, list) and c and isinstance(c[0], list):
                            lines.append([(p[0], p[1]) for p in c])
            if lines:
                checks["lines"] = self.topology.check_line_connectivity(lines)
                checks["lines"]["duplicate"] = self.topology.check_duplicate_lines(lines)

        # 旅游：POI 归属（用区县政区面）
        if map_type == "tourism":
            pois = []
            for l in layers:
                if l.get("type") in ("circleMarker", "marker", "point"):
                    for c in (l.get("coordinates") or []):
                        if isinstance(c, list) and len(c) >= 2:
                            pois.append((c[1], c[0]))
            if pois and polygons:
                checks["poi"] = self.topology.check_poi_containment(pois, polygons)

        # 地势：等高线有效性
        if map_type == "terrain":
            contours = []
            for l in layers:
                if "等高线" in (l.get("name") or ""):
                    for c in (l.get("coordinates") or []):
                        if isinstance(c, list) and c and isinstance(c[0], list):
                            contours.append([(p[0], p[1]) for p in c])
            checks["contours"] = self.topology.check_contour_validity(contours)
        return checks

    def _generalize_layer(self, layer: Dict, cat: str, rule) -> Dict:
        name = layer.get("name", "")
        t = layer.get("type", "")
        layer = dict(layer)

        if t == "polyline" and ("道路" in name or cat in ("motorway", "trunk_road", "primary_road", "secondary_road", "minor_road")):
            return self._generalize_roads(layer, cat, rule)
        if t == "polyline" and cat in ("metro", "railway"):
            return self._simplify_polyline(layer, rule.tolerance_m(cat))
        if t == "polyline" and "等高线" in name:
            return self._generalize_contours(layer, rule)
        if t in ("circleMarker", "marker", "point"):
            if cat == "peak":
                return layer  # 山峰点保留（重要地形特征，不聚类不裁剪）
            return self._generalize_pois(layer, cat, rule)
        if t in ("polygon", "area"):
            return self._generalize_polygons(layer, cat, rule)
        return layer

    def _simplify_polyline(self, layer: Dict, tol: float) -> Dict:
        new_coords = []
        for c in (layer.get("coordinates") or []):
            if isinstance(c, list) and c and isinstance(c[0], list):
                lonlat = _to_lonlat([(p[0], p[1]) for p in c])
                simplified = self.crs.simplify_meters(lonlat, tol, preserve_topology=True)
                new_coords.append(_to_latlng(simplified))
            else:
                new_coords.append(c)
        layer["coordinates"] = new_coords
        return layer

    def _generalize_contours(self, layer: Dict, rule) -> Dict:
        """地势图等高线：动态等高距选取 + 米制简化"""
        from .terrain_scale_rules import contour_interval
        coords = layer.get("coordinates") or []
        props = layer.get("properties") or []
        n = len(coords)
        elevations = []
        for p in props:
            if isinstance(p, dict) and p.get("ele") is not None:
                try:
                    elevations.append(float(p["ele"]))
                except (TypeError, ValueError):
                    pass
        if not elevations:
            return self._simplify_polyline(
                layer, rule.tolerance_m("contour_minor" if "首曲线" in layer.get("name", "") else "contour_major"))
        relief = max(elevations) - min(elevations)
        interval = contour_interval(rule.scale_denominator, 30.0, relief)
        # 选取：保留 elevation % interval == 0
        kept_coords, kept_props = [], []
        removed = 0
        for i, c in enumerate(coords):
            ele = None
            if i < len(props) and isinstance(props[i], dict):
                try:
                    ele = float(props[i].get("ele"))
                except (TypeError, ValueError):
                    ele = None
            if ele is None or abs(ele) % interval < 1e-9:
                if isinstance(c, list) and c and isinstance(c[0], list):
                    simplified = self.crs.simplify_meters(
                        _to_lonlat([(p[0], p[1]) for p in c]),
                        rule.tolerance_m("contour_minor" if "首曲线" in layer.get("name", "") else "contour_major"),
                        preserve_topology=True)
                    kept_coords.append(_to_latlng(simplified))
                else:
                    kept_coords.append(c)
                if i < len(props):
                    kept_props.append(props[i])
            else:
                removed += 1
        layer["coordinates"] = kept_coords
        layer["properties"] = kept_props
        layer["contour_interval"] = interval
        layer["contour_removed"] = removed
        layer["contour_kept"] = len(kept_coords)
        layer["contour_reason"] = (
            f"等高距 {interval}m（scale 1:{rule.scale_denominator}，DEM 30m，起伏 {relief:.0f}m）")
        return layer

    def _generalize_roads(self, layer: Dict, cat: str, rule) -> Dict:
        coords = layer.get("coordinates") or []
        props = layer.get("properties") or []
        n = len(coords)
        if n == 0:
            return layer

        endpoints: Dict[str, int] = {}
        for c in coords:
            if isinstance(c, list) and c and isinstance(c[0], list):
                for ep in (c[0], c[-1]):
                    key = f"{round(ep[0], 4)},{round(ep[1], 4)}"
                    endpoints[key] = endpoints.get(key, 0) + 1
        scored = []
        for i, c in enumerate(coords):
            if not (isinstance(c, list) and c and isinstance(c[0], list)):
                continue
            length = self.crs.length_meters(_to_lonlat([(p[0], p[1]) for p in c]))
            conn = 0
            for ep in (c[0], c[-1]):
                conn += endpoints.get(f"{round(ep[0], 4)},{round(ep[1], 4)}", 1) - 1
            scored.append({"idx": i, "importance": road_importance(cat, length, conn),
                           "coords": c, "length": length, "conn": conn})

        budget = self.selection.budget_for_scale(cat, len(scored))
        kept = self.selection.select_features(scored, budget, "importance")
        kept_idx = {k["idx"] for k in kept}
        removed_idx = set(range(len(coords))) - kept_idx
        self._selection_removed += len(removed_idx)

        tol = rule.tolerance_m(cat)
        new_coords = []
        for i, c in enumerate(coords):
            if i in removed_idx:
                continue
            if isinstance(c, list) and c and isinstance(c[0], list):
                simplified = self.crs.simplify_meters(
                    _to_lonlat([(p[0], p[1]) for p in c]), tol, preserve_topology=True)
                new_coords.append(_to_latlng(simplified))
            else:
                new_coords.append(c)

        # displacement：平行近距线位移（真实几何偏移）
        lines = [{"coordinates": c, "importance": 1.0 if cat in ("motorway", "trunk_road") else 0.5}
                 for c in new_coords if isinstance(c, list) and c and isinstance(c[0], list)]
        if len(lines) >= 2:
            lines = self.displacement.resolve_parallel(lines, rule.displacement_distance_m(cat))
            new_coords = [l["coordinates"] for l in lines]

        layer["coordinates"] = new_coords
        if props and len(props) == n:
            layer["properties"] = [props[i] for i in range(n) if i not in removed_idx]
        return layer

    def _generalize_pois(self, layer: Dict, cat: str, rule) -> Dict:
        coords = layer.get("coordinates") or []
        props = layer.get("properties") or []
        n = len(coords)
        if n == 0:
            return layer
        pois = []
        for i, c in enumerate(coords):
            imp = (props[i] or {}).get("importance", 0.5) if i < len(props) else 0.5
            pois.append({"idx": i, "importance": imp, "coords": c})
        budget = self.selection.budget_for_scale(cat, n)
        kept, removed = self.selection.select_pois(pois, budget)
        self._selection_removed += len(removed)
        kept_lonlat = [_to_lonlat([tuple(p["coords"])])[0] for p in kept
                       if isinstance(p["coords"], list) and len(p["coords"]) >= 2]
        clusters = self.aggregation.cluster_points(kept_lonlat, rule.aggregation_distance_m(cat))
        new_coords = [_to_latlng([tuple(c["centroid"])])[0] for c in clusters]
        layer["coordinates"] = new_coords
        if props and len(props) == n:
            kept_idx = [p["idx"] for p in kept]
            layer["properties"] = [props[i] for i in kept_idx][:len(new_coords)]
        layer["cluster_count"] = len(clusters)
        return layer

    def _generalize_polygons(self, layer: Dict, cat: str, rule) -> Dict:
        name = layer.get("name", "")
        if cat == "district_boundary" or "区县政区" in name:
            # 行政区划面：不删除任何合法行政区，13 区全保留；features 形式不在此做几何综合
            layer["_generalization"] = {"operation": "keep_all_districts", "reason": "行政区不删除"}
            return layer
        if "湖泊" in name:
            min_area = 100_000.0
            kept_coords = []
            for c in (layer.get("coordinates") or []):
                if not (isinstance(c, list) and len(c) >= 4):
                    kept_coords.append(c)
                    continue
                geom = {"type": "Polygon", "coordinates": [[(p[1], p[0]) for p in c]]}
                if self.collapse.should_collapse(geom, min_area):
                    pt = self.collapse.collapse_to_point(geom)
                    kept_coords.append([pt["coordinates"][1], pt["coordinates"][0]])
                else:
                    kept_coords.append(c)
            layer["coordinates"] = kept_coords
        return layer

    def _counts(self, layers: List[Dict]) -> Dict[str, float]:
        features = vertices = 0
        length_m = 0.0
        area_m2 = 0.0
        for l in layers:
            for c in (l.get("coordinates") or []):
                if isinstance(c, list) and c and isinstance(c[0], list):
                    features += 1
                    vertices += len(c)
                    try:
                        length_m += self.crs.length_meters(_to_lonlat([(p[0], p[1]) for p in c]))
                    except Exception:
                        pass
                elif isinstance(c, list) and c and isinstance(c[0], (int, float)):
                    features += 1
                    vertices += 1
            features += len(l.get("features") or [])
        return {"features": features, "vertices": vertices, "length_m": length_m, "area_m2": area_m2}
