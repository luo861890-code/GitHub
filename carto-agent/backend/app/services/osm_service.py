"""OSM数据获取服务 - 通过Overpass API获取OpenStreetMap地理要素数据

支持多服务器轮询重试机制，确保在服务器不可用时自动切换。
使用OVERPASS_QUERY_MAP构建查询语句，按要素类型分组返回结果。
"""
from app.utils.logger import get_logger
logger = get_logger(__name__)
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
import shutil
import subprocess
import tempfile
import sys

# Windows下不弹出cmd窗口
CREATE_NO_WINDOW = 0x08000000 if sys.platform == 'win32' else 0

import re

import requests
from typing import List, Dict, Any, Optional

from app.core.config import settings
from app.core.constants import CITY_BBOX, OVERPASS_QUERY_MAP


class OSMService:
    """OSM数据获取服务

    通过Overpass API获取OpenStreetMap地理要素（道路、铁路、水系、POI等）。
    支持多服务器轮询、自动重试、按区域和要素类型查询。
    """

    # 缓存最大条目数
    _CACHE_MAX_SIZE: int = 20
    # 缓存TTL（秒）
    _CACHE_TTL: float = 1800.0
    # 磁盘缓存（跨重启持久，制图提速）
    _DISK_CACHE_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "runtime", "osm_cache.json",
    )
    _DISK_CACHE_TTL: float = 86400.0   # 24小时

    def __init__(self):
        """从配置获取Overpass服务器列表"""
        self.servers: List[str] = settings.overpass_server_list
        # 内存缓存：使用 OrderedDict 实现 LRU，{ (region, types): (timestamp, data) }
        self._cache: OrderedDict[tuple, tuple] = OrderedDict()
        # 复用 HTTP 连接池，减少反复建连的开销
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": "CartoAgent/1.0 (Map Cartography Agent)",
            "Accept": "application/json",
        })
        # 绕过本机失效代理（HTTP(S)_PROXY=127.0.0.1:9），requests 兜底时也直连
        self._session.trust_env = False
        self._probe_cache = {"ts": 0.0, "ok": True}
        self._disk_cache: Dict[tuple, dict] = {}
        # 服务器健康度：最近成功时间 / 连续失败次数（用于把稳定镜像排到前面）
        self._server_health: Dict[str, float] = {}
        self._server_failures: Dict[str, int] = {}
        try:
            if os.path.exists(self._DISK_CACHE_PATH):
                with open(self._DISK_CACHE_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                for k, v in raw.items():
                    parts = k.split("||")
                    if len(parts) == 2:
                        self._disk_cache[(parts[0], parts[1])] = v
                logger.info(f"[OSMService] 磁盘缓存加载: {len(self._disk_cache)} 条")
        except Exception as e:
            logger.info(f"[OSMService] 磁盘缓存加载失败: {e}")
        logger.info(f"[OSMService] 初始化完成，可用服务器: {len(self.servers)}个")

    def _save_disk_cache(self):
        """将内存缓存落盘（跨重启复用，避免每次制图重复抓取 OSM）"""
        try:
            os.makedirs(os.path.dirname(self._DISK_CACHE_PATH), exist_ok=True)
            raw = {}
            for (region, typ), data in self._disk_cache.items():
                raw[region + "||" + typ] = data
            with open(self._DISK_CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False)
        except Exception as e:
            logger.info(f"[OSMService] 磁盘缓存保存失败: {e}")

    def _probe_ok(self, ttl: float = 60.0) -> bool:
        """快速探测 Overpass 是否可达（任一服务器返回 HTTP 状态即视为可用）。

        全部镜像不可达（断网/被屏蔽）时直接跳过 OSM 抓取，
        避免每次制图都在不可达镜像上空等数分钟（本地数据可兜底）。
        """
        now = time.time()
        if now - self._probe_cache["ts"] < ttl:
            return self._probe_cache["ok"]
        ok = False
        for server in self._ordered_servers()[:4]:
            try:
                r = subprocess.run(
                    ["curl.exe", "-s", "-o", os.devnull, "-w", "%{http_code}",
                     "--connect-timeout", "4", "--max-time", "6", server],
                    capture_output=True, text=True, timeout=10,
                    creationflags=CREATE_NO_WINDOW,
                )
                code = (r.stdout or "").strip()
                if code and code != "000":
                    ok = True
                    # 探测可达的服务器立即标记为健康，抓取时优先使用
                    self._server_health[server] = now
                    self._server_failures[server] = 0
                    break
            except Exception:
                continue
        self._probe_cache = {"ts": now, "ok": ok}
        logger.info(f"[OSMService] 连通性探测: {'可达' if ok else '全部镜像不可达，跳过OSM抓取'}")
        return ok

    def _ordered_servers(self, servers: Optional[List[str]] = None) -> List[str]:
        """按健康度排序服务器：最近成功过的排最前，失败次数少的优先"""
        servers = servers or self.servers
        now = time.time()

        def key(s: str) -> tuple:
            recent_ok = self._server_health.get(s, 0)
            # 5 分钟内成功过的服务器权重最高
            ok_bucket = 0 if now - recent_ok < 300 else 1
            return (ok_bucket, self._server_failures.get(s, 0), servers.index(s))

        return sorted(servers, key=key)

    def fetch_elements(
        self,
        bbox: Dict[str, float],
        element_types: List[str],
        max_retries: int = 1,
    ) -> Dict[str, List[dict]]:
        """从Overpass API获取OSM要素，支持多服务器轮询重试

        按要素类型分块并行请求：单个类型失败不影响其它类型，
        避免巨型组合请求被Overpass限流/超时而整体失败。

        Args:
            bbox: 边界框，格式 {min_lat, min_lon, max_lat, max_lon}
            element_types: 要素类型列表，如 ["highway", "railway"]
            max_retries: 最大重试次数（每轮遍历所有服务器）

        Returns:
            按类型分组的元素字典，key为要素类型，value为元素列表。
        """
        servers = self.servers if self.servers else [
            "https://overpass-api.de/api/interpreter",
            "https://overpass.kumi.systems/api/interpreter",
            "https://z.overpass-api.de/api/interpreter",
            "https://lz4.overpass-api.de/api/interpreter",
        ]

        # 为每个类型构建独立查询；重型线/面要素按子格网拆分，避免公共 Overpass 超时
        SPLIT_TYPES = {"highway", "highway_major", "railway", "building"}
        tasks = []
        for typ in element_types:
            query_part = OVERPASS_QUERY_MAP.get(typ)
            if not query_part:
                logger.info(f"[OSMService] 未知要素类型: {typ}，已跳过")
                continue
            cells = (
                self._split_bbox(bbox, 5, 5) if typ in ("highway_major", "highway")  # 道路体量大，细分网格防超时
                else self._split_bbox(bbox, 2, 2) if typ in SPLIT_TYPES
                else [bbox]
            )
            for cell in cells:
                sub_queries = []
                for sub_query in query_part.split(";"):
                    sub_query = sub_query.strip()
                    if sub_query:
                        sub_queries.append(
                            f"{sub_query}"
                            f"({cell['min_lat']},{cell['min_lon']},"
                            f"{cell['max_lat']},{cell['max_lon']});"
                            f"out geom;"
                        )
                tasks.append((typ, "[out:json][timeout:60];" + "".join(sub_queries)))

        if not tasks:
            logger.info("[OSMService] 没有有效的查询语句")
            return {}

        # 总抓取时限（秒）：超时后停止等待，用已获取部分 + 本地数据兜底
        self._fetch_deadline = time.time() + 600
        # 并行请求各类型（并发 2-4；子格网拆分后单请求体积小、速度快）
        results: Dict[str, List[dict]] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
            # 全量服务器参与轮询（按健康度排序），避免可达镜像排位靠后从未被尝试；
            # _fetch_type 内部会把失败服务器挪到队尾，确保各镜像都被覆盖。
            active_servers = self._ordered_servers(servers)
            futures = {
                executor.submit(self._fetch_type, typ, query, active_servers, max_retries): typ
                for typ, query in tasks
            }
            for future in as_completed(futures):
                typ = futures[future]
                try:
                    elems = future.result()
                    if elems:
                        results.setdefault(typ, []).extend(elems)
                except Exception as e:
                    logger.info(f"[OSMService] 类型[{typ}]获取失败: {e}")

        # 按标签分组汇总
        elements_by_type: Dict[str, List[dict]] = {}
        for typ, elems in results.items():
            base_tag = typ.split("~")[0]
            if base_tag in ("highway_major", "highway_minor"):
                tag_key = "highway"
            elif base_tag in ("waterway_major", "waterway_minor"):
                tag_key = "waterway"
            elif base_tag in ("place_city", "place_suburb"):
                tag_key = "place"
            else:
                tag_key = base_tag
            for elem in elems:
                tags = elem.get("tags", {})
                if not tags:
                    continue
                if tag_key in tags:
                    elements_by_type.setdefault(base_tag, []).append(elem)

        # 地理数据预处理：坐标校验、要素去重、名称清洗
        elements_by_type = self._preprocess(elements_by_type)
        total = sum(len(v) for v in elements_by_type.values())
        logger.info(f"[OSMService] 汇总完成: {total}个要素，{len(elements_by_type)}类")
        return elements_by_type

    @staticmethod
    def _valid_coord(lat, lon) -> bool:
        """坐标有效性校验"""
        if lat is None or lon is None:
            return False
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return False
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0

    @staticmethod
    def _split_bbox(bbox: Dict[str, float], nx: int = 2, ny: int = 2) -> List[Dict[str, float]]:
        """将大范围 bbox 拆分为子格网，避免重型查询在公共 Overpass 上超时"""
        min_lat, max_lat = bbox["min_lat"], bbox["max_lat"]
        min_lon, max_lon = bbox["min_lon"], bbox["max_lon"]
        lat_step = (max_lat - min_lat) / ny
        lon_step = (max_lon - min_lon) / nx
        cells = []
        for iy in range(ny):
            for ix in range(nx):
                cells.append({
                    "min_lat": min_lat + iy * lat_step,
                    "max_lat": min_lat + (iy + 1) * lat_step,
                    "min_lon": min_lon + ix * lon_step,
                    "max_lon": min_lon + (ix + 1) * lon_step,
                })
        return cells

    def _preprocess(self, elements_by_type: Dict[str, List[dict]], bbox: dict = None) -> Dict[str, List[dict]]:
        """地理数据预处理：过滤非法坐标/极小几何、清洗名称、去除重复要素

        bbox: 城市边界框（存在时二次裁剪越界点）
        """
        cleaned: Dict[str, List[dict]] = {}
        for base_tag, elems in elements_by_type.items():
            seen = set()
            out = []
            for elem in elems:
                tags = elem.get("tags", {}) or {}
                # node坐标校验
                if elem.get("type") == "node":
                    if not self._valid_coord(elem.get("lat"), elem.get("lon")):
                        continue
                # way/relation 几何校验：过滤非法坐标点，丢弃过短几何
                geom = elem.get("geometry") or []
                if geom:
                    valid = [p for p in geom
                             if isinstance(p, dict) and self._valid_coord(p.get("lat"), p.get("lon"))]
                    if len(valid) < 2:
                        continue
                    elem = dict(elem)
                    elem["geometry"] = valid
                    geom = valid
                # 名称清洗：去空白、截断、剔除占位名
                name = (tags.get("name") or "").strip()
                if name:
                    name = re.sub(r"\s+", " ", name)
                    if len(name) > 60:
                        name = name[:60]
                    if name.lower() in ("unnamed", "未命名", "unknown", "none"):
                        name = ""
                    tags = dict(tags)
                    tags["name"] = name
                    elem = dict(elem)
                    elem["tags"] = tags
                # 无名POI节点（清洗后仍无名）丢弃，避免地图上出现无意义标记
                if elem.get("type") == "node" and not name:
                    continue
                # 去重：类型 + 首尾坐标 + 名称
                if geom:
                    key = (base_tag, str(geom[0]), str(geom[-1]), name)
                else:
                    key = (base_tag, str(elem.get("lat")), str(elem.get("lon")), name)
                if key in seen:
                    continue
                seen.add(key)
                out.append(elem)
            if out:
                cleaned[base_tag] = out
        return cleaned

    def _fetch_type(
        self,
        typ: str,
        query: str,
        servers: List[str],
        max_retries: int,
    ) -> List[dict]:
        """获取单个类型的OSM要素，多服务器轮询重试"""
        for attempt in range(max_retries):
            for server in servers:
                # 总抓取时限：超过后放弃该类型（本地数据兜底，避免长时间空等）
                if getattr(self, "_fetch_deadline", 0) and time.time() > self._fetch_deadline:
                    logger.info(f"[OSMService] 类型[{typ}] 超过抓取时限，放弃")
                    return []
                try:
                    logger.info(f"[OSMService] 尝试从 {server} 获取[{typ}] (轮次 {attempt + 1}/{max_retries})")
                    data = self._post_overpass(server, query, timeout=60)
                    elems = data.get("elements", [])
                    logger.info(f"[OSMService] 类型[{typ}] 成功获取 {len(elems)} 个要素")
                    self._server_health[server] = time.time()
                    self._server_failures[server] = 0
                    return elems
                except Exception as e:
                    self._server_failures[server] = self._server_failures.get(server, 0) + 1
                    logger.info(f"[OSMService] 类型[{typ}] 请求失败 ({server}): {e}")
                    # 失败服务器挪到队尾，下一轮优先尝试其他镜像
                    if len(servers) > 1:
                        servers = [s for s in servers if s != server] + [server]
                finally:
                    time.sleep(0.5)
            if attempt < max_retries - 1:
                logger.info(f"[OSMService] 类型[{typ}] 所有服务器失败，等待后重试...")
                time.sleep(1)
        return []

    def _post_overpass(self, server: str, query: str, timeout: int = 60) -> dict:
        """向 Overpass 发送 POST 查询，优先用 curl.exe 直连（绕过坏代理）。

        curl 不可用时回退 requests（已 trust_env=False 直连）。
        """
        curl_path = shutil.which("curl.exe") or (r"C:\Windows\System32\curl.exe"
                                                 if os.path.exists(r"C:\Windows\System32\curl.exe") else None)
        if curl_path:
            fd, qpath = tempfile.mkstemp(suffix=".ql", prefix="overpass_")
            os.close(fd)
            outpath = qpath + ".json"
            try:
                with open(qpath, "w", encoding="utf-8") as f:
                    f.write(query)
                r = subprocess.run(
                    [curl_path, "-s", "--max-time", str(timeout),
                     "--connect-timeout", "10",
                     "--data-binary", "@" + qpath, "-o", outpath, server],
                    capture_output=True, timeout=timeout + 20,
                    creationflags=CREATE_NO_WINDOW,
                )
                if r.returncode == 0 and os.path.exists(outpath) and os.path.getsize(outpath) > 0:
                    with open(outpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "error" not in data:
                        return data
                    raise RuntimeError(f"Overpass 返回错误: {data.get('remark', data)}")
                raise RuntimeError(f"curl 退出码 {r.returncode}")
            finally:
                for p in (qpath, outpath):
                    try:
                        if os.path.exists(p):
                            os.remove(p)
                    except Exception:
                        pass
        # 兜底：requests 直连
        resp = self._session.post(server, data={"data": query}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def fetch_by_region(
        self,
        region: str,
        element_types: List[str],
    ) -> Dict[str, List[dict]]:
        """按区域名称获取OSM要素

        从CITY_BBOX获取区域的边界框后调用fetch_elements，
        并进行越界裁剪与数据预处理。

        Args:
            region: 区域名称（如"武汉市"、"北京市"）
            element_types: 要素类型列表

        Returns:
            按类型分组的元素字典
        """
        # 快速连通性探测：全部镜像不可达时直接跳过，避免数分钟空等
        if not self._probe_ok():
            return {}
        bbox = CITY_BBOX.get(region)
        if not bbox:
            logger.info(
                f"[OSMService] 未知区域: {region}，"
                f"支持的城市: {list(CITY_BBOX.keys())}"
            )
            return {}

        # 对bbox做道路缓冲区扩展（避免边界裁剪导致道路截断）
        _buffer = 0.03  # 约3km缓冲区
        bbox_buffered = {
            "min_lat": bbox["min_lat"] - _buffer,
            "min_lon": bbox["min_lon"] - _buffer,
            "max_lat": bbox["max_lat"] + _buffer,
            "max_lon": bbox["max_lon"] + _buffer,
            "center_lat": bbox["center_lat"],
            "center_lon": bbox["center_lon"],
        }

        # 缓存改为“按单类型”存储：任一类型抓取成功后，可在任意组合中复用
        now = time.time()
        requested = list(dict.fromkeys(element_types))
        result: Dict[str, List[dict]] = {}
        missing: List[str] = []
        for typ in requested:
            hit = None
            mem = self._cache.get((region, typ))
            # 空结果只短暂缓存（5 分钟），避免瞬时失败长期污染缓存
            mem_ttl = 300 if (mem and not mem[1]) else self._CACHE_TTL
            if mem and now - mem[0] < mem_ttl:
                self._cache.move_to_end((region, typ))
                hit = mem[1]
            else:
                disk = self._disk_cache.get((region, typ))
                if disk and now - disk.get("ts", 0) < self._DISK_CACHE_TTL and disk.get("data"):
                    hit = disk["data"]
                    self._cache[(region, typ)] = (now, hit)
            if hit is not None:
                result[typ] = hit
            else:
                missing.append(typ)

        if missing:
            logger.info(f"[OSMService] 缓存未命中类型: {missing}，开始抓取")
            fresh = self.fetch_elements(bbox_buffered, missing, max_retries=3)
            if fresh:
                fresh = self._crop_to_bbox(fresh, bbox)
                fresh = self._preprocess(fresh, bbox)
            for typ, elems in (fresh or {}).items():
                if elems:
                    result[typ] = elems
                    self._cache[(region, typ)] = (now, elems)
                    self._cache.move_to_end((region, typ))
                    self._disk_cache[(region, typ)] = {"ts": now, "data": elems}
            # 缺失且本次仍未获取到的类型：写入空缓存，避免每次重复抓取
            for typ in missing:
                if typ not in result:
                    result[typ] = []
                    self._cache[(region, typ)] = (now, [])
                    # 空结果不落盘（下次进程重启后会重新尝试）
            self._save_disk_cache()
            while len(self._cache) > self._CACHE_MAX_SIZE:
                self._cache.popitem(last=False)
            return result

        logger.info(f"[OSMService] 命中缓存: {region} {len(result)}类要素")
        return result

    def _crop_to_bbox(self, elements_by_type: Dict[str, List[dict]], bbox: dict) -> Dict[str, List[dict]]:
        """按城市边界框裁剪要素：剔除超出范围的顶点，保留有效要素

        防止越界点造成边界毛刺、碎线段与面积虚高。
        """
        buf = 0.02  # 缓冲，避免误删边界要素
        min_lat, min_lon = bbox["min_lat"] - buf, bbox["min_lon"] - buf
        max_lat, max_lon = bbox["max_lat"] + buf, bbox["max_lon"] + buf
        cropped: Dict[str, List[dict]] = {}
        for base_tag, elems in elements_by_type.items():
            out = []
            for elem in elems:
                if elem.get("type") == "node":
                    lat, lon = elem.get("lat"), elem.get("lon")
                    if lat is None or lon is None:
                        continue
                    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                        out.append(elem)
                    continue
                geom = elem.get("geometry") or []
                if not geom:
                    continue
                valid = [pt for pt in geom
                         if isinstance(pt, dict) and min_lat <= pt.get("lat", 999) <= max_lat
                         and min_lon <= pt.get("lon", 999) <= max_lon]
                if len(valid) >= 2:
                    elem = dict(elem)
                    elem["geometry"] = valid
                    out.append(elem)
            if out:
                cropped[base_tag] = out
        return cropped

    def get_region_center(self, region: str) -> Optional[List[float]]:
        """获取区域中心坐标

        Args:
            region: 区域名称

        Returns:
            [lat, lng] 中心坐标，未知区域返回None
        """
        bbox = CITY_BBOX.get(region)
        if not bbox:
            return None
        return [bbox["center_lat"], bbox["center_lon"]]
