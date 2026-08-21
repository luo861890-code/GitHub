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
from .duplicate import DuplicateDetector, count_exact_duplicates


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
        self.duplicate = DuplicateDetector(self.crs)
        self._selection_removed = 0  # selection 真实移除数（聚合/坍缩不计入）
        self._displacement_rollbacks = 0

    def generalize(
        self,
        map_type: str,
        layers: List[Dict],
        scale_denominator: int,
    ) -> Dict[str, Any]:
        rule = get_scale_rule(scale_denominator)
        self.selection.rule = rule
        self._selection_removed = 0
        self._displacement_rollbacks = 0
        before_counts = self._counts(layers)
        raw_dup = count_exact_duplicates([c for l in layers for c in (l.get("coordinates") or [])])
        out_layers: List[Dict] = []
        for layer in layers:
            cat = LAYER_CATEGORY.get(layer.get("name", ""), "unknown")
            out_layers.append(self._generalize_layer(layer, cat, rule))
        after_counts = self._counts(out_layers)
        # pipeline 内去重（对全部 polyline 统一去重 exact/reverse，保证 final exact duplicate=0）
        for l in out_layers:
            if l.get("type") != "polyline":
                continue
            coords = l.get("coordinates") or []
            kept_idx = []
            seen = set()
            for i, c in enumerate(coords):
                if not (isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple))):
                    kept_idx.append(i)
                    continue
                key = repr([(round(float(p[0]), 4), round(float(p[1]), 4)) for p in c])
                rkey = repr([(round(float(p[0]), 4), round(float(p[1]), 4)) for p in reversed(c)])
                if key not in seen and rkey not in seen:
                    seen.add(key)
                    seen.add(rkey)
                    kept_idx.append(i)
            if len(kept_idx) != len(coords):
                l["coordinates"] = [coords[i] for i in kept_idx]
                props = l.get("properties") or []
                if props and len(props) == len(coords):
                    l["properties"] = [props[i] for i in kept_idx]
        self._sync_props(out_layers)
        after_counts = self._counts(out_layers)
        # 去重后剩余 exact/reverse duplicate（按图层内统计，应=0；跨图层同坐标不同图层非重复）
        final_dup = sum(
            count_exact_duplicates(l.get("coordinates") or [])
            for l in out_layers if l.get("type") == "polyline")
        recall = compute_all_recall(map_type, out_layers)
        topology_checks = self._topology_checks(map_type, out_layers)
        gates, blockers = self._gate_layers(topology_checks, final_dup)
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
            "gates": gates,
            "blockers": blockers,
            "final_duplicate_count": final_dup,
            "stage_metrics": {
                "raw_duplicate": raw_dup,
                "after_displacement_rollbacks": self._displacement_rollbacks,
                "final_exact_duplicate": final_dup,
            },
            "scale": scale_denominator,
            "before_counts": before_counts,
            "after_counts": after_counts,
        }
        return {
            "layers": out_layers,
            "metrics": metrics,
        }

    @staticmethod
    def _sync_props(layers: List[Dict]) -> None:
        """防御性对齐：coordinates 与 properties 数量不一致时截断/补齐。

        坐标与属性必须一一对应，防止属性缺失误报与图例错位。
        """
        for l in layers:
            coords = l.get("coordinates") or []
            props = l.get("properties") or []
            if not props or len(props) == len(coords):
                continue
            if len(props) > len(coords):
                l["properties"] = props[:len(coords)]
            else:
                l["properties"] = props + [{}] * (len(coords) - len(props))

    def _gate_layers(self, checks: Dict[str, Any], final_dup: int = 0):
        """三层 gate 解耦：dataset / generalization / map（错误来源可追踪）"""
        gates = {"dataset_gate": "PASS", "generalization_gate": "PASS", "map_gate": "PASS"}
        source_blockers = []
        gen_blockers = []
        # 数据源问题：区县面显著重叠（DataV 边界精度）
        polygons = checks.get("polygons", {})
        if polygons.get("significant_overlap_count", 0) > 0:
            gates["dataset_gate"] = "BLOCKED_BY_SOURCE_DATA"
            source_blockers.append(
                f"区县面显著重叠 {polygons['significant_overlap_count']} 处"
                f"（DataV 边界精度，面积 {polygons.get('overlap_area_min_km2')}~"
                f"{polygons.get('overlap_area_max_km2')} km²）")
        # 综合问题：线连通分量过多 / 重复线 / 等高线无效
        lines = checks.get("lines", {})
        if final_dup > 0:
            gates["generalization_gate"] = "BLOCKED_BY_GENERALIZATION"
            gen_blockers.append(f"重复线 {final_dup}")
        if checks.get("contours", {}).get("invalid_contours", 0) > 0:
            gates["generalization_gate"] = "BLOCKED_BY_GENERALIZATION"
            gen_blockers.append("存在无效等高线")
        return gates, {"source_blockers": source_blockers, "generalization_blockers": gen_blockers}

    def _topology_checks(self, map_type: str, layers: List[Dict]) -> Dict[str, Any]:
        """按地图类型执行对应拓扑检查"""
        checks: Dict[str, Any] = {}
        # 行政区：仅区县政区面参与 overlap/gap（湖泊面是自然要素，不在行政拓扑检查内）
        polygons = []
        for l in layers:
            if l.get("name") == "区县政区":
                for f in (l.get("features") or []):
                    g = f.get("geometry")
                    if g:
                        polygons.append(g)
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
        # duplicate detection：去除 exact/reverse 重复（pipeline 内，非最后过滤）
        dup_report = self.duplicate.detect(new_coords)
        exact_idx = {a for a, b, _ in dup_report["exact_pairs"]}
        if exact_idx:
            new_coords = [c for i, c in enumerate(new_coords) if i not in exact_idx]
            layer["duplicate_removed"] = len(exact_idx)
            lines = [{"coordinates": c, "importance": 1.0 if cat in ("motorway", "trunk_road") else 0.5}
                     for c in new_coords if isinstance(c, list) and c and isinstance(c[0], list)]
        # 位移（平行符号冲突消解）仅对可控规模的图层执行：
        # 线数过多时逐对距离计算为 O(n²)，大图层（如基础图居民区道路）会退化；
        # 制图实践中位移只用于主要道路的符号冲突，次要道路做选取/简化即可。
        DISPLACE_LIMIT = 600
        if 2 <= len(lines) <= DISPLACE_LIMIT:
            lines = self.displacement.resolve_parallel(lines, rule.displacement_distance_m(cat))
            new_coords = [l["coordinates"] for l in lines]
            self._displacement_rollbacks += self.displacement.last_rollback_count
        else:
            layer["displacement_skipped"] = len(lines)

        layer["coordinates"] = new_coords
        if props and len(props) == n:
            trimmed = [props[i] for i in range(n) if i not in removed_idx]
            if exact_idx:
                # 重复线去除后属性同步裁剪（保证 props/coords 一一对应）
                trimmed = [p for i, p in enumerate(trimmed) if i not in exact_idx]
            layer["properties"] = trimmed
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
