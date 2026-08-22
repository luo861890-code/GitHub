"""地图生成与管理服务 - 生成JSON格式地图数据并支持动态修改

MapService负责地图的完整生命周期管理：
- 生成地图：调用OSM服务获取真实地理数据，构建结构化地图JSON
- 管理图层：增删图层、修改样式、添加/删除要素
- 视图控制：中心点、缩放级别、底图主题
- 多源数据融合：通过DataSourceRegistry统一接入OSM/高德/天地图等数据源
- 所有修改方法返回更新后的完整地图数据，便于前端实时更新
"""
from app.utils.logger import get_logger
logger = get_logger(__name__)
import json
import os
import re
import time
import threading
import shutil
from collections import OrderedDict
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import (
    CITY_BBOX,
    CITY_ADCODES,
    MAP_TYPE_OSM_TAGS,
    MAP_STYLES,
    MAP_THEMES,
    WUHAN_LANDMARKS,
    CITY_LANDMARKS,
    WUHAN_DISTRICTS,
    BUILDING_STYLES,
    ROAD_CLASSIFICATION,
    RAILWAY_CLASSIFICATION,
    TOURISM_CATEGORIES,
    POI_STYLES,
    WATERWAY_STYLES,
    WATER_SYMBOL_STYLES,
    ADMIN_CENTER_STYLES,
    WUHAN_GOV_COORD,
    WUHAN_WATER_FALLBACK,
    WUHAN_GIS_POI,
    GREENSPACE_STYLES,
    LANDUSE_STYLES,
    LEGEND_TEMPLATES,
    LABEL_STYLES,
    THEMATIC_MAP_CONFIG,
)
from app.core.exceptions import MapGenerationError
from app.utils.helpers import generate_id, get_timestamp, ensure_dir
from app.utils.geometry import _point_in_ring

# 多源数据融合适配器
from app.services.data_source_adapter import (
    DataSourceRegistry,
    DataQuery,
    DataResult,
    OSMSourceAdapter,
    AmapPOIAdapter,
    TiandituTileAdapter,
)


class MapService:
    """地图生成与管理服务

    使用内存字典存储地图数据，支持地图的生成、查询、修改和删除。
    每个地图包含多个图层，每个图层包含多个地理要素。
    """

    # 防抖写入参数：修改后延迟 2 秒写入，期间的新修改会重置计时器
    _SAVE_DEBOUNCE_SECONDS: float = 2.0
    # 主文件保留地图数量上限，超出部分自动归档到 data/archive/maps/
    MAPS_MAIN_LIMIT: int = 10

    def __init__(self, osm_service=None, persist_path: Optional[str] = None):
        """初始化地图服务

        Args:
            osm_service: OSM数据获取服务实例，用于获取真实地理数据
            persist_path: 地图数据持久化文件路径，默认 data/maps.json
        """
        self.osm_service = osm_service
        # 索引：{map_id: 摘要}（轻量，启动即载入）
        self.maps: Dict[str, dict] = {}
        # LRU 缓存：仅保留最近使用的完整地图数据
        self._map_cache: "OrderedDict[str, dict]" = OrderedDict()
        self._map_cache_max = 3
        # 持久化：重启后自动恢复已生成的地图
        self.persist_path = persist_path or os.path.join(settings.data_dir, "maps.json")
        # 按地图独立存储目录（data/maps/{map_id}.json）
        self.maps_dir = os.path.join(os.path.dirname(self.persist_path), "maps")
        # 历史地图归档目录（迁移后的旧地图按 map_id 独立存放，按需加载）
        self.archive_dir = os.path.join(os.path.dirname(self.persist_path), "archive", "maps")
        # 防抖写入相关
        self._save_timer: Optional[threading.Timer] = None
        self._save_lock = threading.Lock()
        # LocalGeoService 缓存单例（避免每次 generate_map 都重新实例化）
        self._local_geo_service = None

        # ========== 多源数据融合适配器注册中心 ==========
        self.data_registry = DataSourceRegistry()
        # 注册 OSM 适配器（核心数据源，始终可用）
        self.data_registry.register(OSMSourceAdapter(self.osm_service))
        # 高德 POI 适配器（仅在有 API Key 时注册）
        if os.getenv("AMAP_KEY") or os.getenv("AMAP_API_KEY"):
            self.data_registry.register(AmapPOIAdapter())
        else:
            logger.info("[MapService] 未配置 AMAP_KEY，高德 POI 适配器未注册"
                  "（在 .env 中设置 AMAP_KEY 后启用）")
        # 天地图瓦片适配器（仅在有 API Key 时注册）
        if os.getenv("TIANDITU_KEY"):
            self.data_registry.register(TiandituTileAdapter())
        else:
            logger.info("[MapService] 未配置 TIANDITU_KEY，天地图适配器未注册"
                  "（在 .env 中设置 TIANDITU_KEY 后启用）")

        self._load()
        logger.info(f"[MapService] 初始化完成，已注册数据源:"
              f" {self.data_registry.get_available_sources()}")

    def _load(self):
        """从磁盘加载地图数据（重启恢复）——带容错
        
        新版存储：maps.json 为轻量索引，完整地图按 map_id 独立存放；
        检测到旧版全量数据（含 layers）时自动迁移。
        """
        backup_path = self.persist_path + ".bak"
        for source_path, source_label in [(self.persist_path, "主文件"), (backup_path, "备份文件")]:
            if not os.path.exists(source_path):
                continue
            try:
                with open(source_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    first = next(iter(data.values()), {})
                    if isinstance(first, dict) and "layers" in first:
                        self._migrate_to_lazy(data)
                    else:
                        self.maps = data
                    logger.info(f"[MapService] 已从{source_label} {source_path} 恢复 {len(self.maps)} 张地图")
                    return
            except (json.JSONDecodeError, OSError) as e:
                logger.info(f"[MapService] {source_label}加载失败: {e}")
                # 记录损坏文件以便排查
                corrupted = self.persist_path + f".corrupted.{int(time.time())}"
                try:
                    os.rename(source_path, corrupted)
                    logger.info(f"[MapService] 损坏文件已重命名: {corrupted}")
                except OSError:
                    pass
        # 全部恢复失败，从空开始（下次保存自动修复）
        logger.info("[MapService] 所有持久化文件加载失败，使用空内存（下次保存会自动重建）")
        self.maps = {}

    @staticmethod
    def _build_summary(map_data: dict) -> dict:
        """从完整地图数据提取轻量摘要（索引用）"""
        return {
            "map_id": map_data.get("map_id", ""),
            "name": map_data.get("name", ""),
            "map_type": map_data.get("map_type", ""),
            "region": map_data.get("region", ""),
            "center": map_data.get("center"),
            "zoom": map_data.get("zoom"),
            "theme": map_data.get("theme"),
            "created_at": map_data.get("created_at"),
            "layer_count": len(map_data.get("layers", []) or []),
        }

    def _migrate_to_lazy(self, full_maps: dict):
        """将旧版全量 maps.json 迁移为“索引 + 每图独立文件”"""
        ensure_dir(self.maps_dir)
        migrated = 0
        for map_id, map_data in full_maps.items():
            if not isinstance(map_data, dict) or not map_data.get("map_id"):
                continue
            with open(os.path.join(self.maps_dir, f"{map_id}.json"), "w", encoding="utf-8") as f:
                json.dump(map_data, f, ensure_ascii=False)
            self.maps[map_id] = self._build_summary(map_data)
            migrated += 1
        # 迁移后立即落盘索引
        self._write_index()
        # 保留一次性备份（不覆盖已有备份）
        stamp = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(
            os.path.dirname(self.persist_path), "archive", f"backup_{stamp}_pre_lazy"
        )
        backup_path = os.path.join(backup_dir, "maps.json")
        if not os.path.exists(backup_path):
            try:
                ensure_dir(backup_dir)
                shutil.copy2(self.persist_path, backup_path)
                logger.info(f"[MapService] 迁移前备份已保存: {backup_path}")
            except OSError as e:
                logger.info(f"[MapService] 迁移前备份失败: {e}")
        logger.info(f"[MapService] 旧版全量数据已迁移为按图存储: {migrated} 张")

    def _write_index(self):
        """原子写入索引文件（maps.json）"""
        tmp_path = self.persist_path + ".tmp"
        backup_path = self.persist_path + ".bak"
        try:
            ensure_dir(os.path.dirname(self.persist_path) or ".")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.maps, f, ensure_ascii=False)
            if os.path.exists(self.persist_path):
                try:
                    os.replace(self.persist_path, backup_path)
                except OSError:
                    pass
            os.replace(tmp_path, self.persist_path)
        except Exception as e:
            logger.info(f"[MapService] 索引写入失败: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _load_map(self, map_id: str) -> Optional[dict]:
        """按需加载单张地图完整数据（LRU 缓存）"""
        if map_id in self._map_cache:
            self._map_cache.move_to_end(map_id)
            return self._map_cache[map_id]
        path = os.path.join(self.maps_dir, f"{map_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.info(f"[MapService] 地图文件加载失败 {map_id}: {e}")
            return None
        self._map_cache[map_id] = data
        while len(self._map_cache) > self._map_cache_max:
            self._map_cache.popitem(last=False)
        return data

    def _get_map(self, map_id: str) -> Optional[dict]:
        """获取完整地图数据：缓存 → 按图文件 → 历史归档"""
        data = self._load_map(map_id)
        if data is not None:
            return data
        archived = self._load_archived_map(map_id)
        if archived is not None:
            # 归档地图编辑后也能落盘（写入按图文件，不进入索引）
            self._map_cache[map_id] = archived
            return archived
        return None

    def put_map(self, map_id: str, map_data: dict):
        """写入/替换一张完整地图（索引摘要 + LRU 缓存），供测试与程序内复用。"""
        self.maps[map_id] = self._build_summary(map_data)
        self._map_cache[map_id] = map_data

    def import_geojson_layer(
        self,
        map_id: str,
        name: str,
        geojson: dict,
        layer_type: str = "auto",
    ) -> dict:
        """导入用户上传的 GeoJSON 为地图图层（计划 2.2 用户数据上传）

        Args:
            map_id: 目标地图
            name: 图层名称
            geojson: GeoJSON（FeatureCollection 或 Feature）
            layer_type: auto / point / line / polygon
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        if geojson.get("type") == "FeatureCollection":
            features = geojson.get("features", []) or []
        elif geojson.get("type") == "Feature":
            features = [geojson]
        else:
            raise MapGenerationError("仅支持 GeoJSON Feature / FeatureCollection")
        if not features:
            raise MapGenerationError("GeoJSON 中没有要素")

        coords: List[Any] = []
        props: List[dict] = []
        detected = None
        for feat in features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type", "")
            c = geom.get("coordinates") or []
            if gtype == "Point" and len(c) >= 2:
                coords.append([float(c[1]), float(c[0])])
                detected = detected or "circleMarker"
            elif gtype in ("LineString", "MultiLineString"):
                line = c if gtype == "LineString" else (c[0] if c else [])
                pts = [[float(p[1]), float(p[0])] for p in line if isinstance(p, list) and len(p) >= 2]
                if len(pts) >= 2:
                    coords.append(pts)
                    detected = detected or "polyline"
            elif gtype in ("Polygon", "MultiPolygon"):
                ring = c[0] if c else []
                pts = [[float(p[1]), float(p[0])] for p in ring if isinstance(p, list) and len(p) >= 2]
                if len(pts) >= 3:
                    coords.append(pts)
                    detected = detected or "polygon"
            props.append(feat.get("properties") or {})

        if not coords:
            raise MapGenerationError("未能从 GeoJSON 中提取有效坐标")
        if layer_type == "point":
            detected = "circleMarker"
        elif layer_type == "line":
            detected = "polyline"
        elif layer_type == "polygon":
            detected = "polygon"
        detected = detected or "polyline"

        layer = {
            "id": generate_id("layer"),
            "type": detected,
            "name": name,
            "coordinates": coords,
            "properties": props,
            "style": self._get_default_style(detected),
            "metadata": {"source": "user_upload", "format": "geojson"},
        }
        map_data["layers"].append(layer)
        self._schedule_save()
        logger.info(f"[MapService] GeoJSON 图层已导入: {name} ({len(coords)} 个要素)")
        return map_data

    def apply_style_package(self, map_id: str, package_key: str) -> dict:
        """应用地图风格包（计划 3.5）：按图层语义统一调整配色"""
        from app.core.constants import STYLE_PACKAGES
        pkg = STYLE_PACKAGES.get(package_key)
        if not pkg:
            raise MapGenerationError(f"未知风格包: {package_key}")
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data.get("layers", []) or []:
            name = layer.get("name", "") or ""
            st = layer.get("style") or {}
            ltype = layer.get("type", "") or ""
            if "道路-" in name or name in (
                "高速公路", "国道/主干道", "省道/主要道路", "次干道",
                "支路", "社区道路", "其他道路", "高速铁路", "普通铁路", "地铁",
            ):
                high = any(k in name for k in ("高速", "国道", "干线", "主干道", "省道", "主要道路", "铁路", "地铁"))
                st["color"] = pkg["road_primary"] if high else pkg["road_minor"]
            elif any(k in name for k in ("水系", "河流", "溪流", "运河")):
                st["color"] = pkg["water"]
            elif any(k in name for k in ("湖泊", "水库")):
                st["fillColor"] = pkg["water_fill"]
                st["color"] = pkg["water"]
            elif any(k in name for k in ("绿地", "公园", "森林", "草地", "草甸")):
                st["fillColor"] = pkg["green"]
                st["color"] = pkg["green"]
            elif name == "陆地底图":
                st["fillColor"] = pkg["land_fill"]
                st["color"] = pkg["land_fill"]
            elif ltype in ("textLabel", "label") or name in ("地标名称", "水系注记"):
                st["color"] = pkg["label"]
            elif ltype in ("circleMarker", "marker", "point") and st.get("icon"):
                st["color"] = pkg["poi"]
            layer["style"] = st
        self._schedule_save()
        logger.info(f"[MapService] 风格包已应用: {package_key} ({pkg.get('name')})")
        return map_data

    def _schedule_save(self):
        """防抖调度持久化：延迟 _SAVE_DEBOUNCE_SECONDS 后写入，期间的新调用会重置计时器"""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
            self._save_timer = threading.Timer(
                self._SAVE_DEBOUNCE_SECONDS, self._save
            )
            self._save_timer.daemon = True
            self._save_timer.start()

    def flush(self):
        """立即将待写入的数据持久化到磁盘（用于服务关闭前的安全落盘）"""
        with self._save_lock:
            if self._save_timer is not None:
                self._save_timer.cancel()
                self._save_timer = None
        self._save()

    def _save(self):
        """落盘：索引原子写入 + 缓存中的完整地图按图写入独立文件"""
        # 先归档超限的最旧地图，避免主文件再次膨胀
        self._archive_old_maps()
        try:
            ensure_dir(self.maps_dir)
            for map_id, map_data in list(self._map_cache.items()):
                with open(os.path.join(self.maps_dir, f"{map_id}.json"), "w", encoding="utf-8") as f:
                    json.dump(map_data, f, ensure_ascii=False)
            self._write_index()
        except Exception as e:
            logger.info(f"[MapService] 地图数据持久化失败: {e}")

    def _archive_old_maps(self):
        """主文件超过 MAPS_MAIN_LIMIT 时，将最旧的地图移入归档目录"""
        if len(self.maps) <= self.MAPS_MAIN_LIMIT:
            return
        items = sorted(
            self.maps.items(),
            key=lambda kv: kv[1].get("created_at", 0) if isinstance(kv[1], dict) else 0,
        )
        overflow = items[: len(self.maps) - self.MAPS_MAIN_LIMIT]
        for map_id, _summary in overflow:
            map_data = self._get_map(map_id)
            if map_data and self._write_archived_map(map_id, map_data):
                del self.maps[map_id]
                self._map_cache.pop(map_id, None)
                # 移除按图文件（已写入归档）
                try:
                    os.remove(os.path.join(self.maps_dir, f"{map_id}.json"))
                except OSError:
                    pass
                logger.info(f"[MapService] 旧地图已归档: {map_id}")

    def _write_archived_map(self, map_id: str, map_data: dict) -> bool:
        """将单张地图写入归档目录，并更新归档清单"""
        try:
            ensure_dir(self.archive_dir)
            archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
            with open(archive_path, "w", encoding="utf-8") as f:
                json.dump(map_data, f, ensure_ascii=False)
            manifest_path = os.path.join(self.archive_dir, "_manifest.json")
            manifest = []
            if os.path.exists(manifest_path):
                try:
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    if not isinstance(manifest, list):
                        manifest = []
                except (json.JSONDecodeError, OSError):
                    manifest = []
            entry = {
                "map_id": map_id,
                "name": map_data.get("name", ""),
                "map_type": map_data.get("map_type", ""),
                "region": map_data.get("region", ""),
                "created_at": map_data.get("created_at"),
                "file": f"{map_id}.json",
            }
            manifest = [m for m in manifest if m.get("map_id") != map_id] + [entry]
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=1)
            return True
        except OSError as e:
            logger.info(f"[MapService] 地图归档失败 {map_id}: {e}")
            return False

    # ==================== 地图基础操作 ====================

    def generate_map(
        self,
        map_type: str,
        region: str,
        center: Optional[List[float]] = None,
        zoom: int = 12,
        layers: Optional[List[str]] = None,
    ) -> dict:
        """生成地图

        调用OSM服务获取真实地理数据，构建JSON格式地图数据。

        Args:
            map_type: 地图类型（traffic/tourism/campus/basic/food/administrative）
            region: 区域名称（如"武汉市"）
            center: 中心坐标 [lat, lng]，为None时从CITY_BBOX获取
            zoom: 缩放级别，默认12
            layers: 自定义图层类型列表，为None时根据map_type自动确定

        Returns:
            完整的地图数据字典，包含map_id, name, center, zoom, theme, layers, created_at

        Raises:
            MapGenerationError: 地图生成失败
        """
        try:
            # 确定中心坐标
            if center is None:
                bbox = CITY_BBOX.get(region, {})
                if bbox:
                    center = [bbox["center_lat"], bbox["center_lon"]]
                else:
                    center = [30.5928, 114.3055]  # 默认武汉

            # 行政区划标准图：默认图幅范围包含周边相邻地市（规范九-5）；
            # 调用方显式传更大 zoom 时允许放大到区县详图比例尺（大比例尺行政图）
            if map_type == "administrative" and zoom is None:
                zoom = 10

            # 确定要素类型
            if layers is None:
                element_types = MAP_TYPE_OSM_TAGS.get(map_type, ["highway"])
            else:
                element_types = layers

            # 非专题地图统一补充水系要素（陆地/水系底图需要）；
            # 行政区划图（GIS叠加底图风格）同样叠加水系与路网要素
            if map_type not in THEMATIC_MAP_CONFIG:
                for _extra in ("waterway", "natural", "highway"):
                    if _extra not in element_types:
                        element_types.append(_extra)

            # 制图综合：按缩放级别选取要素等级（大比例尺显示更多细节）
            if "highway" in element_types:
                element_types = [t for t in element_types if t != "highway"]
                element_types.append("highway_major")
                if zoom >= 13:
                    element_types.append("highway_minor")
            if "waterway" in element_types:
                element_types = [t for t in element_types if t != "waterway"]
                element_types.append("waterway_major")
                if zoom >= 12:
                    element_types.append("waterway_minor")
            if "place" in element_types:
                element_types = [t for t in element_types if t != "place"]
                element_types.append("place_city")
                if zoom >= 13:
                    element_types.append("place_suburb")

            # 行政区划图：边界线使用 DataV 标准境界线（本地 wuhan_districts/hubei_* 数据），
            # 无需抓取 OSM boundary（Overpass 行政边界查询重且易超时，且后续会被 DataV 境界线替换）
            if map_type == "administrative":
                _dist_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    "data", "geo", "wuhan_districts.geojson",
                )
                if os.path.exists(_dist_path):
                    element_types = [t for t in element_types if not t.startswith("boundary")]

            # 专题地图特殊处理
            if map_type in THEMATIC_MAP_CONFIG:
                map_layers = self._generate_thematic_layers(map_type, region, center)
                logger.info(f"[MapService] 专题地图生成完成: {map_type}, {len(map_layers)} 个图层")
            else:
                map_layers = []

            # 本地精确数据优先（backend/data/geo/*.geojson）：
            # 存在本地水系/路网时跳过 OSM 对应抓取，避免兜底近似数据
            _local_water = []
            _local_roads = []
            _local_tourism = []
            _local_transit = []
            _local_builtup = []
            try:
                from app.services.local_geo_service import LocalGeoService
                # 缓存 LocalGeoService 单例，避免每次 generate_map 都重新实例化
                if self._local_geo_service is None:
                    self._local_geo_service = LocalGeoService()
                _lgs = self._local_geo_service
                # 本地精确数据仅武汉市具备；其他城市一律走 OSM + 高德，避免数据错配
                if region == "武汉市":
                    _local_water = _lgs.get_water_layers(region)
                    _local_roads = _lgs.get_roads_layers(region)
                    try:
                        # 居民地街区（制图综合：合并/化简/分级），仅大比例尺显示
                        _local_builtup = _lgs.get_builtup_layers(region)
                    except Exception as _be:
                        logger.info(f"[MapService] 居民地街区图层加载失败: {_be}")
                    if map_type == "tourism":
                        _local_tourism = _lgs.get_tourism_layers(region)
                    elif map_type == "traffic":
                        _local_transit = _lgs.get_transit_layers(region)
                if _local_water:
                    element_types = [t for t in element_types
                                     if not t.startswith("waterway") and t != "natural"]
                if _local_roads:
                    element_types = [t for t in element_types if not t.startswith("highway")]
                # 本地轨道交通/旅游POI存在时，跳过OSM对应抓取，避免重复叠加破坏协调性
                if _local_transit:
                    element_types = [t for t in element_types if t != "railway"]
                if _local_tourism:
                    element_types = [t for t in element_types
                                     if t not in ("tourism", "historic", "leisure")]
            except Exception as e:
                logger.info(f"[MapService] 本地地理数据加载失败: {e}")

            # 获取OSM数据（非专题地图才获取）
            osm_data = {}
            if not map_layers and self.osm_service:
                logger.info(f"[MapService] 正在获取{region}的OSM数据，类型: {element_types}")
                osm_data = self.osm_service.fetch_by_region(region, element_types)
                # 高德POI数据补充（配置AMAP_API_KEY后自动启用，无key时自动跳过）
                try:
                    from app.services.amap_service import AmapService
                    amap = AmapService()
                    if amap.enabled and "amenity" in element_types:
                        pois = amap.fetch_region_pois(region, map_type)
                        if pois:
                            osm_data.setdefault("amenity", []).extend(pois)
                except Exception as e:
                    logger.info(f"[MapService] 高德数据补充失败: {e}")

            # 将OSM元素转换为图层（仅当没有专题图层时）
            if not map_layers:
                map_layers = self._elements_to_layers(osm_data, element_types, map_type)
            # 叠加本地精确数据图层（水系在底层、路网在上；GIS叠加顺序由前端layerZ控制）
            if _local_water:
                map_layers = _local_water + map_layers
            if _local_roads:
                # 地势图道路为辅助要素：仅保留 motorway/trunk（MAP_TYPE_PROFILES.terrain）
                if map_type == "terrain":
                    _local_roads = [
                        l for l in _local_roads
                        if ((l.get("properties") or [{}])[0].get("subtype") in ("motorway", "trunk")
                            or any(k in (l.get("name") or "") for k in ("高速公路", "城市干线")))
                    ]
                map_layers = map_layers + _local_roads
            if _local_transit:
                map_layers = map_layers + _local_transit
            if _local_tourism:
                map_layers = map_layers + _local_tourism
            if _local_builtup:
                map_layers = map_layers + _local_builtup

            # 地势图（DEM 山体阴影底图）：水系/道路作为辅助要素淡化，突出等高线与山体阴影
            if map_type == "terrain":
                for _l in map_layers:
                    _ln = _l.get("name") or ""
                    _st = dict(_l.get("style") or {})
                    if _l.get("type") == "polyline" and re.search(
                        r"河流|水系|溪流|运河|道路|高速|公路|主干道|次干道|支路|铁路|轨道|轻轨|地铁|等高线",
                        _ln,
                    ):
                        # 等高线保持原有醒目度，仅淡化河流与道路
                        if "等高线" not in _ln:
                            _st["opacity"] = min(float(_st.get("opacity", 1.0) or 1.0), 0.55)
                            _l["style"] = _st
                    elif _l.get("type") == "polygon" and re.search(r"湖泊|河流水面|水库", _ln):
                        _st["opacity"] = min(float(_st.get("opacity", 1.0) or 1.0), 0.55)
                        _st["fillOpacity"] = min(float(_st.get("fillOpacity", 0.35) or 0.35), 0.3)
                        _l["style"] = _st

            # 交通图（GIS 叠加风格）：以线/面要素为主（道路/轨道/河流/湖泊/边界），
            # 去除点状符号（POI/公交站/轨道站点/湖泊点符号等），避免图面堆叠
            if map_type == "traffic":
                map_layers = [
                    l for l in map_layers
                    if l.get("type") not in ("circleMarker", "marker", "point", "circle")
                ]
                # 交通图：行政边界加粗突出（省界/市界/县界为骨架要素）
                for _l in map_layers:
                    _ln = _l.get("name") or ""
                    _st = dict(_l.get("style") or {})
                    if "边界" in _ln or "境界" in _ln or "省界" in _ln or "市界" in _ln or "县界" in _ln:
                        _st["weight"] = max(float(_st.get("weight", 1.5) or 1.5), 2.5)
                        _st["opacity"] = max(float(_st.get("opacity", 0.9) or 0.9), 0.95)
                        _l["style"] = _st
                    # 交通图道路保留到次干道（motorway/trunk/primary/secondary）
                    # 剔除支路/社区道路/步行道等低等级道路
                _TRAFFIC_ROAD_DROP = ("支路", "三级", "社区道路", "服务道路", "居民区街区",
                                      "生活性街道", "未分级", "步行", "自行车", "阶梯", "匝道", "连接线")
                map_layers = [
                    l for l in map_layers
                    if not (
                        l.get("type") == "polyline"
                        and ("道路" in (l.get("name") or "") or re.search(r"高速|公路|国道|省道|干线|主干道|次干道", l.get("name") or ""))
                        and any(k in (l.get("name") or "") for k in _TRAFFIC_ROAD_DROP)
                    )
                ]

            # 标准行政区划图：叠加官方区划面底图（DataV GeoAtlas，含区县政区面/注记/行政中心）
            if map_type == "administrative":
                try:
                    from app.services.geo_service import GeoService
                    gs = GeoService()
                    geo_layers = gs.build_district_layers(region)
                    if geo_layers:
                        # 移除OSM place生成的区县注记（与DataV注记重复），保留街道地名标注
                        map_layers = [
                            l for l in map_layers
                            if not (l.get("type") == "textLabel" and l.get("name") == "区县名称标注")
                        ]
                        # 移除OSM生成的边界线（改用DataV标准境界线；紫色地级市界已按用户要求删除）
                        map_layers = [
                            l for l in map_layers
                            if not (l.get("type") == "polyline"
                                    and (l.get("style", {}).get("osm_boundary") or "边界" in (l.get("name") or "")))
                        ]
                        # 移除与专题无关的绿地面（公园/森林/草地），保留湖泊水域面
                        map_layers = [
                            l for l in map_layers
                            if l.get("name") not in ("公园", "森林", "草地", "草甸", "其他绿地", "绿化用地")
                        ]
                        # 区名白名单校验：只保留武汉市13个标准区名注记，
                        # 过滤数据源错误名称（如"汝南区"等非规范区名）
                        _std_names = {d["name"] for d in WUHAN_DISTRICTS}
                        map_layers = [
                            ({
                                **l,
                                "coordinates": [c for c, p in zip(l.get("coordinates") or [], l.get("properties") or [])
                                                if p.get("name") in _std_names],
                                "properties": [p for p in (l.get("properties") or []) if p.get("name") in _std_names],
                            } if (l.get("type") == "textLabel" and l.get("name") == "区县名称标注") else l)
                            for l in map_layers
                        ]
                        # 周边地市底图(极浅米黄) + 标准境界线（省界/地级市界）
                        # 周边地市上下文仅武汉市具备本地数据（其他城市不叠加错误的省域底图）
                        surrounding = gs.build_surrounding_layers(region) if region == "武汉市" else []
                        map_layers = surrounding + geo_layers + map_layers
                        # 市级行政中心（红色五角星★，正红#D82828，规范三-1）
                        # 坐标按用户要求标注于武昌区（官方驻地实际在江岸区沿江大道188号）
                        cc = ADMIN_CENTER_STYLES["city"]
                        _gov = WUHAN_GOV_COORD if region == "武汉市" else None
                        if _gov:
                            map_layers.append({
                                "id": generate_id("layer"),
                                "type": "circleMarker",
                                "name": cc["name"],
                                "coordinates": [[_gov[0], _gov[1]]],
                                "properties": [{"name": region}],
                                "style": {"color": cc["color"], "fillColor": cc["fillColor"],
                                          "fillOpacity": cc["fillOpacity"], "weight": cc["weight"],
                                          "radius": cc["radius"], "icon": cc["icon"],
                                          "iconClass": cc.get("iconClass"), "kind": cc.get("kind")},
                            })
                    # 水系：本地精确数据优先；本地缺失时走 OSM → 兜底近似
                    if not _local_water and region == "武汉市":
                        has_water = any(
                            any(k in (l.get("name") or "") for k in ("河", "湖", "水库", "水系"))
                            for l in map_layers
                        )
                        map_layers += self._fallback_water_layers(region, surrounding_only=has_water)
                    # 重点POI标注（机场/景区/交通枢纽等，GIS叠加风格绿点）
                    gis_pois = WUHAN_GIS_POI if region == "武汉市" else []
                    # 完美复刻 carto-agent-1 行政区划图：行政图不叠加新增的樱花主题地标
                    if map_type == "administrative":
                        _CHERRY_POIS = {"武汉大学樱花大道", "东湖磨山樱花园", "晴川阁樱花园"}
                        gis_pois = [p for p in gis_pois if p.get("name") not in _CHERRY_POIS]
                    if gis_pois:
                        map_layers.append({
                            "id": generate_id("layer"),
                            "type": "circleMarker",
                            "name": "重点地标",
                            "coordinates": [[p["lat"], p["lng"]] for p in gis_pois],
                            "properties": [{"name": p["name"], "category": p["type"]} for p in gis_pois],
                            "style": {"color": "#16a34a", "fillColor": "#ffffff", "fillOpacity": 0.9,
                                      "weight": 2.5, "radius": 7, "icon": "🏞️", "iconClass": "fa-location-dot",
                                      "group": "兴趣点(POI)"},
                        })
                except Exception as e:
                    logger.info(f"[MapService] 区划面底图获取失败: {e}")

            # 旅游图：叠加核心景区/地标（真实 GIS POI，绿点高亮）——
            # 东湖绿道、木兰文化生态旅游区等核心景点须上图（旅游图 GroundTruth recall）
            if map_type == "tourism" and region == "武汉市":
                gis_pois = WUHAN_GIS_POI
                if gis_pois and not any(l.get("name") == "重点地标" for l in map_layers):
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "circleMarker",
                        "name": "重点地标",
                        "coordinates": [[p["lat"], p["lng"]] for p in gis_pois],
                        "properties": [{"name": p["name"], "category": p["type"]} for p in gis_pois],
                        "style": {"color": "#16a34a", "fillColor": "#ffffff", "fillOpacity": 0.9,
                                  "weight": 2.5, "radius": 7, "icon": "🏞️", "iconClass": "fa-location-dot",
                                  "group": "兴趣点(POI)"},
                    })

            # 非行政区划图：叠加"上一级行政边界"上下文（湖北省市级边界 + 武汉市域）
            # 生成的地图仅含用户所需区域 + 行政规划上一级，两个模块颜色区分
            if map_type != "administrative" and region == "武汉市":
                try:
                    from app.services.geo_service import GeoService
                    _gs = GeoService()
                    _ctx = _gs.build_surrounding_layers(region)
                    if _ctx:
                        map_layers = _ctx + map_layers
                except Exception as e:
                    logger.info(f"[MapService] 上一级行政边界叠加失败: {e}")

            # 如果图层为空（OSM数据为空或API不可用），使用本地地标数据作为回退
            if not map_layers:
                logger.info(f"[MapService] OSM数据为空，使用本地地标数据作为回退: {region}")
                map_layers = self._generate_fallback_layers(map_type, region, center, zoom)

            # 陆地/水系底图：所有地图插入"陆地底图"米色面（水系蓝色面由OSM数据生成）；
            # 行政区划图除外（政区面即陆地底图）
            if map_type not in THEMATIC_MAP_CONFIG and map_type != "administrative":
                _bbox = CITY_BBOX.get(region, {})
                if _bbox:
                    _land = [[_bbox["min_lat"], _bbox["min_lon"]], [_bbox["min_lat"], _bbox["max_lon"]],
                             [_bbox["max_lat"], _bbox["max_lon"]], [_bbox["max_lat"], _bbox["min_lon"]],
                             [_bbox["min_lat"], _bbox["min_lon"]]]
                    map_layers = [{
                        "id": generate_id("layer"),
                        "type": "polygon",
                        "name": "陆地底图",
                        "coordinates": [_land],
                        "style": {"fillColor": "#f3ead9", "fillOpacity": 0.6,
                                  "color": "#e5d9c0", "weight": 0.5},
                    }] + map_layers

            # 县级行政区划专题规范：隐藏乡镇边界图层；"武汉市"总注记由图廓标题承担，移除图内重复
            if map_type == "administrative":
                map_layers = [
                    l for l in map_layers
                    # 乡镇边界、城市名称标注、湖泊点符号（概览）均不显示：面状湖泊已承载水系信息，
                    # 点状湖泊符号会干扰区划范围观感
                    if l.get("name") not in ("乡镇边界", "城市名称标注", "湖泊点符号（概览）")
                ]

                # 边界为主、水系/道路为辅：行政区划图仅保留主要道路并淡化（突出省/市/县界）
                # 保留三级主要道路：高速公路(motorway)、国道/干线(trunk)、城市主干道(primary)
                # 剔除次干道及以下，避免道路干扰行政区划范围观感
                _ADMIN_ROAD_KEEP = ("高速公路", "国道", "干线", "城市主干道", "省道")
                _ADMIN_ROAD_DROP = ("匝道", "连接线", "衔接", "次干道", "支路", "三级",
                                    "社区道路", "服务道路", "居民区街区", "其他道路",
                                    "生活性街道", "未分级", "步行", "自行车", "阶梯")
                map_layers = [
                    l for l in map_layers
                    if not (
                        l.get("type") == "polyline"
                        and ("道路" in (l.get("name") or "") or re.search(r"高速|公路|国道|省道|干线|主干道", l.get("name") or ""))
                        and (any(k in (l.get("name") or "") for k in _ADMIN_ROAD_DROP)
                             or not any(k in (l.get("name") or "") for k in _ADMIN_ROAD_KEEP))
                    )
                ]
                for _l in map_layers:
                    _ln = _l.get("name") or ""
                    _st = dict(_l.get("style") or {})
                    if _l.get("type") == "polyline" and re.search(
                            r"道路|高速|公路|主干道|次干道|支路|铁路|轨道|轻轨|地铁", _ln):
                        # 道路线进一步弱化（更细、更透明），不干扰区划范围观感
                        _st["opacity"] = min(float(_st.get("opacity", 1.0) or 1.0), 0.22)
                        _st["weight"] = max(0.4, float(_st.get("weight", 1.0) or 1.0) * 0.4)
                        _l["style"] = _st
                    elif _l.get("type") == "polyline" and re.search(
                            r"河流|水系|溪流|运河|水库", _ln):
                        # 河流湖泊等水系线淡化（细线、半透明）
                        _st["opacity"] = min(float(_st.get("opacity", 1.0) or 1.0), 0.26)
                        _st["weight"] = max(0.4, float(_st.get("weight", 1.0) or 1.0) * 0.45)
                        _l["style"] = _st
                    elif _l.get("type") == "polygon" and re.search(r"河流水面|湖泊|水库", _ln):
                        # 湖泊/水库水面更淡（降低饱和度，突出边界）
                        _st["opacity"] = min(float(_st.get("opacity", 1.0) or 1.0), 0.45)
                        _st["fillOpacity"] = min(float(_st.get("fillOpacity", 0.35) or 0.35), 0.2)
                        _l["style"] = _st

                # 强化边界线（行政图主体）：市域界 > 区县界 > 省界 视觉层级
                for _l in map_layers:
                    _ln = _l.get("name") or ""
                    if _l.get("type") != "polyline":
                        continue
                    _st = dict(_l.get("style") or {})
                    if "武汉市域边界" in _ln or "地级市界" in _ln:
                        _st["color"] = "#E03131"
                        _st["weight"] = max(float(_st.get("weight", 1.0) or 1.0), 4.5)
                        _st["opacity"] = 1.0
                        _st.pop("dashArray", None)
                    elif "区县界" in _ln:
                        _st["color"] = "#6B6B6B"
                        _st["weight"] = max(float(_st.get("weight", 1.0) or 1.0), 1.8)
                        _st["opacity"] = 0.95
                    elif "省界" in _ln:
                        _st["color"] = "#000000"
                        _st["weight"] = max(float(_st.get("weight", 1.0) or 1.0), 1.5)
                        _st["opacity"] = 1.0
                        _st.setdefault("dashArray", "1,4")
                    _l["style"] = _st

                # 市级名称标注（依据比例尺标注对应等级行政单位）：大字号、置于市域中心附近
                if region == "武汉市":
                    _city_label_pt = [30.5928, 114.3055]
                    _gov = WUHAN_GOV_COORD
                    # 从区县政区面的主面内寻找合适注记点：优先市区几何中心附近
                    _dist_poly = next((l for l in map_layers if l.get("name") == "区县政区"), None)
                    if _dist_poly and _dist_poly.get("features"):
                        _main = max(
                            _dist_poly["features"],
                            key=lambda f: len(f.get("coordinates") or []),
                        )
                        _coords = _main.get("coordinates") or []
                        if len(_coords) >= 3:
                            _pts = [p for p in _coords if isinstance(p, list) and len(p) >= 2]
                            if _pts:
                                _city_label_pt = [
                                    sum(p[0] for p in _pts) / len(_pts),
                                    sum(p[1] for p in _pts) / len(_pts),
                                ]
                    elif _gov:
                        _city_label_pt = _gov
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "textLabel",
                        "name": "市级名称标注",
                        "coordinates": [_city_label_pt],
                        "properties": [{"name": "武汉市", "admin_level": 4}],
                        "style": {"color": "#1f2937", "fontSize": 22, "weight": 4,
                                  "font": "song", "center": True},
                    })

            # 行政区划图兜底：place数据缺失(Overpass限流)时补充武汉区县标注
            if map_type == "administrative" and region == "武汉市":
                has_label = any(l.get("type") == "textLabel" for l in map_layers)
                if not has_label:
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "textLabel",
                        "name": "区县名称标注",
                        "coordinates": [[d["lat"], d["lng"]] for d in WUHAN_DISTRICTS],
                        "properties": [{"name": d["name"]} for d in WUHAN_DISTRICTS],
                        "style": {"color": "#000000", "fontSize": 15, "weight": 3, "font": "song"},
                    })

            # 重要地标名称常驻注记（全国主要城市通用，直接附着在地图上）
            _landmarks = CITY_LANDMARKS.get(region, [])
            if _landmarks and map_type in ("tourism", "basic", "traffic"):
                if not any(l.get("name") == "地标名称" for l in map_layers):
                    map_layers.append({
                        "id": generate_id("layer"),
                        "type": "textLabel",
                        "name": "地标名称",
                        "coordinates": [[lm["lat"], lm["lng"]] for lm in _landmarks],
                        "properties": [{"name": lm["name"]} for lm in _landmarks],
                        "style": {"color": LABEL_STYLES["landmark"]["color"],
                                  "fontSize": LABEL_STYLES["landmark"]["fontSize"],
                                  "weight": LABEL_STYLES["landmark"]["weight"],
                                  "font": LABEL_STYLES["landmark"]["font"]},
                    })

            # 按制图规范调整图层叠置顺序（面状底图→建筑→水系→铁路→道路→点状符号）
            map_layers = self._sort_layers(map_layers)
            # 线状要素按名称连通：同一条道路/边界/铁路的离散线段合并为完整折线（制图综合连通性）
            map_layers = self._connect_polylines_by_name(map_layers)
            # 应用 Cartographic Profile（主题-数据-尺度约束矩阵）：按图类型过滤/提取/分级
            map_layers = self._apply_cartographic_profile(map_type, map_layers, zoom)
            # 制图综合（GeneralizationEngine）：真实 Selection/Simplification/Aggregation/Displacement/Collapse
            generalization_metrics = self._apply_generalization(map_type, map_layers, zoom)
            # SymbolRegistry：统一符号来源（颜色/线宽/优先级从注册表解析，禁止随机配色）
            map_layers = self._apply_symbol_registry(map_layers)
            # LabelEngine：点注记碰撞消解 + 道路/河流线注记（真实 Label Engine 接入）
            label_metrics = self._apply_label_engine(map_type, map_layers, zoom)

            # 生成图例数据
            legend = self._generate_legend(map_type, map_layers)

            # 构建地图数据
            map_id = generate_id("map")
            # 获取地图类型中文名
            type_names = {
                "traffic": "交通图", "tourism": "旅游图", "campus": "校园图",
                "basic": "基础地图", "food": "美食图", "administrative": "行政区划图",
                "terrain": "地势图",
            }
            map_name = f"{region}{type_names.get(map_type, '地图')}"

            # 数据质量校验：行政区划图不再自动输出面积统计（坐标投影换算易失真，
            # 需求8：关闭错误的自动面积统计），只保留其他通用告警
            quality = {"warnings": []}

            # 底图主题：地势图使用 DEM 山体阴影作为地势底图；行政区划图保持矢量制图底图
            default_theme = "hillshade" if map_type == "terrain" else "plain"
            scale_den = self._zoom_to_scale(zoom)
            # 编制说明中的地图类型描述（按地图类型动态生成）
            meta_type = {
                "administrative": "行政区划图（政区版）· 普通参考地图",
                "traffic": "交通图（GIS叠加版）",
                "terrain": "地势图（DEM山体阴影 + 等高线）",
                "tourism": "旅游图",
                "campus": "校园图",
                "basic": "基础地图",
                "food": "美食图",
            }.get(map_type, "专题地图")

            map_data = {
                "map_id": map_id,
                "name": map_name,
                "map_type": map_type,
                "region": region,
                "center": center,
                "zoom": zoom,
                "theme": default_theme,
                "layers": map_layers,
                "legend": legend,
                "quality": quality,
                "generalization_metrics": generalization_metrics,
                # 编制说明（规范3.7：坐标系/投影/数据来源/资料截止）
                "metadata": {
                    "坐标系": "WGS84 (EPSG:4326) 经纬度（源数据）",
                    "投影": "前端渲染 Web墨卡托 (EPSG:3857)；导出/米制计算可重投影 CGCS2000 高斯-克吕格 3°分带 (EPSG:4547)",
                    "数据来源": "DataV GeoAtlas 官方行政区划数据 / OpenStreetMap",
                    "地图类型": meta_type,
                    "图幅范围": "武汉市及周边相邻地市（区位关系）",
                    "比例尺": f"1:{scale_den}",
                    "经纬网": "按图幅范围自动绘制经纬网",
                    "指北针": "图廓内右上角",
                    "图廓": "竖版双线图廓",
                    "幅面版式": "竖版",
                    "审图号": "鄂S(2022)100号",
                    "编制单位": "地图制图智能体 CartoAgent",
                    "出版日期": "2026年8月",
                    "制图时间": "2026年8月",
                    "资料截止": "民政部行政区划现状 / OSM实时",
                    "说明": "依据《行政区划地图制作规范》编制；正式出版需取得审图号并配置标准投影",
                },
                # LayoutEngine：自动版式（标题/图例/比例尺/指北针/来源/坐标/时间 + 冲突避免）
                "layout": self._build_layout(map_name, map_type, legend),
                "label_metrics": label_metrics,
                "created_at": get_timestamp(),
            }

            # 存储：索引写入摘要，完整数据写入 LRU 缓存（随 _save 落盘独立文件）
            self.maps[map_id] = self._build_summary(map_data)
            self._map_cache[map_id] = map_data
            self._schedule_save()
            logger.info(f"[MapService] 地图生成成功: {map_name} (ID: {map_id})，"
                  f"共{len(map_layers)}个图层")

            return map_data

        except Exception as e:
            logger.info(f"[MapService] 地图生成失败: {e}")
            raise MapGenerationError(f"地图生成失败: {e}")

    def get_map(self, map_id: str) -> Optional[dict]:
        """获取地图数据

        Args:
            map_id: 地图ID

        Returns:
            地图数据字典，不存在时返回None
        """
        map_data = self._get_map(map_id)
        if map_data is not None:
            self._classify_layers(map_data)
            return map_data
        return None

    def _load_archived_map(self, map_id: str) -> Optional[dict]:
        """从归档目录加载历史地图（data/archive/maps/{map_id}.json）"""
        if not map_id:
            return None
        archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
        if not os.path.exists(archive_path):
            return None
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.info(f"[MapService] 归档地图加载失败 {map_id}: {e}")
            return None

    def _classify_layers(self, map_data: dict) -> None:
        """图层分类综合（QGIS/ArcGIS 图层管理）：

        给每个图层补齐持久化的分类元数据：
          - group   按制图要素类别分组的名称（底图/行政区划/水系/湖泊/…）
          - format  颜色/线宽/填充/虚线等视觉格式摘要
          - visible 图层可见性（默认True，可隐藏并持久化）

        分类依据"颜色与格式 + 名称语义"，与前端图层面板联动。
        """
        if not map_data or "layers" not in map_data:
            return
        changed = False
        # 老图迁移：道路图层英文名 -> 中文名 + 子分组
        ROAD_CN = {
            "motorway": "高速公路主线", "motorway_link": "高速互通匝道",
            "trunk": "城市干线主干道", "trunk_link": "主干道连接匝道",
            "primary": "城市主干道", "primary_link": "主干道衔接匝道",
            "secondary": "城市次干道", "secondary_link": "次干道连接匝道",
            "tertiary": "三级道路（次要道路）", "tertiary_link": "三级道路连接线",
            "residential": "居民区街区道路", "living_street": "生活性街道",
            "service": "服务性道路", "unclassified": "未分级道路", "other": "其他道路",
        }
        ROAD_SUB = {
            "motorway": "高速路网", "motorway_link": "高速路网",
            "trunk": "城市主干道", "trunk_link": "城市主干道",
            "primary": "城市主干道", "primary_link": "城市主干道",
            "secondary": "城区道路", "secondary_link": "城区道路",
            "tertiary": "城区道路", "tertiary_link": "城区道路",
            "residential": "城区道路", "living_street": "城区道路",
            "service": "其他道路", "unclassified": "其他道路", "other": "其他道路",
        }
        ROAD_OPACITY = {
            # 与 carto-agent-1 行政区划图完全一致：道路统一不透明度 0.9
            "motorway": 0.9, "motorway_link": 0.9, "trunk": 0.9, "trunk_link": 0.9,
            "primary": 0.9, "primary_link": 0.9, "secondary": 0.9,
            "secondary_link": 0.9, "tertiary": 0.9, "tertiary_link": 0.9,
            "residential": 0.9, "living_street": 0.9, "service": 0.9,
            "unclassified": 0.9, "other": 0.9,
        }

        def _cat(layer: dict) -> str:
            n = layer.get("name", "") or ""
            t = layer.get("type", "") or ""
            if re.search(r"陆地底图|省域|周边地市|市域底图|湖北省", n):
                return "底图"
            if re.search(r"政区|区县|边界|行政中心|区划", n):
                return "行政区划"
            if re.search(r"河流|水系|河道|中心线|大江|水面", n):
                return "水系"
            if "湖泊" in n:
                return "湖泊"
            if "居民地" in n:
                return "居民地"
            if "等高线" in n:
                return "等高线"
            if n.startswith("道路-") or re.search(r"高速|国道|省道|主干道|次干道|支路|街巷", n):
                return "道路"
            if re.search(r"轨道|铁路|地铁|轻轨", n):
                return "轨道/铁路"
            if t in ("circleMarker", "marker", "point", "circle"):
                return "POI/符号"
            if t in ("textLabel", "label") or "注记" in n or "标注" in n:
                return "注记/标注"
            return "其他"

        for layer in map_data["layers"]:
            # 老图道路图层命名迁移
            _m = re.match(r"^道路-([a-z_]+)$", layer.get("name", "") or "")
            if _m and _m.group(1) in ROAD_CN:
                hw = _m.group(1)
                new_name = f"道路-{ROAD_CN[hw]}"
                if layer.get("name") != new_name:
                    layer["name"] = new_name
                    changed = True
                if layer.get("subgroup") != ROAD_SUB[hw]:
                    layer["subgroup"] = ROAD_SUB[hw]
                    changed = True
                _st = layer.setdefault("style", {})
                if _st.get("opacity", 1.0) != ROAD_OPACITY.get(hw):
                    _st["opacity"] = ROAD_OPACITY.get(hw, 0.9)
                    changed = True
                layer.setdefault("metadata", {})["raw_class"] = hw
                layer.setdefault("metadata", {})["description"] = ROAD_CN[hw]
            # 道路样式迁移（按 raw_class / properties.subtype 设置分级不透明度）
            _rc = (layer.get("metadata") or {}).get("raw_class")
            if not _rc and layer.get("properties") and isinstance(layer.get("properties"), list):
                _p0 = layer["properties"][0] if layer["properties"] else None
                _rc = _p0.get("subtype") if isinstance(_p0, dict) else None
            if _rc in ROAD_OPACITY:
                _st = layer.setdefault("style", {})
                if _st.get("opacity", 1.0) != ROAD_OPACITY[_rc]:
                    _st["opacity"] = ROAD_OPACITY[_rc]
                    changed = True
            if "group" not in layer:
                layer["group"] = _cat(layer)
                changed = True
            if "format" not in layer:
                st = layer.get("style") or {}
                layer["format"] = {
                    "color": st.get("color", ""),
                    "fillColor": st.get("fillColor", ""),
                    "weight": st.get("weight"),
                    "dashArray": st.get("dashArray", ""),
                    "opacity": st.get("opacity"),
                }
                changed = True
            if "visible" not in layer:
                layer["visible"] = True
                changed = True
        if changed:
            self._schedule_save()

    def list_maps(self) -> List[dict]:
        """列出所有地图

        Returns:
            地图摘要列表（不含完整图层数据，减少传输量）
        """
        result = []
        for summary in self.maps.values():
            result.append({
                "map_id": summary.get("map_id", ""),
                "name": summary.get("name", ""),
                "map_type": summary.get("map_type", ""),
                "region": summary.get("region", ""),
                "center": summary.get("center"),
                "zoom": summary.get("zoom"),
                "theme": summary.get("theme"),
                "layer_count": summary.get("layer_count", 0),
                "created_at": summary.get("created_at"),
            })
        return result

    def delete_map(self, map_id: str) -> bool:
        """删除地图

        Args:
            map_id: 地图ID

        Returns:
            删除是否成功
        """
        if map_id in self.maps:
            del self.maps[map_id]
            self._map_cache.pop(map_id, None)
            try:
                os.remove(os.path.join(self.maps_dir, f"{map_id}.json"))
            except OSError:
                pass
            self._schedule_save()
            logger.info(f"[MapService] 地图已删除: {map_id}")
            return True
        # 归档地图也可删除（同步清理归档文件）
        archive_path = os.path.join(self.archive_dir, f"{map_id}.json")
        if os.path.exists(archive_path):
            try:
                os.remove(archive_path)
                logger.info(f"[MapService] 归档地图已删除: {map_id}")
                return True
            except OSError as e:
                logger.info(f"[MapService] 归档地图删除失败 {map_id}: {e}")
                return False
        logger.info(f"[MapService] 地图不存在: {map_id}")
        return False

    # ==================== 多源数据融合 ====================

    def fetch_data_multi_source(
        self,
        data_type: str,
        bbox: Optional[List[float]] = None,
        region: Optional[str] = None,
        limit: int = 1000,
        preferred_source: Optional[str] = None,
        merge: bool = True,
        **filters,
    ) -> DataResult:
        """多源数据融合获取

        通过 DataSourceRegistry 从多个数据源获取地理要素数据，
        支持自动选择最优源、多源查询、结果合并去重。

        Args:
            data_type: 要素类型，如 "highway", "poi/restaurant", "vec"
            bbox: 边界框 [min_lng, min_lat, max_lng, max_lat]，
                  为 None 时自动根据 region 填充
            region: 区域名称（如"武汉市"），在 bbox 为 None 时使用
            limit: 返回数量上限
            preferred_source: 优先使用的数据源
            merge: 是否合并多源结果（True=合并去重, False=返回第一个源的结果）
            **filters: 额外筛选条件

        Returns:
            DataResult: 统一返回对象

        Example:
            # 多源融合获取武汉餐饮 POI
            result = map_service.fetch_data_multi_source(
                "poi/restaurant", region="武汉市", merge=True
            )
            # 获取 OSM 道路数据
            result = map_service.fetch_data_multi_source(
                "highway", region="武汉市", preferred_source="osm"
            )
        """
        # 构建查询对象
        if bbox:
            query = DataQuery(
                data_type=data_type,
                bbox=bbox,
                limit=limit,
                filters=filters if filters else None,
                region=region,
            )
        elif region:
            query = DataQuery.from_region(
                data_type=data_type,
                region=region,
                limit=limit,
                filters=filters if filters else None,
            )
        else:
            return DataResult.empty("map_service", "no bbox or region specified")

        logger.info(f"[MapService] 多源数据获取: type={data_type},"
              f" region={region}, merge={merge}, preferred={preferred_source}")

        if merge:
            # 多源融合：获取所有源的结果并合并去重
            result = self.data_registry.fetch_and_merge(query)
        elif preferred_source:
            # 指定优先源
            result = self.data_registry.fetch(query, preferred_source=preferred_source)
        else:
            # 自动选择第一个支持的源
            result = self.data_registry.fetch(query)

        logger.info(f"[MapService] 多源数据获取完成: {result.count} 个要素,"
              f" source={result.source}, quality={result.quality_score}")
        return result

    def get_data_sources(self) -> List[str]:
        """获取当前可用的数据源列表"""
        return self.data_registry.get_available_sources()

    # ==================== 图层操作 ====================

    def add_layer(
        self,
        map_id: str,
        layer_type: str,
        name: str,
        query: Optional[str] = None,
        coordinates: Optional[Any] = None,
        properties: Optional[Any] = None,
        style: Optional[dict] = None,
        features: Optional[Any] = None,
        group: Optional[str] = None,
    ) -> dict:
        """向地图添加新图层

        如果提供了query参数（OSM标签类型），会自动查询OSM数据填充图层。
        若提供了 coordinates/features 等直接数据，则优先使用（用于
        前端空间分析结果、图层复制等自定义图层回写）。

        Args:
            map_id: 地图ID
            layer_type: 图层类型（polyline/marker/polygon）
            name: 图层名称
            query: OSM查询标签（如"highway"、"railway"），可选
            coordinates: 直接写入的坐标数组（可选）
            properties: 与坐标对应的属性数组（可选）
            style: 图层样式（可选）
            features: features 型图层数据（可选）
            group: 图层分组名（可选）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在或添加失败
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        # 调用方是否直接提供了完整数据（自定义图层/分析结果/复制图层）
        provided_direct_data = coordinates is not None or bool(features)
        if coordinates is None:
            coordinates = []
        properties = properties or []
        features = features or []

        # 未提供直接数据且带 OSM 查询标签时，拉取真实数据填充
        if not provided_direct_data and query and self.osm_service:
            region = map_data.get("region", "武汉市")
            osm_data = self.osm_service.fetch_by_region(region, [query])
            elements = osm_data.get(query, [])

            for elem in elements:
                coords = self._extract_coordinates(elem, layer_type)
                if coords:
                    coordinates.append(coords)

        # 获取默认样式
        layer_style = style or self._get_default_style(query or layer_type)

        # 创建新图层
        layer = {
            "id": generate_id("layer"),
            "type": layer_type,
            "name": name,
            "coordinates": coordinates,
            "style": layer_style,
        }
        if properties:
            layer["properties"] = properties
        if features:
            layer["features"] = features
        if group:
            layer["group"] = group

        map_data["layers"].append(layer)
        self._schedule_save()
        logger.info(f"[MapService] 图层已添加: {name} (ID: {layer['id']})，"
              f"包含{len(coordinates) or len(features)}个要素")
        return map_data

    def duplicate_layer(self, map_id: str, layer_id: str) -> dict:
        """复制图层（含几何/属性/样式），插入到原图层之后"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for index, layer in enumerate(map_data["layers"]):
            if layer["id"] == layer_id:
                copy = json.loads(json.dumps(layer))
                copy["id"] = generate_id("layer")
                copy["name"] = (copy.get("name") or "未命名图层") + " 副本"
                copy["visible"] = True
                map_data["layers"].insert(index + 1, copy)
                self._schedule_save()
                logger.info(f"[MapService] 图层已复制: {layer_id} -> {copy['id']}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def reorder_layers(self, map_id: str, layer_ids: List[str]) -> dict:
        """按给定 ID 顺序重排图层（未列出的图层保持相对顺序追加在末尾）"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        by_id = {layer["id"]: layer for layer in map_data["layers"]}
        ordered = []
        for lid in layer_ids:
            layer = by_id.pop(lid, None)
            if layer is not None:
                ordered.append(layer)
        ordered.extend(by_id.values())
        map_data["layers"] = ordered
        self._schedule_save()
        logger.info(f"[MapService] 图层顺序已更新: {len(ordered)} 个图层")
        return map_data

    def set_layer_group(self, map_id: str, layer_id: str, group: Optional[str]) -> dict:
        """设置/移除图层所属分组"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                if group:
                    layer["group"] = group
                else:
                    layer.pop("group", None)
                self._schedule_save()
                logger.info(f"[MapService] 图层分组已更新: {layer_id} -> {group or '无'}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def accept_quality(self, map_id: str) -> dict:
        """接受当前质量报告：在地图编制信息中记录质检结论"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        metadata = map_data.setdefault("metadata", {})
        now = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        metadata["质检结论"] = "已接受（人工确认）"
        metadata["质检时间"] = now
        self._schedule_save()
        logger.info(f"[MapService] 质量报告已接受: {map_id}")
        return map_data

    def remove_layer(self, map_id: str, layer_id: str) -> dict:
        """从地图移除图层

        Args:
            map_id: 地图ID
            layer_id: 图层ID

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        original_count = len(map_data["layers"])
        map_data["layers"] = [
            layer for layer in map_data["layers"] if layer["id"] != layer_id
        ]

        if len(map_data["layers"]) == original_count:
            raise MapGenerationError(f"图层不存在: {layer_id}")

        self._schedule_save()
        logger.info(f"[MapService] 图层已移除: {layer_id}")
        return map_data

    def update_layer_style(self, map_id: str, layer_id: str, style: dict) -> dict:
        """更新图层样式

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            style: 样式字典（color, weight, opacity, fillOpacity, dashArray等）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                # 合并样式，保留未更新的字段
                layer["style"].update(style)
                self._schedule_save()
                logger.info(f"[MapService] 图层样式已更新: {layer_id}，新样式: {layer['style']}")
                return map_data

        raise MapGenerationError(f"图层不存在: {layer_id}")

    def set_layer_visible(self, map_id: str, layer_id: str, visible: bool) -> dict:
        """设置图层可见性（QGIS/ArcGIS 图层管理：隐藏/显示并持久化）"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["visible"] = bool(visible)
                self._schedule_save()
                logger.info(f"[MapService] 图层可见性已更新: {layer_id} -> {visible}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def rename_layer(self, map_id: str, layer_id: str, name: str) -> dict:
        """重命名图层（QGIS/ArcGIS 图层管理）"""
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["name"] = name
                self._schedule_save()
                logger.info(f"[MapService] 图层已重命名: {layer_id} -> {name}")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def update_layer_geometry(
        self,
        map_id: str,
        layer_id: str,
        coordinates: Optional[Any] = None,
        properties: Optional[Any] = None,
        style: Optional[dict] = None,
        features: Optional[Any] = None,
    ) -> dict:
        """编辑模式：整层替换几何/属性/样式（QGIS/ArcGIS 式编辑保存）

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            coordinates: 新的坐标数组（整层替换，coordinates 型图层）
            properties: 新的属性数组（与 coordinates 一一对应）
            style: 新的样式字典
            features: 新的 features 数组（features 型图层）
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                if coordinates is not None:
                    layer["coordinates"] = coordinates
                if properties is not None:
                    layer["properties"] = properties
                if style is not None:
                    layer["style"] = style
                if features is not None:
                    layer["features"] = features
                self._schedule_save()
                logger.info(f"[MapService] 图层几何已更新: {layer_id} "
                      f"(coords={len(coordinates or []) if coordinates is not None else '-'}, "
                      f"features={len(features or []) if features is not None else '-'})")
                return map_data
        raise MapGenerationError(f"图层不存在: {layer_id}")

    def update_view(
        self,
        map_id: str,
        center: Optional[List[float]] = None,
        zoom: Optional[int] = None,
    ) -> dict:
        """更新地图视图（中心点和缩放级别）

        Args:
            map_id: 地图ID
            center: 新的中心坐标 [lat, lng]，可选
            zoom: 新的缩放级别，可选

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        if center is not None:
            map_data["center"] = center
        if zoom is not None:
            map_data["zoom"] = zoom

        self._schedule_save()
        logger.info(f"[MapService] 视图已更新: center={map_data['center']}, zoom={map_data['zoom']}")
        return map_data

    def update_theme(self, map_id: str, theme: str) -> dict:
        """更新地图底图主题

        Args:
            map_id: 地图ID
            theme: 主题名称（standard/positron/dark/satellite）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图不存在或主题不支持
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        if theme not in MAP_THEMES:
            raise MapGenerationError(
                f"不支持的主题: {theme}，支持的主题: {list(MAP_THEMES.keys())}"
            )

        map_data["theme"] = theme
        self._schedule_save()
        logger.info(f"[MapService] 主题已更新: {theme} ({MAP_THEMES[theme]['name']})")
        return map_data

    def add_feature(
        self,
        map_id: str,
        layer_id: str,
        feature_type: str,
        coordinates: Any,
        properties: Optional[dict] = None,
    ) -> dict:
        """向图层添加单个要素

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            feature_type: 要素类型（marker/polyline/polygon）
            coordinates: 要素坐标
                - marker: [lat, lng]
                - polyline/polygon: [[lat, lng], [lat, lng], ...]
            properties: 要素属性（可选）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图或图层不存在
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                layer["coordinates"].append(coordinates)
                # 如果图层类型与新要素类型不一致，更新图层类型
                if feature_type and layer["type"] != feature_type:
                    layer["type"] = feature_type
                self._schedule_save()
                logger.info(f"[MapService] 要素已添加到图层: {layer_id}")
                return map_data

        raise MapGenerationError(f"图层不存在: {layer_id}")

    def remove_feature(self, map_id: str, layer_id: str, feature_id: str) -> dict:
        """从图层移除要素

        通过要素索引（feature_id格式为"index:N"）移除指定要素。

        Args:
            map_id: 地图ID
            layer_id: 图层ID
            feature_id: 要素ID（索引格式 "index:0"）

        Returns:
            更新后的完整地图数据

        Raises:
            MapGenerationError: 地图、图层或要素不存在
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")

        for layer in map_data["layers"]:
            if layer["id"] == layer_id:
                # 解析要素索引
                try:
                    if feature_id.startswith("index:"):
                        index = int(feature_id.split(":")[1])
                    else:
                        index = int(feature_id)
                except (ValueError, IndexError):
                    raise MapGenerationError(f"无效的要素ID: {feature_id}")

                if 0 <= index < len(layer["coordinates"]):
                    layer["coordinates"].pop(index)
                    self._schedule_save()
                    logger.info(f"[MapService] 要素已移除: {feature_id}")
                    return map_data
                else:
                    raise MapGenerationError(f"要素索引超出范围: {index}")

        raise MapGenerationError(f"图层不存在: {layer_id}")

    # ==================== 内部辅助方法 ====================


    def _apply_cartographic_profile(
        self, map_type: str, map_layers: List[dict], zoom: int
    ) -> List[dict]:
        """按 Cartographic Profile 约束图层集合（《武汉四类专题地图数据规范》）

        1) 移除各主题禁止的图层（forbidden_layers）
        2) 交通图：提取「主要桥梁」独立主题层（跨江结构）
        3) 旅游图：POI 按 P0-P3 分级写入 importance（前端 LOD 抽稀优先保留核心景点）
        """
        from app.core.cartographic_profiles import (
            get_profile, get_tourism_level, is_major_bridge,
        )
        profile = get_profile(map_type)
        filtered = [
            l for l in map_layers
            if not profile.layer_forbidden(l.get("name") or "")
        ]
        if map_type == "traffic":
            bridge_layer = self._extract_bridge_layer(map_layers)
            if bridge_layer:
                filtered.append(bridge_layer)
            filtered = self._add_transport_reference_layers(filtered)
        elif map_type == "tourism":
            for l in filtered:
                if l.get("type") not in ("circleMarker", "marker", "point"):
                    continue
                level, importance, _ = get_tourism_level(l.get("name") or "")
                for p in (l.get("properties") or []):
                    if isinstance(p, dict):
                        p.setdefault("importance", importance)
                        p["poi_level"] = level
        return filtered

    def _add_transport_reference_layers(self, layers: List[dict]) -> List[dict]:
        """交通图补齐：铁路独立图层 + 交通枢纽实体（真实来源，非 mock）"""
        try:
            from app.core.transport_reference import RAILWAYS, HUBS
            # 铁路（polyline，真实节点走向）
            rail_coords = []
            rail_props = []
            for r in RAILWAYS:
                rail_coords.append(r["coords"])
                rail_props.append({
                    "name": r["name"], "category": "railway",
                    "importance": r["importance"], "source": r["source"],
                    "verification_status": r["verification_status"],
                    "geometry_quality": r.get("geometry_quality", "approximate"),
                    "source_confidence": r.get("source_confidence", "unverified"),
                })
            if rail_coords:
                layers.append({
                    "id": generate_id("layer"), "type": "polyline", "name": "铁路",
                    "coordinates": rail_coords, "properties": rail_props,
                    "style": {"color": "#555555", "weight": 2.0, "opacity": 0.85,
                              "dashArray": "8,4"},
                    "group": "交通要素",
                })
            # 交通枢纽（circleMarker 真实坐标）
            hub_coords = [[h["lat"], h["lng"]] for h in HUBS]
            hub_props = [{"name": h["name"], "category": "transport_hub",
                          "importance": h["importance"], "source": h["source"],
                          "verification_status": h["verification_status"],
                          "geometry_quality": "reference_point",
                          "source_confidence": "unverified"} for h in HUBS]
            if hub_coords:
                layers.append({
                    "id": generate_id("layer"), "type": "circleMarker", "name": "交通枢纽",
                    "coordinates": hub_coords, "properties": hub_props,
                    "style": {"color": "#d97706", "fillColor": "#f59e0b", "fillOpacity": 0.9,
                              "weight": 2, "radius": 7, "icon": "🚉"},
                    "group": "交通要素",
                })
        except Exception as e:
            logger.info(f"[MapService] 交通补充数据加载失败: {e}")
        return layers

    def _extract_bridge_layer(self, map_layers: List[dict]) -> Optional[dict]:
        """从道路线图层提取「主要桥梁」（跨江/跨河重要桥梁）独立主题层"""
        from app.core.cartographic_profiles import is_major_bridge
        bridge_coords: List[list] = []
        bridge_props: List[dict] = []
        for l in map_layers:
            if l.get("type") not in ("polyline", "line"):
                continue
            if "道路" not in (l.get("name") or ""):
                continue
            props = l.get("properties") or []
            coords = l.get("coordinates") or []
            for i, p in enumerate(props):
                nm = (p.get("name") or "") if isinstance(p, dict) else ""
                if is_major_bridge(nm) and i < len(coords):
                    bridge_coords.append(coords[i])
                    bridge_props.append({"name": nm, "kind": "bridge", "importance": 1.0})
        if not bridge_coords:
            return None
        return {
            "id": generate_id("layer"),
            "type": "polyline",
            "name": "主要桥梁",
            "coordinates": bridge_coords,
            "properties": bridge_props,
            "style": {"color": "#1e40af", "weight": 3.0, "opacity": 0.95},
            "group": "交通要素",
        }

    @staticmethod
    def _zoom_to_scale(zoom: int) -> int:
        """前端 WebMercator zoom → 近似比例尺分母（用于制图综合尺度）"""
        if zoom is None:
            return 250_000
        if zoom < 9:
            return 1_000_000
        if zoom <= 10:
            return 250_000
        if zoom <= 12:
            return 100_000
        return 25_000

    def _apply_generalization(
        self, map_type: str, map_layers: List[dict], zoom: int
    ) -> Dict[str, Any]:
        """调用 GeneralizationEngine 做真实制图综合，返回 metrics"""
        try:
            from app.services.generalization import GeneralizationEngine
            engine = GeneralizationEngine()
            scale = self._zoom_to_scale(zoom)
            # linemerge 后统一去重 exact/reverse（避免重复进入综合）
            map_layers[:] = self._dedupe_polyline_layers(map_layers)
            result = engine.generalize(map_type, map_layers, scale)
            # 用综合后的图层替换（就地修改 map_layers 引用）
            map_layers[:] = result["layers"]
            return result.get("metrics", {})
        except Exception as e:
            logger.info(f"[MapService] 制图综合失败（保留原图层）: {e}")
            return {"error": str(e)}

    def _dedupe_polyline_layers(self, map_layers: List[dict]) -> List[dict]:
        """对 polyline 图层做 exact/reverse 去重（linemerge 后统一）"""
        for layer in map_layers:
            if layer.get("type") != "polyline":
                continue
            coords = layer.get("coordinates") or []
            props = layer.get("properties") or []
            seen = set()
            kept_c, kept_p = [], []
            removed = 0
            for i, c in enumerate(coords):
                if not (isinstance(c, (list, tuple)) and c and isinstance(c[0], (list, tuple))):
                    kept_c.append(c)
                    if props:
                        kept_p.append(props[i])
                    continue
                try:
                    key = repr([(round(float(p[0]), 4), round(float(p[1]), 4)) for p in c])
                    rkey = repr([(round(float(p[0]), 4), round(float(p[1]), 4)) for p in reversed(c)])
                except Exception:
                    kept_c.append(c)
                    if props:
                        kept_p.append(props[i])
                    continue
                if key in seen or rkey in seen:
                    removed += 1
                else:
                    seen.add(key)
                    seen.add(rkey)
                    kept_c.append(c)
                    if props:
                        kept_p.append(props[i])
            if removed:
                layer["coordinates"] = kept_c
                if props:
                    layer["properties"] = kept_p
                layer["_dedup_removed"] = removed
        return map_layers

    def _apply_symbol_registry(self, map_layers: List[dict]) -> List[dict]:
        """SymbolRegistry 接入渲染链：图层样式统一从注册表解析。

        - 已具备主题样式的图层（行政区弱化、交通加粗等）保留其透明度/宽度修饰；
        - 未显式配色或使用通用默认色的图层改为注册表符号色；
        - 每个图层记录 symbol_id，供 QA/前端追溯符号来源。
        """
        from app.core.cartographic_profiles import LAYER_CATEGORY
        from app.services.cartography.symbols.registry import resolve_by_category

        GENERIC_WEIGHTS = {0.8, 1.0, 1.5, 2.0, 3.0}
        GENERIC_COLORS = {"#3388ff", "#3388ff".upper()}
        for layer in map_layers:
            layer["group"] = self._classify_layer_group(layer)
            if layer.get("symbol_id"):
                continue
            name = layer.get("name") or ""
            geom = layer.get("type") or ""
            cat = LAYER_CATEGORY.get(name)
            sym = resolve_by_category(cat, geom) if cat else None
            if not sym:
                continue
            st = dict(layer.get("style") or {})
            cur_color = str(st.get("color") or "").lower()
            cur_fill = str(st.get("fillColor") or "").lower()
            if (not cur_color or cur_color in GENERIC_COLORS) and sym.get("color"):
                st["color"] = sym["color"]
            if sym.get("casing") and not st.get("casing"):
                st["casing"] = sym["casing"]
            try:
                cur_w = float(st.get("weight") or 0)
            except (TypeError, ValueError):
                cur_w = 0
            if sym.get("width") and (cur_w == 0 or cur_w in GENERIC_WEIGHTS):
                st["weight"] = sym["width"]
            if (not cur_fill or cur_fill in GENERIC_COLORS) and sym.get("color"):
                st["fillColor"] = sym["color"]
            layer["style"] = st
            layer["symbol_id"] = sym["symbol_id"]
        return map_layers

    @staticmethod
    def _classify_layer_group(layer: dict) -> str:
        """图层分组：行政/道路/轨道/桥梁/交通枢纽/水系/地形/旅游POI/居民地/注记/底图"""
        name = layer.get("name") or ""
        ltype = layer.get("type") or ""
        if ltype == "polygon" and any(k in name for k in ("陆地底图", "湖北省域", "底图")):
            return "底图"
        if any(k in name for k in ("区县政区", "区县界", "市界", "省界", "境界", "边界",
                                   "行政中心", "乡镇界")):
            return "行政区划"
        if ltype in ("textLabel", "label") or "注记" in name or "标注" in name:
            return "注记"
        if any(k in name for k in ("铁路", "轨道", "地铁", "轻轨")):
            return "轨道交通"
        if "桥梁" in name:
            return "桥梁"
        if any(k in name for k in ("枢纽", "机场", "车站", "公交", "火车站")):
            return "交通枢纽"
        if any(k in name for k in ("道路", "高速", "公路", "干道", "环线", "匝道",
                                   "国道", "省道")):
            return "道路"
        if any(k in name for k in ("河", "湖", "水库", "水系", "溪流", "水")):
            return "水系"
        if any(k in name for k in ("等高线", "山峰", "山体", "地貌")):
            return "地形地貌"
        if any(k in name for k in ("景点", "旅游", "公园", "博物馆", "文化", "历史",
                                   "宗教", "自然", "地标", "名胜", "古迹")):
            return "旅游POI"
        if any(k in name for k in ("建成区", "街区", "居民地", "居民区")):
            return "居民地"
        return "制图要素"

    @staticmethod
    def _label_priority_for_layer(layer_name: str) -> str:
        """LabelEngine 优先级分类：行政名称 > 核心地名 > 主要交通 > 核心POI > 普通"""
        name = layer_name or ""
        if any(k in name for k in ("区县名称", "市级名称", "行政", "政区")):
            return "admin"
        if any(k in name for k in ("地标", "水系注记", "湖泊注记", "城市名称")):
            return "core_place"
        if any(k in name for k in ("道路注记", "桥梁", "轨道", "铁路", "枢纽")):
            return "transport"
        if any(k in name for k in ("景点", "景区", "旅游", "公园", "博物馆")):
            return "core_poi"
        return "normal"

    @staticmethod
    def _label_min_zoom(layer_name: str, prop: dict) -> int:
        """注记最小显示比例尺档位（zoom）：小比例尺只保留重要注记。

        规则依据《武汉四类专题地图数据规范》注记分级：
        市级名称 z>=6（常显）→ 区县名称 z>=8（1:100万 即可见，13 区可识别）
        → 山峰 z>=9 / 地标 z>=10 → 大湖 z>=8 / 小湖 z>=12 / 主干道 z>=10 / 次干道 z>=13。
        """
        name = layer_name or ""
        pname = (prop.get("name") or "") if isinstance(prop, dict) else ""
        if "市级名称" in name:
            return 6
        if "区县名称" in name:
            return 8
        if "山峰" in name:
            return 9
        if any(k in name for k in ("地标", "重点地标")):
            return 10
        if "水系" in name or "湖泊" in name:
            # 湖泊按面积分档（面状要素注记规范）：≥100km² z7 / ≥30 z8 / ≥5 z10 / 其余 z12
            try:
                area = float(prop.get("area_km2")) if prop.get("area_km2") is not None else None
            except (TypeError, ValueError):
                area = None
            if area is not None:
                if area >= 100:
                    return 7
                if area >= 30:
                    return 8
                if area >= 5:
                    return 10
                return 12
            MAJOR_WATER = {
                "长江", "汉江", "东湖", "汤逊湖", "梁子湖", "涨渡湖", "斧头湖",
                "武湖", "后官湖", "沉湖", "严西湖", "童家湖", "牛山湖", "鲁湖",
                "豹澥后湖", "夏家寺水库", "梅店水库", "后湖", "金银湖",
            }
            return 8 if pname in MAJOR_WATER else 12
        if "道路" in name:
            # 道路注记按等级：高速/干线/主干道 z>=10，次干道 z>=13，其他 z>=14
            if any(k in (prop.get("layer") or "") for k in ("高速公路", "城市干线", "城市主干道")):
                return 10
            if "次干道" in (prop.get("layer") or ""):
                return 13
            return 14
        if any(k in name for k in ("铁路", "轨道")):
            return 9
        return 12

    @staticmethod
    def _label_importance(layer_name: str, prop: dict) -> float:
        """注记重要性（0-1），供前端按比例尺/载负量优先保留"""
        name = layer_name or ""
        if any(k in name for k in ("市级名称", "区县名称")):
            return 1.0
        if "山峰" in name:
            return 0.9
        if any(k in name for k in ("地标", "重点地标")):
            return 0.8
        if "水系" in name or "湖泊" in name:
            pname = (prop.get("name") or "") if isinstance(prop, dict) else ""
            try:
                area = float(prop.get("area_km2")) if prop.get("area_km2") is not None else None
            except (TypeError, ValueError):
                area = None
            if area is not None:
                return 0.95 if area >= 100 else (0.85 if area >= 30 else 0.5)
            MAJOR_WATER = {
                "长江", "汉江", "东湖", "汤逊湖", "梁子湖", "涨渡湖", "斧头湖",
                "武湖", "后官湖", "沉湖", "严西湖", "童家湖", "牛山湖", "鲁湖",
                "豹澥后湖", "夏家寺水库", "梅店水库", "后湖", "金银湖",
            }
            return 0.9 if pname in MAJOR_WATER else 0.5
        if "道路" in name:
            if any(k in (prop.get("layer") or "") for k in ("高速公路", "城市干线", "城市主干道")):
                return 0.7
            return 0.4
        if any(k in name for k in ("铁路", "轨道")):
            return 0.8
        return 0.3

    @staticmethod
    def _label_priority_value(layer_name: str, prop: dict) -> int:
        """注记优先级数值（规范 §二：P0=100 / P1=80 / P2=50 / P3=20）"""
        from app.core.label_spec import P0, P1, P2, P3
        name = layer_name or ""
        pname = (prop.get("name") or "") if isinstance(prop, dict) else ""
        # P0：市名、核心河流、核心交通枢纽
        if "市级名称" in name:
            return P0
        if any(k in name for k in ("枢纽", "火车站", "机场")):
            return P0
        if pname in ("长江", "汉江"):
            return P0
        # P1：区名、主要道路、铁路/轨道、核心景区/地标
        if "区县名称" in name:
            return P1
        if any(k in name for k in ("铁路", "轨道", "地铁", "轻轨")):
            return P1
        if any(k in name for k in ("重点地标", "地标名称")):
            return P1
        if "道路" in name:
            src = (prop.get("layer") or "") if isinstance(prop, dict) else ""
            if any(k in src for k in ("高速公路", "城市干线", "城市主干道")):
                return P1
            if "次干道" in src:
                return P2
            return P3
        # 水系：核心大湖 P1，一般水系 P2
        if "水系" in name or "湖泊" in name:
            MAJOR_WATER = {
                "长江", "汉江", "东湖", "汤逊湖", "梁子湖", "涨渡湖", "斧头湖",
                "武湖", "后官湖", "沉湖", "严西湖", "童家湖", "牛山湖", "鲁湖",
                "豹澥后湖", "夏家寺水库", "梅店水库", "后湖", "金银湖",
            }
            try:
                area = float(prop.get("area_km2")) if prop.get("area_km2") is not None else None
            except (TypeError, ValueError):
                area = None
            if area is not None:
                return P1 if area >= 30 else P2
            return P1 if pname in MAJOR_WATER else P2
        if "山峰" in name:
            return P1
        if any(k in name for k in ("景点", "景区", "公园", "博物馆")):
            return P2
        return P3

    @staticmethod
    def _label_feature_type(layer_name: str) -> str:
        """注记要素类型（admin/water/transport/poi/peak）"""
        name = layer_name or ""
        if any(k in name for k in ("区县", "市级", "行政", "政区")):
            return "admin"
        if any(k in name for k in ("水系", "湖泊", "河流", "溪流")):
            return "water"
        if any(k in name for k in ("道路", "高速", "公路", "干道", "铁路", "轨道",
                                   "桥梁", "枢纽", "车站", "机场")):
            return "transport"
        if "山峰" in name:
            return "peak"
        return "poi"

    def _apply_label_engine(self, map_type: str, map_layers: List[dict], zoom: int) -> dict:
        """LabelEngine 接入：点注记候选/碰撞消解 + 道路/河流线注记。

        1) textLabel 点注记：同一 0.02° 格网内保留高优先级、抑制低优先级（真实消解）；
        2) 线注记：主要道路/河流取线中点生成「道路注记/水系注记」层，含旋转角；
        3) 输出 label_metrics（放置/抑制/重要标签召回/碰撞率）。
        """
        from app.services.label.engine import LabelEngine
        from app.core.constants import CITY_BBOX
        from app.core.label_spec import make_label_meta

        engine = LabelEngine()
        bbox = CITY_BBOX.get("武汉市", {})
        if not bbox:
            return {"applied": False, "reason": "no_bbox"}

        canvas = (1680, 950)
        min_lat, max_lat = float(bbox["min_lat"]), float(bbox["max_lat"])
        min_lng, max_lng = float(bbox["min_lon"]), float(bbox["max_lon"])
        span_lat = max(1e-6, max_lat - min_lat)
        span_lng = max(1e-6, max_lng - min_lng)

        def to_px(lat, lng):
            x = int((lng - min_lng) / span_lng * (canvas[0] - 120) + 60)
            y = int((max_lat - lat) / span_lat * (canvas[1] - 120) + 60)
            return x, y

        placed_count = 0
        suppressed_count = 0
        priority_total: Dict[int, int] = {}
        line_out_of_bounds = 0
        used_cells: Dict[str, int] = {}

        def cell_key(lat, lng):
            return f"{round(float(lat) / 0.02)},{round(float(lng) / 0.02)}"

        for layer in map_layers:
            if layer.get("type") not in ("textLabel", "label"):
                continue
            coords = layer.get("coordinates") or []
            props = layer.get("properties") or []
            cat = self._label_priority_for_layer(layer.get("name") or "")
            kept_c, kept_p = [], []
            for i, c in enumerate(coords):
                if not (isinstance(c, list) and len(c) >= 2 and isinstance(c[0], (int, float))):
                    kept_c.append(c)
                    if i < len(props):
                        kept_p.append(props[i])
                    continue
                name = (props[i] if i < len(props) else {}).get("name") or ""
                _prio = self._label_priority_value(layer.get("name") or "", props[i] if i < len(props) else {})
                priority_total[_prio] = priority_total.get(_prio, 0) + 1
                # 0.02° 格网级容量：每格最多 2 个注记（行政名称例外，保证 13 区全上图）
                ck = cell_key(c[0], c[1])
                if used_cells.get(ck, 0) >= 2 and cat != "admin":
                    suppressed_count += 1
                    continue
                x, y = to_px(float(c[0]), float(c[1]))
                res = engine.place_point_label(
                    x, y, 80, 16, name, cat, (float(c[0]), float(c[1])),
                    priority=_prio,
                )
                if res.get("placed"):
                    used_cells[ck] = used_cells.get(ck, 0) + 1
                    placed_count += 1
                    kept_c.append(c)
                    if i < len(props):
                        p = dict(props[i]) if isinstance(props[i], dict) else {"name": name}
                        _lname = layer.get("name") or ""
                        _mz = self._label_min_zoom(_lname, p)
                        _prio = self._label_priority_value(_lname, p)
                        _ftype = self._label_feature_type(_lname)
                        meta = make_label_meta(
                            generate_id("label"), name, _ftype, _prio,
                            "point", _mz, _ftype,
                        )
                        meta["importance"] = self._label_importance(_lname, p)
                        meta["rotation"] = p.get("rotation", 0)
                        meta["category"] = cat
                        kept_p.append(meta)
                else:
                    suppressed_count += 1
            layer["coordinates"] = kept_c
            if props:
                layer["properties"] = kept_p
            layer["label_engine"] = {"category": cat, "suppressed": len(coords) - len(kept_c)}

        # 线注记：主要道路/河流/轨道（有名称）沿中线放置，按类别分入注记层
        line_labels = []          # 道路注记
        water_line_labels = []    # 水系注记（并入已有水系注记层或新建）
        rail_line_labels = []     # 铁路/轨道注记
        LINE_HINT = ("道路", "高速", "公路", "干道", "环线", "匝道")
        WATER_HINT = ("河流", "水系", "长江", "汉江", "溪流")
        RAIL_HINT = ("铁路", "轨道", "地铁", "轻轨")
        for layer in map_layers:
            if layer.get("type") not in ("polyline", "line"):
                continue
            lname = layer.get("name") or ""
            is_road = any(k in lname for k in LINE_HINT)
            is_water = any(k in lname for k in WATER_HINT)
            is_rail = any(k in lname for k in RAIL_HINT)
            if not (is_road or is_water or is_rail):
                continue
            coords = layer.get("coordinates") or []
            props = layer.get("properties") or []
            for i, c in enumerate(coords):
                if not (isinstance(c, list) and len(c) >= 2 and isinstance(c[0], list)):
                    continue
                p = props[i] if i < len(props) else {}
                name = (p.get("name") or "") if isinstance(p, dict) else ""
                if not name or len(c) < 3:
                    continue
                # 每层最多 60 条线注记，避免载负量过高
                if len(line_labels) >= 60:
                    break
                # LabelEngine 线注记约定坐标为 (lat, lng)
                lonlat = [(float(pt[0]), float(pt[1])) for pt in c
                          if isinstance(pt, list) and len(pt) >= 2]
                if len(lonlat) < 2:
                    continue
                _lname = ("道路注记" if is_road else
                          ("水系注记" if is_water else "轨道注记"))
                _prop = {"name": name, "layer": lname}
                _prio = self._label_priority_value(_lname, _prop)
                res = engine.place_line_label(
                    lonlat, name, "transport", canvas,
                    bounds=(min_lat, min_lng, max_lat, max_lng),
                    priority=_prio,
                )
                if res.get("reason") == "out_of_bounds":
                    line_out_of_bounds += 1
                if res.get("placed"):
                    mid = lonlat[len(lonlat) // 2]
                    lat, lng = mid[0], mid[1]
                    ck = cell_key(mid[1], mid[0])
                    if used_cells.get(ck, 0) >= 2:
                        continue
                    used_cells[ck] = used_cells.get(ck, 0) + 1
                    _ftype = "transport" if (is_road or is_rail) else "water"
                    _mz = self._label_min_zoom(_lname, _prop)
                    priority_total[_prio] = priority_total.get(_prio, 0) + 1
                    meta = make_label_meta(
                        generate_id("label"), name, _ftype, _prio,
                        "line", _mz, _ftype,
                    )
                    meta["importance"] = self._label_importance(_lname, _prop)
                    meta["rotation"] = res.get("angle", 0)
                    meta["lineLabel"] = True
                    meta["layer"] = lname
                    _label = {
                        "lat": lat, "lng": lng, "name": name, "meta": meta,
                    }
                    if is_road:
                        line_labels.append(_label)
                    elif is_water:
                        water_line_labels.append(_label)
                    elif is_rail:
                        rail_line_labels.append(_label)
        # 道路注记层（仅道路；河流注记并入水系注记层，避免混层）
        def _append_line_labels(target_name: str, labels: list, base_style: dict):
            if not labels:
                return
            target = next((l for l in map_layers if l.get("name") == target_name), None)
            if target is None:
                target = {
                    "id": generate_id("layer"),
                    "type": "textLabel",
                    "name": target_name,
                    "coordinates": [],
                    "properties": [],
                    "style": dict(base_style),
                    "group": "注记",
                }
                map_layers.append(target)
            for lb in labels:
                target["coordinates"].append([lb["lat"], lb["lng"]])
                target["properties"].append(lb["meta"])

        if (line_labels or water_line_labels or rail_line_labels) and map_type in (
                "traffic", "tourism", "administrative", "basic"):
            _append_line_labels("道路注记", line_labels,
                                {"color": "#374151", "fontSize": 11, "weight": 2,
                                 "font": "song", "lineLabel": True})
            _append_line_labels("水系注记", water_line_labels,
                                {"color": "#1e3a8a", "fontSize": 12, "weight": 2,
                                 "font": "song", "lineLabel": True})
            _append_line_labels("轨道注记", rail_line_labels,
                                {"color": "#6b21a8", "fontSize": 11, "weight": 2,
                                 "font": "song", "lineLabel": True})
            placed_count += len(line_labels) + len(water_line_labels) + len(rail_line_labels)

        from app.services.label.metrics import compute_metrics
        important_total = sum(v for k, v in priority_total.items() if k >= 60)
        metrics = compute_metrics(
            engine.placed, engine.suppressed,
            important_total=important_total,
            total_by_priority=priority_total,
            out_of_bounds_count=0,          # 越界注记已被拒绝，已放置注记越界率=0
            total_labels=placed_count,
        )
        metrics["rejected_out_of_bounds_count"] = line_out_of_bounds
        metrics.update({
            "line_label_count": len(line_labels),
            "water_line_label_count": len(water_line_labels),
            "rail_line_label_count": len(rail_line_labels),
            "point_label_count": placed_count - len(line_labels) - len(water_line_labels) - len(rail_line_labels),
            "suppressed_count": suppressed_count,
            "applied": True,
        })
        return metrics

    @staticmethod
    def _build_layout(map_name: str, map_type: str, legend: dict) -> dict:
        """LayoutEngine 版式规划：标题/图例/比例尺/指北针/来源/坐标/时间 + 冲突避免"""
        from app.services.cartography.layout import LayoutEngine
        le = LayoutEngine()
        plan = le.plan(
            map_name,
            map_type,
            has_legend=bool((legend or {}).get("items")),
            has_scale_bar=True,
        )
        plan["validation"] = le.validate(plan)
        return plan


    def _generate_thematic_layers(self, map_type: str, region: str, center: List[float]) -> List[dict]:
        """生成专题地图图层数据"""
        from app.core.constants import THEMATIC_MAP_CONFIG
        import random
        if map_type == "terrain":
            return self._generate_terrain_layers(region, center)
        config = THEMATIC_MAP_CONFIG.get(map_type, {})
        if not config:
            return []
        layers = []
        cs = config.get("color_scheme", ["#3388ff"])
        rt = config.get("render_type", "choropleth")
        lid = generate_id("layer")
        def rp(o=0.06):
            return [center[0] + random.uniform(-o, o), center[1] + random.uniform(-o, o)]
        if rt == "heatmap":
            pts = []
            for _ in range(120):
                p = rp(0.08)
                pts.append([p[0], p[1], random.uniform(0.2, 1.0)])
            layers.append({"id": lid, "type": "heatmap", "name": config.get("name", "热力图"), "coordinates": pts, "style": {"color_scheme": cs, "radius": 35, "blur": 25, "maxZoom": 17, "minOpacity": 0.3}, "metadata": {"render_type": "heatmap", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "point_count": len(pts)}})
        elif rt == "proportional_symbol":
            feats = []
            for i in range(60):
                p = rp(0.07)
                v = random.uniform(10, 100)
                s = 5 + (v / 100) * 25
                ci = min(int(v / 20), len(cs) - 1)
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "name": f"点{i+1}", "size": round(s, 1)}, "style": {"color": cs[ci], "radius": s, "fillOpacity": 0.7, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "比例符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "proportional_symbol"}, "metadata": {"render_type": "proportional_symbol", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        elif rt == "choropleth":
            feats = []
            gs = 8
            off = 0.08
            step = (off * 2) / gs
            for i in range(gs):
                for j in range(gs):
                    lat = center[0] - off + i * step
                    lng = center[1] - off + j * step
                    v = random.uniform(0, 100)
                    ci = min(int(v / (100 / len(cs))), len(cs) - 1)
                    coords = [[lat, lng], [lat + step, lng], [lat + step, lng + step], [lat, lng + step], [lat, lng]]
                    feats.append({"id": generate_id("feat"), "type": "polygon", "coordinates": coords, "properties": {"value": round(v, 1), "grid_id": f"{i}_{j}"}, "style": {"color": cs[ci], "fillColor": cs[ci], "fillOpacity": 0.6, "weight": 0.5, "opacity": 0.3}})
            layers.append({"id": lid, "type": "polygon", "name": config.get("name", "分级色彩图"), "features": feats, "style": {"color_scheme": cs, "render_type": "choropleth"}, "metadata": {"render_type": "choropleth", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "grid_size": f"{gs}x{gs}", "feature_count": len(feats)}})
        elif rt == "categorical":
            feats = []
            if isinstance(cs, dict):
                cats = list(cs.keys())
                for i in range(80):
                    p = rp(0.07)
                    cat = random.choice(cats)
                    feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"category": cat, "name": cat}, "style": {"color": cs[cat], "fillColor": cs[cat], "radius": 6, "fillOpacity": 0.8, "weight": 1}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分类图"), "features": feats, "style": {"color_scheme": cs, "render_type": "categorical"}, "metadata": {"render_type": "categorical", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "categories": list(cs.keys()) if isinstance(cs, dict) else [], "feature_count": len(feats)}})
        elif rt == "graduated":
            feats = []
            for i in range(70):
                p = rp(0.07)
                v = random.uniform(0, 50)
                if v < 10: s, col = 4, cs[0]
                elif v < 20: s, col = 8, cs[1] if len(cs) > 1 else cs[0]
                elif v < 30: s, col = 14, cs[2] if len(cs) > 2 else cs[-1]
                elif v < 40: s, col = 20, cs[3] if len(cs) > 3 else cs[-1]
                else: s, col = 28, cs[-1]
                feats.append({"id": generate_id("feat"), "type": "point", "coordinates": p, "properties": {"value": round(v, 1), "level": int(v / 10)}, "style": {"color": col, "fillColor": col, "radius": s, "fillOpacity": 0.6, "weight": 1.5}})
            layers.append({"id": lid, "type": "circle", "name": config.get("name", "分级符号图"), "features": feats, "style": {"color_scheme": cs, "render_type": "graduated"}, "metadata": {"render_type": "graduated", "description": config.get("description", ""), "legend_title": config.get("legend_title", ""), "unit": config.get("unit", ""), "feature_count": len(feats)}})
        return layers

    def _generate_terrain_layers(self, region: str = "武汉市", center: Optional[List[float]] = None) -> List[dict]:
        """地势图（DEM 山体阴影 + 等高线）：陆地底图 + 计曲线/首曲线 + 山峰注记。

        等高线数据来自 SRTM 30m DEM（tools/generate_contours.py 已做制图综合：
        舍谷-微小谷地锯齿化简、扩谷-典型弯曲保护、鞍部保持-鞍部邻域顶点保护，
        以及遇河/湖断开处理）。
        水系/道路/行政边界由通用流程叠加（generate_map 统一处理），避免重复。
        前端配合「山体阴影」底图瓦片（hillshade）作为地势底图。
        """
        from app.core.constants import CITY_BBOX
        from app.services.contour_service import ContourService
        layers = []

        # 陆地底图（米黄色，衬托等高线）
        bbox = CITY_BBOX.get(region, {})
        if bbox:
            land = [[bbox["min_lat"], bbox["min_lon"]], [bbox["min_lat"], bbox["max_lon"]],
                    [bbox["max_lat"], bbox["max_lon"]], [bbox["max_lat"], bbox["min_lon"]],
                    [bbox["min_lat"], bbox["min_lon"]]]
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "陆地底图",
                "coordinates": [land],
                "style": {"fillColor": "#f2ead7", "fillOpacity": 0.85,
                          "color": "#e2d5b8", "weight": 0.5, "opacity": 0.6},
            })

        # 等高线（计曲线/首曲线）
        try:
            contour_layers = ContourService().get_contour_layers()
            layers.extend(contour_layers)
        except Exception as e:
            logger.info(f"[MapService] 等高线图层加载失败: {e}")

        # 山峰注记（名称 + 高程，SRTM DEM 山峰点）
        try:
            from app.services.local_geo_service import LocalGeoService
            peak_layers = LocalGeoService().get_peaks_layers(region)
            layers.extend(peak_layers)
        except Exception as e:
            logger.info(f"[MapService] 地势图山峰注记加载失败: {e}")

        return layers

    def _generate_fallback_layers(self, map_type: str, region: str = "武汉市", center: Optional[List[float]] = None, zoom: Optional[int] = None) -> List[dict]:
        """生成本地回退图层（当OSM数据不可用时使用本地地标数据）

        对于武汉市使用WUHAN_LANDMARKS中的详细地标数据；
        对于其他城市，根据中心坐标生成模拟地标数据。

        Args:
            map_type: 地图类型
            region: 区域名称
            center: 中心坐标 [lat, lng]

        Returns:
            图层列表，包含地标的marker要素
        """
        # 根据地图类型筛选合适的地标
        type_filter = {
            "tourism": ["attraction", "scenic", "museum", "cultural"],
            "food": ["food"],
            "campus": ["university"],
            "traffic": ["landmark", "commercial"],
            "basic": None,  # None表示所有类型
        }
        filter_types = type_filter.get(map_type, None)

        markers = []

        if region == "武汉市":
            # 使用武汉详细地标数据
            for landmark in WUHAN_LANDMARKS:
                if filter_types is None or landmark["type"] in filter_types:
                    markers.append({
                        "name": landmark["name"],
                        "lat": landmark["lat"],
                        "lng": landmark["lng"],
                        "type": landmark["type"],
                    })
        else:
            # 其他城市：根据中心坐标生成模拟地标
            if center and len(center) == 2:
                base_lat, base_lng = center[0], center[1]
                # 模拟地标数据（围绕中心点分布）
                sim_landmarks = [
                    {"name": f"{region}中心地标", "lat": base_lat, "lng": base_lng, "type": "landmark"},
                    {"name": f"{region}博物馆", "lat": base_lat + 0.02, "lng": base_lng + 0.01, "type": "museum"},
                    {"name": f"{region}公园", "lat": base_lat - 0.015, "lng": base_lng + 0.02, "type": "scenic"},
                    {"name": f"{region}大学", "lat": base_lat + 0.025, "lng": base_lng - 0.015, "type": "university"},
                    {"name": f"{region}商业区", "lat": base_lat - 0.01, "lng": base_lng - 0.02, "type": "commercial"},
                    {"name": f"{region}美食街", "lat": base_lat + 0.015, "lng": base_lng + 0.025, "type": "food"},
                ]
                for landmark in sim_landmarks:
                    if filter_types is None or landmark["type"] in filter_types:
                        markers.append(landmark)

        if not markers:
            # 如果没有匹配的地标，至少返回所有地标
            if region == "武汉市":
                markers = [{"name": lm["name"], "lat": lm["lat"], "lng": lm["lng"], "type": lm["type"]} for lm in WUHAN_LANDMARKS]
            elif center:
                markers = [{"name": f"{region}中心", "lat": center[0], "lng": center[1], "type": "landmark"}]

        if not markers:
            return []

        # 旅游图使用分类标记（不同类型不同颜色和符号）
        if map_type == "tourism":
            cat_map = {
                "attraction": "scenic", "scenic": "scenic", "museum": "museum",
                "cultural": "cultural", "university": "university", "food": "food",
                "commercial": "commercial", "landmark": "landmark",
            }
            by_cat = {}
            for m in markers:
                cat = cat_map.get(m.get("type", "default"), "default")
                by_cat.setdefault(cat, []).append(m)

            layers = []
            for cat, items in by_cat.items():
                cfg = TOURISM_CATEGORIES.get(cat, TOURISM_CATEGORIES["default"])
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": cfg["name"],
                    "coordinates": [[m["lat"], m["lng"]] for m in items],
                    "properties": [{"name": m["name"], "category": cat} for m in items],
                    "style": {
                        "color": cfg["color"],
                        "fillColor": cfg.get("fillColor", cfg["color"]),
                        "fillOpacity": cfg.get("fillOpacity", 0.7),
                        "weight": cfg.get("weight", 2),
                        "radius": cfg.get("radius", 6),
                        "icon": cfg.get("icon", "📍"),
                    },
                })
            return layers

        # 交通图：生成模拟分级道路 + 铁路 + 地标
        if map_type == "traffic":
            layers = []
            if center and len(center) == 2:
                import random
                clat, clng = center[0], center[1]
                # 模拟各级道路
                road_templates = [
                    ("motorway", "高速公路", [[clat - 0.06, clng - 0.08], [clat - 0.02, clng - 0.03], [clat + 0.01, clng + 0.02], [clat + 0.05, clng + 0.07]]),
                    ("trunk", "主干道-南北", [[clat - 0.07, clng + 0.01], [clat - 0.03, clng + 0.005], [clat + 0.02, clng], [clat + 0.06, clng - 0.01]]),
                    ("primary", "主要道路-东西", [[clat + 0.005, clng - 0.09], [clat, clng - 0.04], [clat - 0.005, clng + 0.03], [clat - 0.01, clng + 0.08]]),
                    ("secondary", "次干道1", [[clat - 0.04, clng - 0.05], [clat - 0.01, clng - 0.02], [clat + 0.02, clng + 0.01]]),
                    ("secondary", "次干道2", [[clat + 0.03, clng - 0.06], [clat + 0.01, clng - 0.02], [clat - 0.01, clng + 0.04]]),
                    ("tertiary", "支路1", [[clat - 0.02, clng - 0.03], [clat, clng - 0.01], [clat + 0.01, clng + 0.02]]),
                    ("tertiary", "支路2", [[clat + 0.02, clng + 0.01], [clat + 0.03, clng + 0.03], [clat + 0.04, clng + 0.05]]),
                ]
                if zoom is None or zoom >= 13:
                    road_templates += [
                        ("residential", "社区道路1", [[clat - 0.01, clng - 0.01], [clat + 0.005, clng + 0.005]]),
                        ("residential", "社区道路2", [[clat + 0.01, clng - 0.02], [clat + 0.02, clng - 0.01]]),
                    ]
                # 按道路等级分组渲染
                by_class = {}
                for rtype, rname, rcoords in road_templates:
                    by_class.setdefault(rtype, []).append({"coords": rcoords, "name": rname})
                sorted_classes = sorted(
                    by_class.items(),
                    key=lambda x: ROAD_CLASSIFICATION.get(x[0], {}).get("level", 99)
                )
                for road_class, items in sorted_classes:
                    cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])
                    if "outer" in cfg:
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(外层)",
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(cfg["outer"]),
                        })
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(内层)",
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(cfg["inner"]),
                        })
                    else:
                        style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": cfg["name"],
                            "coordinates": [item["coords"] for item in items],
                            "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                            "style": dict(style),
                        })
                # 模拟铁路
                rail_coords = [[clat - 0.05, clng + 0.06], [clat - 0.02, clng + 0.04], [clat + 0.02, clng + 0.02], [clat + 0.06, clng - 0.02]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "普通铁路(外层)",
                    "coordinates": [rail_coords],
                    "style": dict(RAILWAY_CLASSIFICATION["rail"]["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "普通铁路(内层)",
                    "coordinates": [rail_coords],
                    "style": dict(RAILWAY_CLASSIFICATION["rail"]["inner"]),
                })
                # 地铁
                subway_coords = [[clat - 0.03, clng - 0.06], [clat, clng - 0.02], [clat + 0.03, clng + 0.03]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "地铁",
                    "coordinates": [subway_coords],
                    "style": {k: v for k, v in RAILWAY_CLASSIFICATION["subway"].items() if k != "name"},
                })
            # 添加地标标记
            if markers:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": "交通枢纽",
                    "coordinates": [[m["lat"], m["lng"]] for m in markers],
                    "properties": [{"name": m["name"], "category": "landmark"} for m in markers],
                    "style": {
                        "color": TOURISM_CATEGORIES["landmark"]["color"],
                        "fillColor": TOURISM_CATEGORIES["landmark"]["fillColor"],
                        "fillOpacity": 0.8, "weight": 2, "radius": 7,
                        "icon": TOURISM_CATEGORIES["landmark"]["icon"],
                        "iconClass": TOURISM_CATEGORIES["landmark"].get("iconClass"),
                    },
                })
            return layers

        # 基础地图：生成模拟道路 + 建筑物面状要素 + 水系 + 地标
        if map_type == "basic":
            layers = []
            if center and len(center) == 2:
                import random
                clat, clng = center[0], center[1]
                # 模拟主要道路
                road_templates = [
                    ("motorway", "高速公路", [[clat - 0.06, clng - 0.08], [clat - 0.02, clng - 0.03], [clat + 0.05, clng + 0.07]]),
                    ("primary", "主要道路", [[clat - 0.07, clng + 0.01], [clat + 0.06, clng - 0.01]]),
                    ("secondary", "次干道", [[clat + 0.005, clng - 0.09], [clat - 0.01, clng + 0.08]]),
                    ("tertiary", "支路", [[clat - 0.02, clng - 0.03], [clat + 0.01, clng + 0.02]]),
                ]
                by_class = {}
                for rtype, rname, rcoords in road_templates:
                    by_class.setdefault(rtype, []).append({"coords": rcoords, "name": rname})
                for road_class, items in by_class.items():
                    cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])
                    if "outer" in cfg:
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(外层)",
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(cfg["outer"]),
                        })
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": f"{cfg['name']}(内层)",
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(cfg["inner"]),
                        })
                    else:
                        style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                        layers.append({
                            "id": generate_id("layer"),
                            "type": "polyline",
                            "name": cfg["name"],
                            "coordinates": [item["coords"] for item in items],
                            "style": dict(style),
                        })
                # 模拟河流
                river_coords = [[clat - 0.08, clng - 0.02], [clat - 0.04, clng + 0.01], [clat, clng + 0.03], [clat + 0.04, clng + 0.05], [clat + 0.08, clng + 0.06]]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": "河流",
                    "coordinates": [river_coords],
                    "style": {k: v for k, v in WATERWAY_STYLES["river"].items() if k != "name"},
                })
                # 模拟建筑物面状要素
                building_templates = [
                    ("residential", "住宅小区", clat + 0.02, clng - 0.03, 0.008),
                    ("residential", "居民楼", clat - 0.03, clng + 0.04, 0.006),
                    ("commercial", "商业中心", clat + 0.01, clng + 0.05, 0.01),
                    ("public", "政府大楼", clat - 0.01, clng - 0.05, 0.008),
                    ("school", "学校", clat + 0.04, clng - 0.02, 0.012),
                    ("hospital", "医院", clat - 0.04, clng - 0.01, 0.01),
                ]
                by_btype = {}
                for btype, bname, blat, blng, bsize in building_templates:
                    coords = [
                        [blat - bsize, blng - bsize],
                        [blat - bsize, blng + bsize],
                        [blat + bsize, blng + bsize],
                        [blat + bsize, blng - bsize],
                        [blat - bsize, blng - bsize],
                    ]
                    by_btype.setdefault(btype, []).append({"coords": coords, "name": bname})
                for btype, items in by_btype.items():
                    style = BUILDING_STYLES.get(btype, BUILDING_STYLES["default"])
                    layers.append({
                        "id": generate_id("layer"),
                        "type": "polygon",
                        "name": style["name"],
                        "coordinates": [item["coords"] for item in items],
                        "properties": [{"name": item["name"], "subtype": btype} for item in items],
                        "style": {
                            "color": style["color"],
                            "fillColor": style["fillColor"],
                            "fillOpacity": style["fillOpacity"],
                            "weight": style["weight"],
                        },
                    })
                # 模拟公园
                park_coords = [
                    [clat + 0.05, clng + 0.02],
                    [clat + 0.05, clng + 0.06],
                    [clat + 0.02, clng + 0.06],
                    [clat + 0.02, clng + 0.02],
                    [clat + 0.05, clng + 0.02],
                ]
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polygon",
                    "name": "公园",
                    "coordinates": [park_coords],
                    "properties": [{"name": "城市公园", "subtype": "park"}],
                    "style": {
                        "color": GREENSPACE_STYLES["park"]["color"],
                        "fillColor": GREENSPACE_STYLES["park"]["fillColor"],
                        "fillOpacity": GREENSPACE_STYLES["park"]["fillOpacity"],
                        "weight": GREENSPACE_STYLES["park"]["weight"],
                    },
                })
            # 添加地标标记
            if markers:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "circleMarker",
                    "name": "地标建筑",
                    "coordinates": [[m["lat"], m["lng"]] for m in markers],
                    "properties": [{"name": m["name"], "category": m.get("type", "landmark")} for m in markers],
                    "style": {
                        "color": TOURISM_CATEGORIES["landmark"]["color"],
                        "fillColor": TOURISM_CATEGORIES["landmark"]["fillColor"],
                        "fillOpacity": 0.8, "weight": 2, "radius": 6,
                        "icon": TOURISM_CATEGORIES["landmark"]["icon"],
                        "iconClass": TOURISM_CATEGORIES["landmark"].get("iconClass"),
                    },
                })
            return layers

        # 行政区划图：离线回退时生成模拟省/市/区边界，避免只有地标点
        if map_type == "administrative":
            layers = []
            if center and len(center) == 2:
                clat, clng = center[0], center[1]

                def _box(half):
                    return [[clat - half, clng - half], [clat - half, clng + half],
                            [clat + half, clng + half], [clat + half, clng - half],
                            [clat - half, clng - half]]

                for name, color, weight, half, dash in [
                    ("省界(周边外省)", "#000000", 1.2, 0.35, "1,4"),
                    ("地级市界", "#7040A0", 3.2, 0.22, None),
                    ("区县界", "#000000", 1.5, 0.10, "7,3,1,3"),
                ]:
                    _style = {"color": color, "weight": weight, "opacity": 0.9}
                    if dash:
                        _style["dashArray"] = dash
                    layers.append({
                        "id": generate_id("layer"), "type": "polyline", "name": name,
                        "coordinates": [_box(half)],
                        "style": _style,
                    })
                layers.append({
                    "id": generate_id("layer"), "type": "polyline", "name": "乡镇界",
                    "coordinates": [
                        [[clat - 0.10, clng], [clat + 0.10, clng]],
                        [[clat, clng - 0.10], [clat, clng + 0.10]],
                    ],
                    "style": {"color": "#000000", "weight": 0.8, "opacity": 0.6, "dashArray": "2,3"},
                })
            # 行政区名称标注（武汉区县中心兜底）
            if region == "武汉市":
                layers.append({
                    "id": generate_id("layer"),
                    "type": "textLabel",
                    "name": "区县名称标注",
                    "coordinates": [[d["lat"], d["lng"]] for d in WUHAN_DISTRICTS],
                    "properties": [{"name": d["name"]} for d in WUHAN_DISTRICTS],
                    "style": {"color": "#1e3a8a", "fontSize": 15, "weight": 3},
                })
            return layers

        # 其他地图类型保持原有逻辑
        layer_style = MAP_STYLES.get("amenity", {"color": "#f59e0b", "radius": 6})
        return [{
            "id": generate_id("layer"),
            "type": "marker",
            "name": f"{region}地标（本地数据）",
            "coordinates": [[m["lat"], m["lng"]] for m in markers],
            "properties": [{"name": m["name"], "type": m["type"]} for m in markers],
            "style": layer_style,
        }]

    @staticmethod
    def _district_area(layers: List[dict]) -> float:
        """计算区县政区面的球面总面积（km²），用于质量校验"""
        import math
        R = 6371.0
        total = 0.0
        for layer in layers:
            if layer.get("name") != "区县政区":
                continue
            for feat in layer.get("features", []):
                ring = feat.get("coordinates") or []
                if len(ring) < 3:
                    continue
                area = 0.0
                n = len(ring)
                for i in range(n):
                    j = (i + 1) % n
                    lat1 = math.radians(ring[i][0])
                    lon1 = math.radians(ring[i][1])
                    lat2 = math.radians(ring[j][0])
                    lon2 = math.radians(ring[j][1])
                    area += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
                total += abs(area * R * R / 2.0)
        return round(total, 2)

    def add_custom_marker(self, map_id: str, name: str, lat: float, lng: float,
                          icon: str = None, color: str = "#e11d48") -> dict:
        """添加自定义标注点（答辩演示：标注赏樱点/卫生间等自定义点位）

        自动创建/复用"自定义标注"circleMarker图层。
        """
        map_data = self._get_map(map_id)
        if not map_data:
            raise MapGenerationError(f"地图不存在: {map_id}")
        layer = None
        for L in map_data["layers"]:
            if L.get("name") == "自定义标注":
                layer = L
                break
        if layer is None:
            layer = {
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": "自定义标注",
                "coordinates": [],
                "properties": [],
                "style": {"color": color, "fillColor": "#ffffff", "fillOpacity": 1.0,
                          "radius": 7, "weight": 2.5, "icon": icon or "\U0001f4cd"},
            }
            map_data["layers"].append(layer)
        layer["coordinates"].append([lat, lng])
        layer["properties"].append({"name": name})
        map_data["layers"] = self._sort_layers(map_data["layers"])
        self._schedule_save()
        logger.info(f"[MapService] 已添加自定义标注: {name} ({lat},{lng})")
        return map_data

    def _sort_layers(self, layers: List[dict]) -> List[dict]:
        """按制图规范调整图层叠置顺序

        面状底图（绿地/用地/水体）→ 建筑面 → 水系线 → 铁路 → 道路 → 点状符号。
        高等级道路最后绘制（位于顶层），保证主干道视觉突出；
        采用稳定排序，同层要素保持原有相对顺序。
        """
        road_rank = {
            "高速公路": 90, "国道": 80, "主干道": 80, "省道": 70, "主要道路": 70,
            "次干道": 60, "支路": 50, "社区道路": 40, "服务道路": 30, "其他道路": 20,
        }

        def zkey(layer: dict) -> int:
            t = layer.get("type", "")
            name = layer.get("name", "")
            if t in ("polygon", "area"):
                if "陆地" in name:
                    return 0
                if any(k in name for k in ("水体", "湖泊", "水库")):
                    return 50
                if any(k in name for k in ("用地", "绿地", "公园", "花园", "森林", "草地",
                                           "草甸", "土地", "政区", "区划")):
                    return 100
                if any(k in name for k in ("建筑", "住宅", "公寓", "宿舍", "商业", "零售", "酒店",
                                           "工业", "公共", "政府", "学校", "大学", "医院", "宗教",
                                           "文化", "体育", "停车", "车库", "仓储", "交通枢纽",
                                           "农业", "温室")):
                    return 200
                return 100
            if t in ("polyline", "line"):
                if any(k in name for k in ("水系", "河流", "溪流", "运河", "湖泊", "水库")):
                    return 300
                if "边界" in name:
                    return 350
                if any(k in name for k in ("铁路", "地铁", "轻轨", "高铁")):
                    return 400
                rank = next((r for k, r in road_rank.items() if k in name), 10)
                return 500 + rank
            if t in ("textLabel", "label"):
                return 650
            return 600

        return sorted(layers, key=zkey)

    def _connect_polylines_by_name(self, map_layers: List[dict]) -> List[dict]:
        """线状要素按名称连通：把同一条道路/边界/铁路的离散线段合并为完整折线。

        制图综合要求不同比例尺下主要道路保持连通，不出现“一段一段”的割裂。
        方法：按要素名称分组 → 坐标吸附到 1m 网格 → unary_union + linemerge。

        仅对「道路/边界/铁路」类图层中有名称的要素执行连接：
        - 无名称要素（支流溪流、等高线等）不属于同一要素，强制合并会造成
          语义错误并导致 unary_union 性能灾难（数千米长 MultiLineString）。
        - 等高线按高程独立表达，禁止跨线合并。
        """
        from shapely.geometry import LineString
        from shapely.ops import linemerge, unary_union
        from app.core.crs_manager import CRSManager
        _crs = CRSManager()
        CONNECT_HINT = ("道路", "高速", "公路", "国道", "省道", "干道", "边界",
                        "境界", "铁路", "轨道", "环线", "匝道")

        for layer in map_layers:
            if layer.get("type") not in ("polyline", "line"):
                continue
            lname = layer.get("name") or ""
            if "等高线" in lname:
                continue
            if not any(k in lname for k in CONNECT_HINT):
                continue
            coords = layer.get("coordinates") or []
            props = layer.get("properties") or []
            if len(coords) < 2:
                continue
            groups: Dict[str, List[Any]] = {}
            for i, c in enumerate(coords):
                if not isinstance(c, list) or len(c) < 2:
                    continue
                name = (props[i] if i < len(props) else {}).get("name") or ""
                if not name:
                    # 无名称线段保持原样（不属于任何可连接要素）
                    continue
                groups.setdefault(name, []).append((c, props[i] if i < len(props) else {}))

            merged_coords: List[Any] = []
            merged_props: List[dict] = []
            for name, segs in groups.items():
                lines = []
                for c, _p in segs:
                    try:
                        rounded = [[round(p[0], 5), round(p[1], 5)]
                                   for p in c if isinstance(p, list) and len(p) >= 2]
                        if len(rounded) >= 2:
                            lines.append(LineString([(p[1], p[0]) for p in rounded]))
                    except Exception:
                        pass
                if not lines:
                    continue
                try:
                    union = unary_union(lines)
                    merged = linemerge(union)
                    geoms = list(merged.geoms) if merged.geom_type == "MultiLineString" else [merged]
                    for g in geoms:
                        if g.geom_type != "LineString" or len(g.coords) < 2:
                            continue
                        merged_coords.append([[y, x] for x, y in g.coords])
                        # 保留原始属性（如等高线 ele/index），附加合并标记与米制长度
                        base_prop = dict(segs[0][1]) if segs and isinstance(segs[0][1], dict) else {}
                        length_m = _crs.length_meters([(x, y) for x, y in g.coords])
                        merged_props.append({
                            **base_prop,
                            "name": name,
                            "merged": True,
                            "length_km": round(length_m / 1000.0, 2),
                        })
                except Exception:
                    # 合并失败时保留原线段
                    for c, p in segs:
                        merged_coords.append(c)
                        merged_props.append(p)
            # 无名称线段按原顺序保留（不再参与分组合并）
            for i, c in enumerate(coords):
                name = (props[i] if i < len(props) else {}).get("name") or ""
                if not name:
                    merged_coords.append(c)
                    merged_props.append(props[i] if i < len(props) else {})
            if merged_coords:
                layer["coordinates"] = merged_coords
                layer["properties"] = merged_props
        return map_layers

    def _generate_legend(self, map_type: str, map_layers: List[dict]) -> dict:
        """根据地图类型和图层生成图例数据

        优先使用LEGEND_TEMPLATES中的预设模板，并根据实际图层过滤；
        若无模板则从图层数据动态生成。

        Args:
            map_type: 地图类型
            map_layers: 图层列表

        Returns:
            图例字典 {title, items: [{label, type, color, ...}]}
        """
        # 背景/上下文图层不进入主题图例，减少视觉噪声（只保留主题要素）
        _base_layers = {"陆地底图", "湖北省域", "武汉市域底图", "周边地市"}
        map_layers = [
            layer for layer in map_layers
            if (layer.get("name") or "") not in _base_layers
            and not (layer.get("name") or "").startswith("集中居民地")
        ]

        # 收集实际存在的图层名称（去除"(外层)""(内层)"后缀）
        actual_names = set()
        actual_styles = {}
        for layer in map_layers:
            name = layer.get("name", "")
            # 去除后缀得到基础名称
            base_name = name.replace("(外层)", "").replace("(内层)", "").strip()
            actual_names.add(base_name)
            actual_styles[base_name] = layer.get("style", {})

        # 优先使用预设模板（根据实际图层过滤）
        if map_type in LEGEND_TEMPLATES:
            template = LEGEND_TEMPLATES[map_type]
            filtered_items = []
            for item in template["items"]:
                label = item.get("label", "")
                # 对交通图等模板：仅保留实际存在的图层对应的图例项
                if map_type in ("traffic", "basic", "campus", "administrative"):
                    if label in actual_names:
                        filtered_items.append(item)
                else:
                    # 其他类型保留全部图例项
                    filtered_items.append(item)

            # 如果过滤后为空（模板名称与真实图层不匹配），改为按真实图层动态生成，
            # 保证图例配色与实际渲染一致（避免“协调性”错位）
            if not filtered_items:
                filtered_items = []

            # 补充实际存在但模板未覆盖的图层项（POI象形符号/线/面），保证整套图例完整
            covered = {it.get("label") for it in filtered_items}
            for layer in map_layers:
                base_name = layer.get("name", "").replace("(外层)", "").replace("(内层)", "").strip()
                if base_name in covered:
                    continue
                style = layer.get("style", {})
                ltype = layer.get("type", "")
                if ltype in ("circleMarker", "marker", "point") and style.get("icon"):
                    filtered_items.append({
                        "label": base_name, "type": "point",
                        "color": style.get("color", "#f59e0b"),
                        "icon": style.get("icon", "\U0001f4cd"),
                        "iconClass": style.get("iconClass"),
                        "radius": style.get("radius", 6),
                        "group": style.get("group", "兴趣点(POI)"),
                    })
                elif ltype in ("textLabel", "label"):
                    filtered_items.append({
                        "label": base_name, "type": "point",
                        "color": style.get("color", "#1e3a8a"),
                        "icon": "\U0001f3f7\ufe0f",
                        "group": "行政区划",
                    })
                elif ltype in ("polygon", "area"):
                    filtered_items.append({
                        "label": base_name, "type": "polygon",
                        "fillColor": style.get("fillColor", style.get("color", "#3388ff")),
                        "color": style.get("color", "#3388ff"),
                        "fillOpacity": style.get("fillOpacity", 0.3),
                    })
                elif ltype in ("polyline", "line"):
                    filtered_items.append({
                        "label": base_name, "type": "line",
                        "color": style.get("color", "#3388ff"),
                        "weight": style.get("weight", 3),
                        "dashArray": style.get("dashArray"),
                    })
                covered.add(base_name)

            return {"title": template["title"], "items": filtered_items}

        # 动态生成：从图层数据中提取图例项
        legend_items = []
        seen_labels = set()
        for layer in map_layers:
            name = layer.get("name", "")
            # 去除后缀，避免"外层""内层"生成重复图例
            base_name = name.replace("(外层)", "").replace("(内层)", "").strip()
            if base_name in seen_labels:
                continue
            style = layer.get("style", {})
            ltype = layer.get("type", "")

            if ltype in ("polyline", "line"):
                legend_items.append({
                    "label": base_name, "type": "line",
                    "color": style.get("color", "#3388ff"),
                    "weight": style.get("weight", 3),
                    "dashArray": style.get("dashArray"),
                })
            elif ltype in ("polygon", "area"):
                legend_items.append({
                    "label": base_name, "type": "polygon",
                    "fillColor": style.get("fillColor", style.get("color", "#3388ff")),
                    "color": style.get("color", "#3388ff"),
                    "fillOpacity": style.get("fillOpacity", 0.3),
                })
            elif ltype in ("circleMarker", "marker", "point", "circle"):
                legend_items.append({
                    "label": base_name, "type": "point",
                    "color": style.get("color", "#f59e0b"),
                    "icon": style.get("icon", "📍"),
                    "iconClass": style.get("iconClass"),
                    "radius": style.get("radius", 6),
                    "group": style.get("group", "兴趣点(POI)"),
                })
            seen_labels.add(base_name)

        return {"title": f"图例（{len(legend_items)}项）", "items": legend_items}

    def _elements_to_layers(
        self,
        elements_by_type: Dict[str, List[dict]],
        element_types: List[str],
        map_type: str = "basic",
    ) -> List[dict]:
        """将OSM元素按类型转换为图层列表（增强版）

        按要素类型分发到专用处理器，支持：
        - 建筑物面状渲染（按类型分色）
        - 道路分级渲染（主要道路双层渲染）
        - 铁路分类渲染
        - 水系分类渲染
        - 旅游地分类标记（不同颜色和符号）
        - 绿地面状渲染

        Args:
            elements_by_type: 按类型分组的OSM元素字典
            element_types: 要素类型列表
            map_type: 地图类型（用于按地图类型配置过滤道路等级等）

        Returns:
            图层列表
        """
        layers = []
        # 水系类型（waterway_major/waterway_minor等）合并为一次处理，
        # 保证河源/汇入口检测能同时看到主河与支流
        _water_merged = False

        for typ in element_types:
            base_tag = typ.split("~")[0]
            elements = elements_by_type.get(base_tag, [])
            if not elements:
                continue
            if base_tag.startswith("waterway"):
                if _water_merged:
                    continue
                _water_merged = True
                merged = []
                for _t in element_types:
                    if _t.split("~")[0].startswith("waterway"):
                        merged.extend(elements_by_type.get(_t, []))
                elements = merged

            way_elements = [e for e in elements if e.get("type") == "way"]
            node_elements = [e for e in elements if e.get("type") == "node"]
            other_elements = [e for e in elements if e.get("type") not in ("way", "node")]
            way_elements.extend(other_elements)

            # 按要素类型分发到专用处理器
            if base_tag == "building":
                layers.extend(self._process_buildings(way_elements))
            elif base_tag.startswith("highway"):
                layers.extend(self._process_roads(way_elements, map_type))
            elif base_tag == "railway":
                layers.extend(self._process_railways(way_elements))
            elif base_tag.startswith("waterway"):
                layers.extend(self._process_waterways(way_elements))
            elif base_tag == "boundary":
                layers.extend(self._process_boundaries(way_elements))
            elif base_tag in ("place", "place_city", "place_suburb"):
                layers.extend(self._process_place_labels(node_elements))
            elif base_tag in ("tourism", "historic", "amenity", "shop", "office"):
                layers.extend(self._process_poi(node_elements, way_elements, base_tag))
            elif base_tag in ("landuse", "natural"):
                layers.extend(self._process_landuse(way_elements))
            elif base_tag == "leisure":
                layers.extend(self._process_greenspace(way_elements))
            else:
                layers.extend(self._process_default(way_elements, node_elements, base_tag))

        return layers

    # ==================== 要素分类处理方法 ====================

    def _process_buildings(self, way_elements: List[dict]) -> List[dict]:
        """处理建筑物要素 - 面状渲染，按类型分色"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            # 确保面状闭合
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            btype = self._classify_building(tags)
            name = tags.get("name", "")
            by_type.setdefault(btype, []).append({"coords": coords, "name": name})

        layers = []
        for btype, items in by_type.items():
            style = BUILDING_STYLES.get(btype, BUILDING_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": btype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _classify_building(self, tags: dict) -> str:
        """根据OSM标签判断建筑物子类型

        优先级：building标签 → amenity标签 → 属性标签推断。
        amenity类别的建筑用途通过映射归入对应建筑大类，保证分类完整。
        """
        bval = tags.get("building", "yes")
        if bval != "yes" and bval in BUILDING_STYLES:
            return bval
        # 检查amenity标签推断建筑类型
        amenity = tags.get("amenity", "")
        if amenity in BUILDING_STYLES:
            return amenity
        amenity_fallback = {
            "restaurant": "commercial", "cafe": "commercial", "fast_food": "commercial",
            "bar": "commercial", "pub": "commercial", "bank": "commercial",
            "pharmacy": "commercial", "fuel": "commercial", "marketplace": "retail",
            "supermarket": "retail", "mall": "retail",
            "library": "public", "post_office": "public", "community_centre": "civic",
            "townhall": "government", "courthouse": "government",
            "police": "government", "fire_station": "government", "embassy": "government",
            "clinic": "hospital", "doctors": "hospital", "dentist": "hospital",
            "kindergarten": "school", "college": "university",
            "theatre": "civic", "cinema": "civic", "arts_centre": "civic",
            "events_venue": "civic", "stadium": "sports", "sports_centre": "sports",
            "gym": "sports", "place_of_worship": "religious",
            "hostel": "hotel", "motel": "hotel", "guest_house": "hotel",
            "transportation": "train_station", "bus_station": "train_station",
        }
        if amenity in amenity_fallback:
            return amenity_fallback[amenity]
        # 检查其他标签
        if tags.get("shop"):
            return "retail"
        if tags.get("office"):
            return "commercial"
        if tags.get("residential") == "yes":
            return "residential"
        if tags.get("commercial") == "yes":
            return "commercial"
        if tags.get("industrial") == "yes":
            return "industrial"
        return "default"

    def _process_roads(self, way_elements: List[dict], map_type: str = "basic") -> List[dict]:
        """处理道路要素 - 按等级分级渲染，主要道路双层渲染

        根据地图类型配置(MAP_TYPE_PROFILES)过滤道路等级：
        - 行政区划图：仅保留 motorway/trunk/primary
        - 交通图：保留 motorway/trunk/primary/secondary
        - 地势图：仅保留 motorway/trunk
        - 基础地图：保留全部等级
        """
        # 按地图类型获取允许的道路等级
        from app.core.constants import MAP_TYPE_PROFILES
        profile = MAP_TYPE_PROFILES.get(map_type, {})
        allowed_levels = profile.get("road_levels")  # None 表示不限制

        by_class = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            highway_type = tags.get("highway", "default")
            if highway_type not in ROAD_CLASSIFICATION:
                highway_type = "default"
            # 按地图类型过滤道路等级
            if allowed_levels is not None and highway_type not in allowed_levels:
                continue
            name = tags.get("name", tags.get("ref", ""))
            by_class.setdefault(highway_type, []).append({"coords": coords, "name": name})

        layers = []
        # 按道路等级排序（高等级优先渲染，低等级在上层）
        sorted_classes = sorted(
            by_class.items(),
            key=lambda x: ROAD_CLASSIFICATION.get(x[0], {}).get("level", 99)
        )

        for road_class, items in sorted_classes:
            cfg = ROAD_CLASSIFICATION.get(road_class, ROAD_CLASSIFICATION["default"])

            if "outer" in cfg:
                # 主要道路双层渲染：外层（深色粗线）+ 内层（浅色细线）
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(外层)",
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(cfg["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(内层)",
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(cfg["inner"]),
                })
            else:
                # 普通道路单层渲染
                style = {k: v for k, v in cfg.items() if k not in ("name", "level")}
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"],
                    "coordinates": [item["coords"] for item in items],
                    "properties": [{"name": item["name"], "subtype": road_class} for item in items],
                    "style": dict(style),
                })
        return layers

    def _process_railways(self, way_elements: List[dict]) -> List[dict]:
        """处理铁路要素 - 按类型分类渲染"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            rtype = tags.get("railway", "default")
            if rtype not in RAILWAY_CLASSIFICATION:
                rtype = "default"
            # 高速铁路特殊判断
            if rtype == "rail" and tags.get("highspeed") == "yes":
                rtype = "high_speed"
            name = tags.get("name", "")
            by_type.setdefault(rtype, []).append({"coords": coords, "name": name})

        layers = []
        for rtype, items in by_type.items():
            cfg = RAILWAY_CLASSIFICATION.get(rtype, RAILWAY_CLASSIFICATION["default"])
            if "outer" in cfg:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(外层)",
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(cfg["outer"]),
                })
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": f"{cfg['name']}(内层)",
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(cfg["inner"]),
                })
            else:
                style = {k: v for k, v in cfg.items() if k != "name"}
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"],
                    "coordinates": [item["coords"] for item in items],
                    "style": dict(style),
                })
        return layers

    def _fallback_water_layers(self, region: str, surrounding_only: bool = False) -> List[dict]:
        """本地水系底图：长江/汉江干流折线 + 全图幅主要湖泊面 + 蓝色水系注记

        图幅包含武汉及周边地市（规范底图要素：长江/汉江/湖泊构成水路底图）。
        OSM 水系抓取缺失时补全图幅；OSM 已有武汉水系时只补周边地市水系（surrounding_only）。
        """
        import math
        layers = []
        rivers = WUHAN_WATER_FALLBACK.get("rivers", [])
        lakes = list(WUHAN_WATER_FALLBACK.get("lakes", []))
        if surrounding_only:
            # 只补周边地市水系（武汉核心湖泊已由OSM精细数据提供，避免重叠）
            core = {"东湖", "汤逊湖", "梁子湖", "涨渡湖", "后官湖", "金银湖", "严西湖", "青菱湖"}
            lakes = [lk for lk in lakes if lk["name"] not in core]
        if rivers:
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": "河流干流",
                "coordinates": [r["coords"] for r in rivers],
                "properties": [{"name": r["name"], "subtype": "river"} for r in rivers],
                "style": {"color": "#1e90ff", "weight": 2.6, "opacity": 0.9},
            })
        lake_polys = []
        lake_labels = []
        for lk in lakes:
            coords = lk.get("coords") or []
            if len(coords) < 3:
                continue
            lake_polys.append({"coords": coords, "name": lk["name"]})
            # 大湖标注名称（质心位置），小湖不标避免文字压面外
            if lk.get("label", False):
                _c0 = sum(p[0] for p in coords) / len(coords)
                _c1 = sum(p[1] for p in coords) / len(coords)
                lake_labels.append({"coords": [_c0, _c1], "name": lk["name"]})
        if lake_polys:
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": "湖泊",
                "coordinates": [p["coords"] for p in lake_polys],
                "properties": [{"name": p["name"], "subtype": "lake"} for p in lake_polys],
                "style": {"fillColor": "#1e90ff", "fillOpacity": 0.5,
                          "color": "#1e90ff", "weight": 1.2, "opacity": 0.8},
            })
        if lake_labels:
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": "水系注记" if not surrounding_only else "水系注记(周边)",
                "coordinates": [l["coords"] for l in lake_labels],
                "properties": [{"name": l["name"], "rotation": 0} for l in lake_labels],
                "style": {"color": "#2E6FA3", "fontSize": 12, "weight": 2, "font": "song"},
            })
        return layers

    def _process_waterways(self, way_elements: List[dict]) -> List[dict]:
        """处理水系要素 - 单线河由细到粗渐变，注记沿河道布局

        制图规范：
        - 单线河符号由细到粗渐变（河源细线→干流粗线），体现上下游关系；
        - 河源生成"河源"点状符号；支流汇入主河/湖泊处生成"汇入口"符号，
          汇入口定位于主河曲率最大处的顶点（水涯线在曲率最大处相交）；
        - 湖泊水库按蓝色面渲染；主要河流生成沿河道方向的注记（字头顺流向）。
        """
        import math
        tiers = {}          # tier_index -> [segment_coords,...]
        tier_names = ["河源细流", "上游河道", "中游河道", "下游河道", "干流主河道"]
        # 规范一-2：水系统一蓝色#4088C8，河流等级越高线条越粗（干流≈0.5mm/2.4px）
        tier_weights = [1.2, 1.6, 2.0, 2.4, 2.8]
        tier_colors = ["#1e90ff", "#1e90ff", "#1e90ff", "#1e90ff", "#1e90ff"]
        minor = []
        river_lines = []    # {"coords": [...], "name": str}
        areas = {}
        labels = []
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            if "waterway" in tags:
                wtype = tags["waterway"]
            elif tags.get("natural") == "water":
                wtype = "lake"
            elif tags.get("landuse") == "reservoir":
                wtype = "reservoir"
            else:
                wtype = "default"
            name = tags.get("name", "")
            if wtype in ("lake", "reservoir") or tags.get("natural") == "water" or tags.get("landuse") == "reservoir":
                if coords[0] != coords[-1]:
                    coords = coords + [coords[0]]
                areas.setdefault(wtype, []).append({"coords": coords, "name": name})
                # 湖泊/水库名称注记：蓝色宋体，置于水面内部（规范四）
                if name:
                    _c0 = sum(p[0] for p in coords) / len(coords)
                    _c1 = sum(p[1] for p in coords) / len(coords)
                    labels.append({"coords": [_c0, _c1], "name": name, "rotation": 0})
            elif wtype == "river":
                n = len(coords)
                river_lines.append({"coords": coords, "name": name})
                # 按顶点数切分为 2~5 段渐变（权重/颜色逐级递增，体现上下游）
                ntier = 2 if n < 9 else (3 if n < 15 else (4 if n < 24 else 5))
                step = (n - 1) / max(1, ntier - 1)
                for t in range(ntier):
                    a = int(round(t * step))
                    b = int(round((t + 1) * step))
                    if b > n - 1:
                        b = n - 1
                    if a >= b:
                        continue
                    tiers.setdefault(t, []).append(coords[a:b + 1])
                if name:
                    c_idx = n // 2
                    p0 = coords[max(0, c_idx - 1)]
                    p1 = coords[min(n - 1, c_idx + 1)]
                    ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
                    labels.append({"coords": coords[c_idx], "name": name, "rotation": round(ang)})
            else:
                minor.append({"coords": coords, "name": name})

        layers = []
        # ---- 河流渐变渲染（多级宽度/颜色渐变）----
        for t in sorted(tiers.keys()):
            segs = tiers[t]
            if not segs:
                continue
            layers.append({
                "id": generate_id("layer"), "type": "polyline",
                "name": tier_names[t] if t < len(tier_names) else "河道%d级" % (t + 1),
                "coordinates": segs,
                "style": {
                    "color": tier_colors[t], "weight": tier_weights[t],
                    "opacity": min(0.95, 0.85 + 0.03 * t),
                },
            })
        # ---- 支流溪流 ----
        if minor:
            layers.append({
                "id": generate_id("layer"), "type": "polyline", "name": "支流溪流",
                "coordinates": [m["coords"] for m in minor],
                "properties": [{"name": m["name"]} for m in minor],
                "style": {"color": "#1e90ff", "weight": 1.0, "opacity": 0.75},
            })
        # ---- 面状水体（湖泊/水库，蓝色）----
        for wtype, items in areas.items():
            cfg = WATERWAY_STYLES.get(wtype, WATERWAY_STYLES["default"])
            layers.append({
                "id": generate_id("layer"), "type": "polygon", "name": cfg["name"],
                "coordinates": [it["coords"] for it in items],
                "properties": [{"name": it["name"], "subtype": wtype} for it in items],
                "style": {
                    "color": cfg.get("color", "#0ea5e9"),
                    "fillColor": cfg.get("fillColor", "#7dd3fc"),
                    "fillOpacity": cfg.get("fillOpacity", 0.4),
                    "weight": cfg.get("weight", 1),
                },
            })
        # ---- 河源符号（主河上游端点，蓝色水滴形符号）----
        springs = []
        for rl in river_lines:
            if len(rl["coords"]) >= 12:
                springs.append({"coords": rl["coords"][0], "name": rl["name"]})
                if len(springs) >= 10:
                    break
        if springs:
            scfg = WATER_SYMBOL_STYLES["spring"]
            layers.append({
                "id": generate_id("layer"), "type": "circleMarker", "name": "河源",
                "coordinates": [s["coords"] for s in springs],
                "properties": [{"name": (s["name"] + "河源") if s["name"] else "河源", "kind": "spring"} for s in springs],
                "style": {
                    "color": scfg["color"], "fillColor": scfg["fillColor"],
                    "fillOpacity": scfg["fillOpacity"], "weight": scfg["weight"],
                    "radius": scfg["radius"], "icon": scfg["icon"],
                    "iconClass": scfg["iconClass"], "kind": "spring", "group": "水系符号",
                },
            })
        # ---- 汇入口（支流端点→主河/湖泊；定位于主河曲率最大处）----
        confluences = self._detect_confluences(minor, river_lines, areas)
        if confluences:
            cfg = WATER_SYMBOL_STYLES["confluence"]
            layers.append({
                "id": generate_id("layer"), "type": "circleMarker", "name": "汇入口",
                "coordinates": [c["coords"] for c in confluences],
                "properties": [
                    {"name": c["name"], "kind": c["kind"], "target": c.get("target", "")}
                    for c in confluences
                ],
                "style": {
                    "color": cfg["color"], "fillColor": cfg["fillColor"],
                    "fillOpacity": cfg["fillOpacity"], "weight": cfg["weight"],
                    "radius": cfg["radius"], "icon": cfg["icon"],
                    "iconClass": cfg["iconClass"], "kind": "confluence", "group": "水系符号",
                },
            })
        # ---- 水系注记 ----
        if labels:
            seen = set()
            uniq = []
            for lb in labels:
                if lb["name"] in seen:
                    continue
                seen.add(lb["name"])
                uniq.append(lb)
                if len(uniq) >= 16:
                    break
            wcfg = LABEL_STYLES["water"]
            for lb in uniq:
                # 字头朝上：注记旋转角限制在[-60,60]，避免文字倒置
                rot = lb["rotation"]
                lb["rotation"] = max(-60, min(60, ((rot + 180) % 360) - 180 if rot > 90 or rot < -90 else rot))
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": "水系注记",
                "coordinates": [lb["coords"] for lb in uniq],
                "properties": [{"name": lb["name"], "rotation": lb["rotation"]} for lb in uniq],
                "style": {"color": wcfg["color"], "fontSize": wcfg["fontSize"],
                          "weight": wcfg["weight"], "font": wcfg["font"]},
            })
        return layers

    def _detect_confluences(self, minor_lines: List[dict], river_lines: List[dict], areas: dict) -> List[dict]:
        """检测支流汇入主河/湖泊的汇入口

        制图规范：汇入口与主河/湖/海的水涯线在曲率最大处相交。
        实现：支流端点贴近主河时，把汇入口定位到主河最近处曲率最大的顶点；
        支流端点落入湖泊/水库时生成入湖口。
        """
        import math
        tol = 0.004  # 约400m（局部小范围平面近似）
        results = []
        seen = set()
        for mline in minor_lines:
            coords = mline.get("coords", [])
            if not coords or len(coords) < 2:
                continue
            name = mline.get("name", "")
            for ep in (coords[0], coords[-1]):
                key = (round(ep[0], 4), round(ep[1], 4))
                if key in seen:
                    continue
                seen.add(key)
                # 1) 支流端点贴近主河 → 汇入口（定位到主河曲率最大处顶点）
                best = None
                for rl in river_lines:
                    rc = rl.get("coords", [])
                    for i in range(len(rc) - 1):
                        d = self._point_seg_dist(ep, rc[i], rc[i + 1])
                        if d < tol and (best is None or d < best[0]):
                            best = (d, rl)
                if best:
                    rl = best[1]
                    v = self._max_curvature_vertex(rl["coords"], ep, window=6)
                    results.append({
                        "coords": v,
                        "name": name or "支流汇入",
                        "kind": "confluence",
                        "target": rl.get("name", "主河"),
                    })
                    continue
                # 2) 支流端点落入湖泊/水库 → 入湖口
                matched = False
                for wtype in ("lake", "reservoir"):
                    for item in areas.get(wtype, []):
                        if _point_in_ring(ep, item["coords"]):
                            results.append({
                                "coords": ep,
                                "name": name or "河流入湖",
                                "kind": "to_lake",
                                "target": item.get("name", "湖泊"),
                            })
                            matched = True
                            break
                    if matched:
                        break
        return results

    def _point_seg_dist(self, p: list, a: list, b: list) -> float:
        """点到线段距离（经纬度平面近似，局部小范围足够）"""
        import math
        px, py = p[1], p[0]
        ax, ay = a[1], a[0]
        bx, by = b[1], b[0]
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return math.hypot(px - cx, py - cy)

    def _max_curvature_vertex(self, coords: list, near: list, window: int = 6) -> list:
        """在汇入点附近寻找河道曲率最大处的顶点

        曲率用相邻两段线段的转角绝对值近似（弧度）；
        汇入口与水涯线在曲率最大处相交。
        """
        import math
        n = len(coords)
        if n < 3:
            return near
        closest = min(range(n), key=lambda i: (coords[i][0] - near[0]) ** 2 + (coords[i][1] - near[1]) ** 2)
        lo, hi = max(1, closest - window), min(n - 2, closest + window)
        best_i, best_ang = closest, -1.0
        for i in range(lo, hi + 1):
            p0, p1, p2 = coords[i - 1], coords[i], coords[i + 1]
            a1 = math.atan2(p1[0] - p0[0], p1[1] - p0[1])
            a2 = math.atan2(p2[0] - p1[0], p2[1] - p1[1])
            d = (a2 - a1 + math.pi) % (2 * math.pi) - math.pi
            if abs(d) > best_ang:
                best_ang = abs(d)
                best_i = i
        return coords[best_i]

    def _process_place_labels(self, node_elements: List[dict]) -> List[dict]:
        """处理行政区划/地名标注 - 按行政级别分级排布

        城市(place=city)大号黑体、区县中号黑体、街道小号弱化；
        注记位置位于要素点右上方，字头朝上。
        """
        city, district, street = [], [], []
        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            name = tags.get("name", "")
            if not name:
                continue
            place = tags.get("place", "")
            # 城市标注仅收真正的城市（排除区/县名，防止与区县标注重复）
            if place == "city" and not name.endswith(("区", "县")):
                city.append({"coords": coords, "name": name})
            elif name.endswith(("区", "县")) or place in ("town", "borough"):
                district.append({"coords": coords, "name": name})
            else:
                street.append({"coords": coords, "name": name})

        layer_names = {"city": "城市名称标注", "district": "区县名称标注", "town": "街道地名标注"}
        layers = []
        for items, key in ((city, "city"), (district, "district"), (street, "town")):
            if not items:
                continue
            cfg = LABEL_STYLES[key]
            layers.append({
                "id": generate_id("layer"),
                "type": "textLabel",
                "name": layer_names[key],
                "coordinates": [d["coords"] for d in items],
                "properties": [{"name": d["name"]} for d in items],
                "style": {"color": cfg["color"], "fontSize": cfg["fontSize"],
                          "weight": cfg["weight"], "font": cfg["font"],
                          "center": key in ("city", "district")},
            })
        return layers

    def _process_boundaries(self, way_elements: List[dict]) -> List[dict]:
        """处理行政区划边界 - 按行政等级分级渲染（省/市/区县/乡镇）"""
        # 行政区划界线（国家标准地图规范）：已定界禁用虚线，区县界用点划线示意；按级别区分线型/线宽/颜色
        # 省级：黑色细点线(周边外省界线)；地级市界：紫色#7040A0粗实线；县级：黑色点划线；乡级：黑色细点线
        boundary_styles = {
            "4": {"name": "省界(周边外省)", "color": "#000000", "weight": 1.2, "opacity": 0.9, "dashArray": "1,4"},
            "6": {"name": "地级市界", "color": "#7040A0", "weight": 3.2, "opacity": 0.9},
            "8": {"name": "区县界", "color": "#000000", "weight": 1.5, "opacity": 0.9, "dashArray": "7,3,1,3"},
            "9": {"name": "乡镇界", "color": "#000000", "weight": 0.8, "opacity": 0.6, "dashArray": "2,3"},
        }
        by_level = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            tags = elem.get("tags", {})
            level = str(tags.get("admin_level", ""))
            name = tags.get("name", "")
            by_level.setdefault(level, []).append({"coords": coords, "name": name})

        layers = []
        for level, items in by_level.items():
            cfg = boundary_styles.get(level, {"name": "其他边界", "color": "#FF6666", "weight": 1})
            inner_cfg = cfg.get("inner")
            # 外层
            style = {k: v for k, v in cfg.items() if k not in ("name", "inner")}
            style["osm_boundary"] = True  # 标记OSM来源界线，行政区划图按需过滤
            layers.append({
                "id": generate_id("layer"),
                "type": "polyline",
                "name": cfg["name"] + ("(外层)" if inner_cfg else ""),
                "coordinates": [it["coords"] for it in items],
                "properties": [{"name": it["name"], "subtype": "boundary", "admin_level": level} for it in items],
                "style": style,
            })
            # 内层（双线表达：浅色中心线，增强视觉层次）
            if inner_cfg:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": cfg["name"] + "(内层)",
                    "coordinates": [it["coords"] for it in items],
                    "properties": [{"name": it["name"], "subtype": "boundary", "admin_level": level} for it in items],
                    "style": dict(inner_cfg),
                })
        return layers

    def _classify_poi(self, tags: dict, base_tag: str) -> str:
        """将OSM标签归类为POI象形符号分类

        优先级：tourism > amenity > shop > office > leisure > historic
        """
        t = tags.get("tourism", "")
        if t:
            return {"attraction": "attraction", "museum": "museum", "viewpoint": "scenic",
                    "hotel": "hotel", "guest_house": "hotel", "theme_park": "park",
                    "zoo": "park", "artwork": "museum"}.get(t, "attraction")
        a = tags.get("amenity", "")
        if a:
            return {
                "restaurant": "restaurant", "cafe": "cafe", "fast_food": "fast_food",
                "bar": "bar", "pub": "pub", "biergarten": "bar", "nightclub": "bar",
                "hospital": "hospital", "clinic": "clinic", "doctors": "clinic",
                "dentist": "clinic", "veterinary": "clinic", "pharmacy": "pharmacy",
                "school": "school", "university": "university", "college": "university",
                "kindergarten": "kindergarten", "library": "library",
                "bank": "bank", "atm": "atm", "bureau_de_change": "bank",
                "police": "police", "fire_station": "fire", "post_office": "post",
                "townhall": "government", "courthouse": "government", "embassy": "government",
                "place_of_worship": "place_of_worship",
                "fuel": "fuel", "parking": "parking", "bus_station": "bus",
                "bus_stop": "bus", "taxi": "transport", "ferry_terminal": "transport",
                "train_station": "transport", "airport": "transport",
                "theatre": "theatre", "cinema": "cinema", "arts_centre": "theatre",
                "community_centre": "theatre", "marketplace": "marketplace",
                "supermarket": "supermarket", "toilets": "toilet",
                "hostel": "hostel", "motel": "hotel", "guest_house": "hotel",
                "gym": "gym", "stadium": "sports", "sports_centre": "sports",
                "swimming_pool": "sports", "bus": "bus", "subway": "subway", "hotel": "hotel", "mall": "mall",
                "attraction": "attraction", "museum": "museum", "park": "park",
                "viewpoint": "scenic", "toilet": "toilet", "post": "post",
                "public_building": "government", "civic": "civic", "arts_centre": "theatre",
            }.get(a, "default")
        if tags.get("shop"):
            s = tags["shop"]
            if s in ("supermarket", "mall", "convenience", "department_store", "pharmacy"):
                return s
            return "shop"
        if tags.get("office"):
            return "office"
        if tags.get("railway"):
            r = tags["railway"]
            if r == "subway_entrance" or (r in ("station", "halt") and tags.get("station") == "subway"):
                return "subway"
            if r in ("station", "halt", "tram_stop"):
                return "transport"
        if base_tag == "leisure" or tags.get("leisure"):
            lv = tags.get("leisure", "")
            return {"park": "park", "garden": "garden", "playground": "park",
                    "sports_centre": "sports", "stadium": "sports",
                    "swimming_pool": "sports", "pitch": "sports"}.get(lv, "park")
        if tags.get("historic"):
            return "historic"
        return "default"

    def _process_poi(self, node_elements: List[dict], way_elements: List[dict], base_tag: str) -> List[dict]:
        """处理兴趣点要素 - 按分类使用整套象形符号表示

        node要素生成点标记，way要素取中心点生成标记；
        每个分类对应专属象形符号(icon)与配色。
        """
        all_features = []

        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            category = self._classify_poi(tags, base_tag)
            name = tags.get("name", "")
            all_features.append({"coords": coords, "name": name, "category": category})

        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            lat_sum = sum(p[0] for p in coords) / len(coords)
            lng_sum = sum(p[1] for p in coords) / len(coords)
            tags = elem.get("tags", {})
            category = self._classify_poi(tags, base_tag)
            name = tags.get("name", "")
            all_features.append({"coords": [lat_sum, lng_sum], "name": name, "category": category})

        if not all_features:
            return []

        # 按分类分组创建图层
        by_category = {}
        for feat in all_features:
            by_category.setdefault(feat["category"], []).append(feat)

        layers = []
        for cat, features in by_category.items():
            cfg = POI_STYLES.get(cat, POI_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": cfg["name"],
                "coordinates": [f["coords"] for f in features],
                "properties": [{"name": f["name"], "category": cat} for f in features],
                "style": {
                    "color": cfg["color"],
                    "fillColor": "#ffffff",
                    "fillOpacity": 0.9,
                    "weight": 2.5,
                    "radius": cfg.get("radius", 6),
                    "icon": cfg.get("icon", "📍"),
                    "iconClass": cfg.get("iconClass"),
                },
            })
        return layers

    def _process_tourism(self, node_elements: List[dict], way_elements: List[dict], base_tag: str) -> List[dict]:
        """处理旅游要素 - 按类别用不同颜色和符号表示

        node要素生成点标记，way要素取中心点生成标记。
        """
        all_features = []

        for elem in node_elements:
            coords = self._extract_coordinates(elem, "marker")
            if not coords or not isinstance(coords, list) or len(coords) != 2:
                continue
            tags = elem.get("tags", {})
            category = self._classify_tourism(tags, base_tag)
            name = tags.get("name", tags.get("tourism", tags.get("historic", "")))
            all_features.append({"coords": coords, "name": name, "category": category})

        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 2:
                continue
            # 取中心点作为标记位置
            lat_sum = sum(p[0] for p in coords) / len(coords)
            lng_sum = sum(p[1] for p in coords) / len(coords)
            tags = elem.get("tags", {})
            category = self._classify_tourism(tags, base_tag)
            name = tags.get("name", tags.get("tourism", tags.get("historic", "")))
            all_features.append({"coords": [lat_sum, lng_sum], "name": name, "category": category})

        # 按类别分组创建图层
        by_category = {}
        for feat in all_features:
            by_category.setdefault(feat["category"], []).append(feat)

        layers = []
        for cat, features in by_category.items():
            cfg = TOURISM_CATEGORIES.get(cat, TOURISM_CATEGORIES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "circleMarker",
                "name": cfg["name"],
                "coordinates": [f["coords"] for f in features],
                "properties": [{"name": f["name"], "category": cat} for f in features],
                "style": {
                    "color": cfg["color"],
                    "fillColor": cfg.get("fillColor", cfg["color"]),
                    "fillOpacity": cfg.get("fillOpacity", 0.7),
                    "weight": cfg.get("weight", 2),
                    "radius": cfg.get("radius", 6),
                    "icon": cfg.get("icon", "📍"),
                    "iconClass": cfg.get("iconClass"),
                },
            })
        return layers

    def _classify_tourism(self, tags: dict, base_tag: str) -> str:
        """根据OSM标签判断旅游地类别"""
        # 历史遗迹
        if base_tag == "historic" or "historic" in tags:
            return "historic"

        tourism_val = tags.get("tourism", "")
        if tourism_val == "museum":
            return "museum"
        if tourism_val in ("attraction", "viewpoint", "artwork"):
            if tags.get("natural") or tags.get("water"):
                return "attraction"
            return "scenic"

        leisure_val = tags.get("leisure", "")
        if leisure_val in ("park", "garden", "playground", "pitch", "stadium"):
            return "park"

        amenity_val = tags.get("amenity", "")
        if amenity_val in ("restaurant", "fast_food", "cafe", "bar", "pub", "food_court"):
            return "food"
        if tourism_val == "hotel" or "shop" in tags:
            return "commercial"
        if amenity_val in ("theatre", "arts_centre", "cinema", "library"):
            return "cultural"
        if amenity_val in ("university", "college"):
            return "university"
        if tags.get("religion") or amenity_val in ("place_of_worship", "monastery"):
            return "religious"
        if tags.get("man_made"):
            return "landmark"

        return "default"

    def _process_greenspace(self, way_elements: List[dict]) -> List[dict]:
        """处理绿地要素 - 面状渲染，按类型分色"""
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            gtype = "default"
            if "landuse" in tags:
                lu = tags["landuse"]
                if lu in GREENSPACE_STYLES:
                    gtype = lu
            if "leisure" in tags and gtype == "default":
                lv = tags["leisure"]
                if lv in GREENSPACE_STYLES:
                    gtype = lv
            name = tags.get("name", "")
            by_type.setdefault(gtype, []).append({"coords": coords, "name": name})

        layers = []
        for gtype, items in by_type.items():
            style = GREENSPACE_STYLES.get(gtype, GREENSPACE_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": gtype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _process_landuse(self, way_elements: List[dict]) -> List[dict]:
        """处理土地利用要素 - 面状渲染，按用地类型全面分类

        涵盖居住、商业、工业、农业、绿地等所有土地利用类型，
        绿地类型复用GREENSPACE_STYLES，其余使用LANDUSE_STYLES。
        """
        by_type = {}
        for elem in way_elements:
            coords = self._extract_coordinates(elem, "polyline")
            if not coords or not isinstance(coords, list) or len(coords) < 3:
                continue
            if coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            tags = elem.get("tags", {})
            # 判断用地类型
            ltype = "default"
            if "landuse" in tags:
                lu = tags["landuse"]
                # 绿地类型优先用GREENSPACE_STYLES
                if lu in GREENSPACE_STYLES:
                    ltype = lu
                elif lu in LANDUSE_STYLES:
                    ltype = lu
            if "leisure" in tags and ltype == "default":
                lv = tags["leisure"]
                if lv in GREENSPACE_STYLES:
                    ltype = lv
            if "natural" in tags and ltype == "default":
                nat = tags["natural"]
                if nat == "wood":
                    ltype = "forest"
                elif nat == "grass":
                    ltype = "grass"
                elif nat == "water":
                    ltype = "water"
            name = tags.get("name", "")
            by_type.setdefault(ltype, []).append({"coords": coords, "name": name})

        layers = []
        for ltype, items in by_type.items():
            # 优先从GREENSPACE_STYLES取样式，其次从LANDUSE_STYLES
            if ltype in GREENSPACE_STYLES:
                style = GREENSPACE_STYLES[ltype]
            elif ltype == "water":
                style = {"name": "水体", "fillColor": "#7dd3fc", "color": "#0ea5e9", "fillOpacity": 0.4, "weight": 0.5}
            else:
                style = LANDUSE_STYLES.get(ltype, LANDUSE_STYLES["default"])
            layers.append({
                "id": generate_id("layer"),
                "type": "polygon",
                "name": style["name"],
                "coordinates": [item["coords"] for item in items],
                "properties": [{"name": item["name"], "subtype": ltype} for item in items],
                "style": {
                    "color": style["color"],
                    "fillColor": style["fillColor"],
                    "fillOpacity": style["fillOpacity"],
                    "weight": style["weight"],
                },
            })
        return layers

    def _process_default(self, way_elements: List[dict], node_elements: List[dict], base_tag: str) -> List[dict]:
        """默认要素处理（amenity等通用类型）"""
        type_names = {
            "amenity": "生活设施", "shop": "商店", "office": "办公",
            "natural": "自然要素", "landuse": "用地类型",
        }
        layers = []
        style = self._get_default_style(base_tag)

        if way_elements:
            way_coords = []
            for elem in way_elements:
                coords = self._extract_coordinates(elem, "polyline")
                if coords and isinstance(coords, list) and len(coords) >= 2:
                    way_coords.append(coords)
            if way_coords:
                layers.append({
                    "id": generate_id("layer"),
                    "type": "polyline",
                    "name": type_names.get(base_tag, base_tag),
                    "coordinates": way_coords,
                    "style": style,
                })

        if node_elements:
            node_coords = []
            node_props = []
            for elem in node_elements:
                coords = self._extract_coordinates(elem, "marker")
                if coords and isinstance(coords, list) and len(coords) == 2:
                    node_coords.append(coords)
                    tags = elem.get("tags", {})
                    node_props.append({
                        "name": tags.get("name", ""),
                        "type": tags.get("amenity", base_tag),
                    })
            if node_coords:
                marker_style = dict(style)
                if "weight" in marker_style:
                    del marker_style["weight"]
                if "dashArray" in marker_style:
                    del marker_style["dashArray"]
                if "radius" not in marker_style:
                    marker_style["radius"] = 6
                layers.append({
                    "id": generate_id("layer"),
                    "type": "marker",
                    "name": f"{type_names.get(base_tag, base_tag)}(点)",
                    "coordinates": node_coords,
                    "properties": node_props,
                    "style": marker_style,
                })
        return layers

    def _extract_coordinates(self, elem: dict, layer_type: str) -> Optional[Any]:
        """从OSM元素中提取坐标

        Args:
            elem: OSM元素
            layer_type: 目标图层类型

        Returns:
            坐标数据：
                - marker: [lat, lng]
                - polyline: [[lat, lng], ...]
            无法提取时返回None
        """
        # 辅助函数：检查坐标值是否有效（非None且为数字）
        def _is_valid_coord(val):
            return val is not None and isinstance(val, (int, float))

        # way类型有geometry字段（坐标点列表）
        geometry = elem.get("geometry", [])
        if geometry:
            # 过滤掉lat/lon为None或非数字的点
            coords = [
                [pt["lat"], pt["lon"]]
                for pt in geometry
                if "lat" in pt and "lon" in pt
                and _is_valid_coord(pt["lat"]) and _is_valid_coord(pt["lon"])
            ]
            if coords:
                if layer_type == "marker" and len(coords) == 1:
                    return coords[0]
                return coords

        # node类型直接有lat/lon字段，检查值有效性
        lat = elem.get("lat")
        lon = elem.get("lon")
        if _is_valid_coord(lat) and _is_valid_coord(lon):
            return [lat, lon]

        return None

    def _get_default_style(self, key: str) -> dict:
        """获取图层默认样式

        从MAP_STYLES中获取对应类型的样式配置。
        highway类型有子类型配置，取默认样式。

        Args:
            key: 要素类型或图层类型

        Returns:
            样式字典
        """
        style_config = MAP_STYLES.get(key)

        if style_config is None:
            # 未知类型使用通用默认样式
            return {"color": "#3388ff", "weight": 2, "opacity": 0.8}

        # highway类型的样式是列表结构（含子类型）
        if isinstance(style_config, list):
            for config in style_config:
                default_style = config.get("default")
                if default_style:
                    return dict(default_style)
            # 回退到列表第一个配置
            if style_config:
                return dict(style_config[0].get("default", {"color": "#999999", "weight": 2}))

        # 普通类型直接返回样式字典的副本
        if isinstance(style_config, dict):
            return dict(style_config)

        return {"color": "#3388ff", "weight": 2, "opacity": 0.8}
