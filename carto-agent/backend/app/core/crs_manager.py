# -*- coding: utf-8 -*-
"""统一 CRS 管理（CRSManager）

支持真实坐标转换（非“经纬度≈米”近似）：
  - EPSG:4326  WGS84 经纬度（数据默认 CRS）
  - EPSG:3857  WebMercator（前端 Leaflet 渲染）
  - EPSG:4547  CGCS2000 / 3° 高斯-克吕格 CM 114E（武汉适宜投影，米制）

所有米制几何操作（simplify/buffer/distance/area/displacement）必须在 projected CRS 中执行。
"""
from typing import Any, Dict, List, Optional, Tuple

from pyproj import Transformer
from pyproj.exceptions import ProjError


EPSG_4326 = "EPSG:4326"
EPSG_3857 = "EPSG:3857"
# 武汉（约 113.5-115.5°E）适宜的 CGCS2000 高斯克吕格 3°分带，中央经线 114°E
EPSG_WUHAN_PROJECTED = "EPSG:4547"


class CRSManager:
    """统一 CRS 转换器（实际坐标转换）"""

    # 武汉中心点（用于确定适宜投影带）
    WUHAN_CENTER = (114.3055, 30.5928)  # (lng, lat)

    def __init__(self, projected_crs: str = EPSG_WUHAN_PROJECTED):
        self.projected_crs = projected_crs
        self._transformers: Dict[Tuple[str, str], Transformer] = {}

    def _transformer(self, src: str, dst: str) -> Transformer:
        key = (src, dst)
        if key not in self._transformers:
            self._transformers[key] = Transformer.from_crs(src, dst, always_xy=True)
        return self._transformers[key]

    def transform(
        self,
        coords: List[Tuple[float, float]],
        src: str,
        dst: str,
    ) -> List[Tuple[float, float]]:
        """坐标列表转换（[lng, lat] 或投影 [x, y]）"""
        if not coords:
            return []
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        tx, ty = self._transformer(src, dst).transform(xs, ys)
        return [(float(x), float(y)) for x, y in zip(tx, ty)]

    def transform_geometry(
        self,
        geom: Dict[str, Any],
        src: str,
        dst: str,
    ) -> Dict[str, Any]:
        """GeoJSON 几何坐标转换（Point/LineString/Polygon/Multi*）"""
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Point":
            if coords and len(coords) >= 2:
                return {"type": "Point", "coordinates": self.transform([(coords[0], coords[1])], src, dst)[0]}
            return geom
        if gtype == "LineString":
            return {"type": "LineString", "coordinates": self.transform([tuple(c) for c in coords], src, dst)}
        if gtype == "Polygon":
            return {"type": "Polygon", "coordinates": [
                self.transform([tuple(c) for c in ring], src, dst) for ring in coords
            ]}
        if gtype == "MultiPolygon":
            return {"type": "MultiPolygon", "coordinates": [
                [self.transform([tuple(c) for c in ring], src, dst) for ring in poly]
                for poly in coords
            ]}
        if gtype == "MultiLineString":
            return {"type": "MultiLineString", "coordinates": [
                self.transform([tuple(c) for c in line], src, dst) for line in coords
            ]}
        return geom

    def to_projected(self, lonlat: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """WGS84 经纬度 → 武汉米制投影（EPSG:4547）"""
        return self.transform(lonlat, EPSG_4326, self.projected_crs)

    def from_projected(self, projected: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """武汉米制投影 → WGS84 经纬度"""
        return self.transform(projected, self.projected_crs, EPSG_4326)

    def to_webmercator(self, lonlat: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """WGS84 → WebMercator（EPSG:3857）"""
        return self.transform(lonlat, EPSG_4326, EPSG_3857)

    def from_webmercator(self, mercator: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        """WebMercator → WGS84"""
        return self.transform(mercator, EPSG_3857, EPSG_4326)

    # ============ 米制几何操作（在 projected CRS 中执行） ============

    def simplify_meters(
        self,
        lonlat: List[Tuple[float, float]],
        tolerance_m: float,
        preserve_topology: bool = True,
    ) -> List[Tuple[float, float]]:
        """米制 Douglas-Peucker：WGS84 → 投影 → 米制简化 → 回 WGS84"""
        if len(lonlat) < 3:
            return list(lonlat)
        from shapely.geometry import LineString
        proj = self.to_projected(lonlat)
        simple = LineString(proj).simplify(tolerance_m, preserve_topology=preserve_topology)
        return self.from_projected(list(simple.coords))

    def length_meters(self, lonlat: List[Tuple[float, float]]) -> float:
        """计算 [lng, lat] 折线的真实米制长度（在投影 CRS 中）"""
        if len(lonlat) < 2:
            return 0.0
        from shapely.geometry import LineString
        return LineString(self.to_projected(lonlat)).length

    def area_meters2(self, geom: Any) -> float:
        """shapely 多边形（WGS84）的真实米制面积（在投影 CRS 中）"""
        if geom.is_empty:
            return 0.0
        return self._to_projected_shapely(geom).area

    def distance_meters(self, a: Any, b: Any) -> float:
        """shapely 几何（WGS84）间的真实米制距离（在投影 CRS 中）"""
        if a.is_empty or b.is_empty:
            return float("inf")
        return self._to_projected_shapely(a).distance(self._to_projected_shapely(b))

    def _to_projected_shapely(self, geom: Any) -> Any:
        """WGS84 shapely 几何 → 投影米制 shapely 几何"""
        from shapely.ops import transform as shapely_transform
        transformer = self._transformer(EPSG_4326, self.projected_crs)

        def fwd(x, y, z=None):
            px, py = transformer.transform(x, y)
            return px, py

        return shapely_transform(fwd, geom)

    def _from_projected_shapely(self, geom: Any) -> Any:
        """投影米制 shapely 几何 → WGS84 shapely 几何"""
        from shapely.ops import transform as shapely_transform
        transformer = self._transformer(self.projected_crs, EPSG_4326)

        def inv(x, y, z=None):
            lng, lat = transformer.transform(x, y)
            return lng, lat

        return shapely_transform(inv, geom)

    def buffer_meters(
        self,
        geom: Any,
        buffer_m: float,
    ) -> Any:
        """米制 buffer：shapely 几何（WGS84）→ 投影 → buffer → 回 WGS84"""
        return self._meters_geom_op(geom, buffer_m, "buffer")

    def _meters_geom_op(self, geom: Any, meters: float, op: str) -> Any:
        """通用米制几何操作封装"""
        g_proj = self._to_projected_shapely(geom)
        if op == "buffer":
            result = g_proj.buffer(meters)
        elif op == "simplify":
            result = g_proj.simplify(meters, preserve_topology=True)
        else:
            result = g_proj
        return self._from_projected_shapely(result)

    def simplify_geometry_meters(
        self,
        geom: Dict[str, Any],
        tolerance_m: float,
        preserve_topology: bool = True,
    ) -> Dict[str, Any]:
        """GeoJSON 几何米制简化"""
        from shapely.geometry import shape, mapping
        g = shape(geom)
        if g.is_empty:
            return geom
        return mapping(self._meters_geom_op(g, tolerance_m, "simplify"))

    def simplify_shapely_meters(self, geom: Any, tolerance_m: float) -> Any:
        """shapely 几何米制简化（WGS84 → 投影 → simplify → 回 WGS84）"""
        if geom.is_empty:
            return geom
        return self._meters_geom_op(geom, tolerance_m, "simplify")

    def buffer_shapely_meters(self, geom: Any, buffer_m: float) -> Any:
        """shapely 几何米制 buffer（WGS84 → 投影 → buffer → 回 WGS84）"""
        if geom.is_empty:
            return geom
        return self._meters_geom_op(geom, buffer_m, "buffer")


def round_trip_error(crs_manager: Optional[CRSManager] = None) -> float:
    """计算 4326 → 武汉投影 → 4326 的往返误差（米，武汉中心点）"""
    cm = crs_manager or CRSManager()
    lonlat = [cm.WUHAN_CENTER]
    proj = cm.to_projected(lonlat)
    back = cm.from_projected(proj)
    import math
    dx = (lonlat[0][0] - back[0][0]) * 111320 * math.cos(math.radians(lonlat[0][1]))
    dy = (lonlat[0][1] - back[0][1]) * 110540
    return math.hypot(dx, dy)
