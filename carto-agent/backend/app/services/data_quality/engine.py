# -*- coding: utf-8 -*-
"""统一 GIS DataQualityEngine：对所有图层执行质量检查并输出机器可读报告"""
from typing import Any, Dict, List, Optional

from .geometry import GeometryValidator, TopologyValidator, PositionalValidator
from .attribute import (
    AttributeValidator,
    CompletenessValidator,
    MetadataValidator,
    SourceValidator,
)


class DataQualityEngine:
    """统一数据质量引擎（进入制图流程前必须通过）"""

    def __init__(self):
        self.geometry = GeometryValidator()
        self.topology = TopologyValidator()
        self.positional = PositionalValidator()
        self.attribute = AttributeValidator()
        self.completeness = CompletenessValidator()
        self.metadata = MetadataValidator()
        self.source = SourceValidator()

    def check_map(
        self,
        map_data: Dict[str, Any],
        expected_layers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """对地图数据（map_data.layers）执行完整质检"""
        layers = map_data.get("layers", [])
        metadata = map_data.get("metadata") or {}
        source_text = (metadata.get("数据来源") or metadata.get("资料来源")
                       or metadata.get("source") or "")

        # 展平所有几何
        geoms: List[Dict[str, Any]] = []
        feature_props: List[Dict[str, Any]] = []
        all_coords: List[tuple] = []
        for l in layers:
            feats = l.get("features") or []
            coords = l.get("coordinates") or []
            if feats:
                for f in feats:
                    g = f.get("geometry")
                    if g:
                        geoms.append(g)
                    feature_props.append(f.get("properties") or {})
                    all_coords.extend(self._coords_of_feature(f))
            elif coords:
                # coordinates + properties 模式：按属性对齐
                props = l.get("properties") or []
                feature_props.extend(props if props else [{} for _ in coords])
                for c in coords:
                    if isinstance(c, list) and c and isinstance(c[0], (int, float)):
                        all_coords.append((float(c[1]), float(c[0])))
                    elif isinstance(c, list) and c and isinstance(c[0], list):
                        # 线/面坐标，构造临时几何做校验
                        gtype = "LineString" if l.get("type") in ("polyline", "line") else "Polygon"
                        geoms.append({"type": gtype, "coordinates": c if gtype == "LineString" else [c]})

        # 几何校验
        invalid = 0
        empty = 0
        self_intersect = 0
        sliver = 0
        for g in geoms:
            r = self.geometry.check_geometry(g)
            if r["invalid"]:
                invalid += 1
            if r["empty"]:
                empty += 1
            if r["self_intersection"]:
                self_intersect += 1
            if r["sliver"]:
                sliver += 1

        # 拓扑（重复）
        topo = self.topology.check(geoms)

        # 位置（CRS + 坐标越界）
        crs_report = self.positional.check_crs(metadata)
        coord_range = self.positional.coordinate_range(all_coords)

        # 属性
        attr = self.attribute.check(feature_props)

        # 完整性（期望图层）
        layer_names = [l.get("name", "") for l in layers]
        completeness = self.completeness.check(
            layer_names, expected_layers or []
        ) if expected_layers else {"missing": [], "completeness": 1.0}

        # 元数据
        meta_report = self.metadata.check(metadata)

        # 来源
        source_report = self.source.check(source_text)

        # 质量评分（0-100，加权扣分）
        score = 100.0
        feature_count = max(1, len(geoms) + attr["feature_count"] or 1)
        if invalid:
            score -= min(40, invalid / feature_count * 100)
        if self_intersect:
            score -= min(20, self_intersect / feature_count * 50)
        if topo["duplicate"]:
            score -= min(15, topo["duplicate"] / feature_count * 30)
        if attr["missing_rate"] > 0.05:
            score -= min(20, attr["missing_rate"] * 40)
        if not crs_report["has_crs"]:
            score -= 15
        for m in meta_report["missing"]:
            score -= 5
        if coord_range["out_of_range"]:
            score -= min(15, coord_range["out_of_range"] / feature_count * 100)
        score = round(max(0.0, score), 1)

        status = "PASS" if score >= 85 else ("WARNING" if score >= 65 else "FAIL")
        if invalid > 0 or self_intersect > 0:
            status = "WARNING" if status == "PASS" else status

        return {
            "dataset": map_data.get("name", "") or map_data.get("map_id", ""),
            "feature_count": len(geoms) + attr["feature_count"],
            "invalid_geometry": invalid,
            "empty_geometry": empty,
            "self_intersection": self_intersect,
            "sliver": sliver,
            "duplicate": topo["duplicate"],
            "out_of_range_coords": coord_range["out_of_range"],
            "missing_attributes": attr["missing_name"],
            "missing_name_rate": round(attr["missing_rate"], 4),
            "missing_layers": completeness["missing"],
            "crs": crs_report["crs"],
            "source": source_report["source"],
            "source_priority": source_report["priority_label"],
            "metadata_missing": meta_report["missing"],
            "quality_score": score,
            "status": status,
        }

    @staticmethod
    def _coords_of_feature(f: Dict[str, Any]) -> List[tuple]:
        g = f.get("geometry") or {}
        coords = g.get("coordinates") or []
        out = []
        if g.get("type") == "Point" and len(coords) >= 2:
            out.append((float(coords[1]), float(coords[0])))
        return out
