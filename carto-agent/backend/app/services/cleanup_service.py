"""地图几何质量清洗服务

针对 QA / 质量检查发现的拓扑几何硬伤提供清洗：
- 安全清洗（生成时自动执行）：
  1) 冗余重复折点：合并连续相同坐标点
  2) 无效退化几何：删除长度/面积趋近 0 的要素
  3) 重复几何要素：同一图层内去重（完全相同的坐标序列）
- 深度清洗（`POST /{map_id}/cleanup` 触发）：
  4) 多边形重叠：相邻政区面相互压盖时，以面积较大者为准剪除较小者被覆盖部分
  5) 碎小多边形：删除面积 < 0.5km² 的异常碎面

所有几何清理保持内部坐标 [lat, lng] 约定，且不改变要素属性。
"""
from typing import List, Dict, Any, Optional

from app.utils.logger import get_logger
logger = get_logger(__name__)

from app.utils.geometry import _ring_area_km2, _line_len_km, _point_in_ring, _interior_point

_TOL = 1e-9


def _geom_key(geom: list) -> str:
    """几何哈希（去重检测），与质量服务同口径：坐标保留 6 位小数"""
    if not geom:
        return ""
    if isinstance(geom[0], (int, float)):
        geom = [geom]
    return repr([round(p[0], 6) for p in geom] + [round(p[1], 6) for p in geom])


class MapCleanupService:
    """地图几何质量清洗服务"""

    def cleanup_map(self, map_data: dict, deep: bool = False) -> dict:
        """清洗地图所有图层，返回（带清洗报告的）地图数据"""
        report = {
            "vertices": 0, "degenerate": 0, "dedupe": 0,
            "overlap": 0, "sliver": 0, "admin_center": 0, "props": 0, "deep": deep,
        }
        for layer in map_data.get("layers", []) or []:
            name = layer.get("name", "")
            ltype = layer.get("type", "")
            # 0) 属性兜底：无 properties 的坐标型图层补基础属性（name/type），保证属性表可用
            self._ensure_properties(layer, report)
            # 1) 冗余重复折点（始终清理）
            self._clean_vertices(layer, report)
            # 2) 退化几何删除（始终清理）
            self._remove_degenerate(layer, report)
            # 3) 重复几何去重（始终清理）
            self._dedupe(layer, report)
            # 深度清洗：重叠 + 碎面
            if deep and ltype in ("polygon", "area") and layer.get("features"):
                self._fix_overlaps(layer, report)
                self._remove_slivers(layer, report)
        if deep:
            self._fix_admin_centers(map_data, report)
        map_data["cleanup_report"] = report
        return map_data

    # ---------- 6) 行政中心越界吸附 ----------

    def _fix_admin_centers(self, map_data: dict, report: dict) -> None:
        """行政中心点落在对应政区面外时，吸附到面内点（深度清洗）"""
        layers = map_data.get("layers", []) or []
        admin_by_name = {}
        for L in layers:
            if L.get("name") == "区县政区":
                for f in L.get("features", []) or []:
                    fname = (f.get("properties") or {}).get("name", "")
                    if fname and f.get("coordinates"):
                        admin_by_name[fname] = f.get("coordinates")
        if not admin_by_name:
            return
        changed = 0
        for L in layers:
            if L.get("name") != "区县行政中心":
                continue
            coords = L.get("coordinates") or []
            props = L.get("properties") or []
            for i, c in enumerate(coords):
                if not isinstance(c, list) or len(c) < 2:
                    continue
                fname = (props[i] or {}).get("name", "") if i < len(props) else ""
                ring = admin_by_name.get(fname)
                if ring and not _point_in_ring(c, ring):
                    ip = _interior_point(ring)
                    if ip:
                        coords[i] = ip
                        changed += 1
        if changed:
            report["admin_center"] += changed
            logger.info(f"[Cleanup] 行政中心吸附修复 {changed} 处")

    # ---------- 0) 属性兜底 ----------

    def _ensure_properties(self, layer: dict, report: dict) -> None:
        """坐标型图层缺失 properties 时补基础属性（name/type），保证属性表有内容"""
        n = len(layer.get("coordinates") or [])
        if not n:
            n = len(layer.get("features") or [])
        if not n:
            return
        if layer.get("properties"):
            return
        if layer.get("features") and (layer["features"][0].get("properties") if layer["features"] else None):
            return
        layer["properties"] = [{"name": "", "type": layer.get("name", "")} for _ in range(n)]
        report["props"] += n

    # ---------- 1) 冗余重复折点 ----------

    @staticmethod
    def _clean_ring(ring: List[list]) -> List[list]:
        """合并连续相同坐标点（保留首尾闭合结构）"""
        if not ring:
            return ring
        out = []
        for p in ring:
            if out and abs(p[0] - out[-1][0]) < _TOL and abs(p[1] - out[-1][1]) < _TOL:
                continue
            out.append(p)
        # 若首尾重复（闭合环）且合并后仍多余，保持原样（闭合点属正常）
        return out

    def _clean_vertices(self, layer: dict, report: dict) -> None:
        coords = layer.get("coordinates") or []
        changed = 0
        for i, c in enumerate(coords):
            if isinstance(c, list) and c and not isinstance(c[0], (int, float)):
                new = self._clean_ring(c)
                if len(new) != len(c):
                    changed += 1
                coords[i] = new
        for feat in layer.get("features", []) or []:
            c = feat.get("coordinates") or []
            if isinstance(c, list) and c and not isinstance(c[0], (int, float)):
                new = self._clean_ring(c)
                if len(new) != len(c):
                    changed += 1
                feat["coordinates"] = new
        if changed:
            report["vertices"] += changed

    # ---------- 2) 无效退化几何 ----------

    def _remove_degenerate(self, layer: dict, report: dict) -> None:
        ltype = layer.get("type", "")
        coords = layer.get("coordinates") or []
        props = layer.get("properties") or []
        kept = []
        kept_p = []
        removed = 0
        for i, c in enumerate(coords):
            if not isinstance(c, (list, tuple)) or not c:
                removed += 1
                continue
            if ltype in ("polygon", "area"):
                if len(c) < 3 or _ring_area_km2(c) < 1e-6:
                    removed += 1
                    continue
            elif ltype in ("polyline", "line"):
                if len(c) < 2 or _line_len_km(c) < 0.001:
                    removed += 1
                    continue
            kept.append(c)
            if i < len(props):
                kept_p.append(props[i])
        if removed:
            layer["coordinates"] = kept
            if props:
                layer["properties"] = kept_p
            report["degenerate"] += removed

        # features 面
        if ltype in ("polygon", "area"):
            feats = layer.get("features") or []
            kept_f = []
            for f in feats:
                ring = f.get("coordinates") or []
                if len(ring) < 3 or _ring_area_km2(ring) < 1e-6:
                    removed += 1
                    continue
                kept_f.append(f)
            if len(kept_f) != len(feats):
                layer["features"] = kept_f
                report["degenerate"] += (len(feats) - len(kept_f))

    # ---------- 3) 重复几何去重 ----------

    @staticmethod
    def _is_exempt(name: str) -> bool:
        """与质量检查同口径：境界线 / 道路双层渲染图层豁免"""
        return ("界" in name or "省界" in name or "(外层)" in name or "(内层)" in name)

    def _dedupe(self, layer: dict, report: dict) -> None:
        if self._is_exempt(layer.get("name", "")):
            return
        ltype = layer.get("type", "")
        if ltype not in ("polygon", "area", "polyline", "line"):
            return
        seen = set()
        removed = 0
        coords = layer.get("coordinates") or []
        props = layer.get("properties") or []
        kept = []
        kept_p = []
        for i, c in enumerate(coords):
            if not isinstance(c, list) or not c or isinstance(c[0], (int, float)):
                kept.append(c)
                if i < len(props):
                    kept_p.append(props[i])
                continue
            k = _geom_key(c)
            if k in seen:
                removed += 1
                continue
            seen.add(k)
            kept.append(c)
            if i < len(props):
                kept_p.append(props[i])
        if removed:
            layer["coordinates"] = kept
            if props:
                layer["properties"] = kept_p
            report["dedupe"] += removed

        feats = layer.get("features") or []
        kept_f = []
        for f in feats:
            ring = f.get("coordinates") or []
            if not ring:
                kept_f.append(f)
                continue
            k = _geom_key(ring)
            if k in seen:
                removed += 1
                continue
            seen.add(k)
            kept_f.append(f)
        if len(kept_f) != len(feats):
            layer["features"] = kept_f
            report["dedupe"] += (len(feats) - len(kept_f))

    # ---------- 4) 多边形重叠修复 ----------

    def _fix_overlaps(self, layer: dict, report: dict) -> None:
        """相邻政区面相互压盖时，以面积较大者为准剪除较小者被覆盖部分"""
        if layer.get("name") != "区县政区":
            return
        feats = layer.get("features") or []
        if len(feats) < 2:
            return
        changed = 0
        for i in range(len(feats)):
            for j in range(i + 1, len(feats)):
                ri, rj = feats[i].get("coordinates") or [], feats[j].get("coordinates") or []
                if not ri or not rj:
                    continue
                pi = _ring_to_shapely(ri)
                pj = _ring_to_shapely(rj)
                if pi is None or pj is None:
                    continue
                inter = pi.intersection(pj)
                if inter.is_empty:
                    continue
                # 面积小者被剪除
                if _ring_area_km2(ri) < _ring_area_km2(rj):
                    new_ring = _shapely_to_ring(pi.difference(pj))
                    if new_ring:
                        feats[i]["coordinates"] = new_ring
                        changed += 1
                else:
                    new_ring = _shapely_to_ring(pj.difference(pi))
                    if new_ring:
                        feats[j]["coordinates"] = new_ring
                        changed += 1
        if changed:
            report["overlap"] += changed
            logger.info(f"[Cleanup] 区县政区重叠修复 {changed} 处")

    # ---------- 5) 碎小多边形 ----------

    def _remove_slivers(self, layer: dict, report: dict) -> None:
        feats = layer.get("features") or []
        kept = []
        removed = 0
        for f in feats:
            ring = f.get("coordinates") or []
            area = _ring_area_km2(ring)
            if 0 < area < 0.5:
                removed += 1
                continue
            kept.append(f)
        if removed:
            layer["features"] = kept
            report["sliver"] += removed
            logger.info(f"[Cleanup] 碎小多边形删除 {removed} 处")


# ---------- shapely 辅助（内部 [lat,lng] ↔ shapely (x=lng,y=lat)） ----------

def _ring_to_shapely(ring: List[list]):
    """内部环 [lat,lng] → shapely Polygon（x=经度, y=纬度）"""
    try:
        from shapely.geometry import Polygon
    except Exception:
        return None
    coords = [(float(p[1]), float(p[0])) for p in ring if isinstance(p, list) and len(p) >= 2]
    if len(coords) < 3:
        return None
    if coords[0] != coords[-1]:
        coords = coords + [coords[0]]
    try:
        return Polygon(coords)
    except Exception:
        return None


def _shapely_to_ring(poly) -> Optional[List[list]]:
    """shapely Polygon → 内部环 [lat,lng]（多部件取面积最大者）"""
    if poly is None or poly.is_empty:
        return None
    if poly.geom_type == "MultiPolygon":
        parts = sorted(list(poly.geoms), key=lambda p: p.area, reverse=True)
        if not parts:
            return None
        poly = parts[0]
    if poly.geom_type != "Polygon" or poly.exterior is None:
        return None
    ring = [[p[1], p[0]] for p in poly.exterior.coords]
    # 去除重复闭合点（保持与源数据一致的简洁环）
    if len(ring) > 2 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring if len(ring) >= 3 else None

