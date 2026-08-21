# -*- coding: utf-8 -*-
"""核心地理数据元数据定义与 manifest 生成（真实、不伪造；未知用 null + reason）"""
from typing import Any, Dict, List


# 统一 metadata schema（字段含义见 manifest 注释）
METADATA_SCHEMA: Dict[str, str] = {
    "dataset_id": "string, 唯一标识",
    "name": "string, 数据集名",
    "geometry_type": "string, Point/LineString/Polygon/Multi*",
    "feature_count": "integer, 要素数",
    "crs": "string, 当前 CRS（EPSG:4326）",
    "source": "string, 数据来源",
    "source_url": "string|null, 来源 URL（未知则 null）",
    "source_type": "string, 来源类型（official/professional/osm/third-party/generated）",
    "acquisition_date": "string|null, 获取/发布日期（未知则 null）",
    "last_verified": "string|null, 最后核验日期",
    "processing_history": "array<string>, 处理历史（下载/清洗/合并/简化/CRS转换/过滤）",
    "original_crs": "string, 原始 CRS",
    "current_crs": "string, 当前 CRS",
    "accuracy": "object|null, {horizontal_m, vertical_m, note}（未知 null）",
    "license": "string|null, 许可",
    "version": "string, 数据版本",
    "quality_status": "string, unknown/cleaned/verified",
}


def _entry(
    dataset_id: str,
    name: str,
    geometry_type: str,
    source: str,
    source_type: str,
    license: str,
    processing: List[str],
    source_url: Any = None,
    accuracy: Any = None,
    quality_status: str = "cleaned",
    acquisition_date: Any = None,
    extra: Dict[str, Any] = None,
) -> Dict[str, Any]:
    """构造真实元数据条目；未知字段为 None（不伪造）"""
    entry: Dict[str, Any] = {
        "dataset_id": dataset_id,
        "name": name,
        "geometry_type": geometry_type,
        "feature_count": 0,  # 由 manifest 生成脚本回填
        "crs": "EPSG:4326",
        "source": source,
        "source_url": source_url,
        "source_type": source_type,
        "acquisition_date": acquisition_date,
        "last_verified": None,
        "processing_history": processing,
        "original_crs": "EPSG:4326",
        "current_crs": "EPSG:4326",
        "accuracy": accuracy,
        "license": license,
        "version": "1.0",
        "quality_status": quality_status,
    }
    if extra:
        entry.update(extra)
    return entry


# 核心数据集清单（真实来源，未知日期/精度明确为 null）
DATASET_MANIFEST: List[Dict[str, Any]] = [
    _entry(
        "wuhan_roads", "武汉市道路网", "MultiLineString",
        "OpenStreetMap (Overpass API)", "osm", "ODbL",
        ["下载(Overpass)", "裁剪到武汉市域", "道路分级", "Douglas-Peucker 简化"],
        source_url="https://www.openstreetmap.org",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_water", "武汉市水系", "MultiPolygon/MultiLineString",
        "OpenStreetMap (Overpass API)", "osm", "ODbL",
        ["下载(Overpass)", "裁剪到武汉市域", "同名湖合并", "繁简归一", "面积过滤", "去除无名碎片"],
        source_url="https://www.openstreetmap.org",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_transit", "武汉市轨道交通", "MultiLineString/MultiPoint",
        "OpenStreetMap (Overpass API)", "osm", "ODbL",
        ["下载(Overpass)", "裁剪到武汉市域", "线路/站点分级"],
        source_url="https://www.openstreetmap.org",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_tourism", "武汉市旅游 POI", "MultiPoint",
        "OpenStreetMap (Overpass API)", "osm", "ODbL",
        ["下载(Overpass)", "类别归一", "裁剪到武汉市域"],
        source_url="https://www.openstreetmap.org",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_builtup", "武汉市居民地街区", "MultiPolygon",
        "OpenStreetMap (Overpass API)", "osm", "ODbL",
        ["下载(Overpass)", "裁剪到武汉市域", "街区形状概括"],
        source_url="https://www.openstreetmap.org",
        quality_status="cleaned",
    ),
    _entry(
        "hubei_cities", "湖北省地级市边界", "MultiPolygon",
        "DataV GeoAtlas（阿里云 DataV 可视化，基于民政部行政区划）", "third-party", None,
        ["下载(DataV GeoAtlas)", "坐标规整"],
        source_url="https://datav.aliyun.com/portal/school/atlas/area_selector",
        quality_status="cleaned",
    ),
    _entry(
        "hubei_province", "湖北省省界", "MultiPolygon",
        "DataV GeoAtlas（阿里云 DataV 可视化，基于民政部行政区划）", "third-party", None,
        ["下载(DataV GeoAtlas)", "坐标规整"],
        source_url="https://datav.aliyun.com/portal/school/atlas/area_selector",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_districts", "武汉市 13 区行政区划", "MultiPolygon",
        "DataV GeoAtlas（阿里云 DataV 可视化，基于民政部行政区划）", "third-party", None,
        ["下载(DataV GeoAtlas)", "坐标规整"],
        source_url="https://datav.aliyun.com/portal/school/atlas/area_selector",
        quality_status="cleaned",
    ),
    _entry(
        "wuhan_contours", "武汉市等高线（SRTM 派生）", "MultiLineString",
        "NASA SRTMGL1 30m DEM（派生）", "generated", "public domain",
        ["下载(SRTM .hgt)", "拼接", "空洞填充", "等高线生成", "遇水断开", "制图综合(舍谷/扩谷/鞍部保持)"],
        source_url="https://doi.org/10.5066/F7K072R7",
        accuracy={"resolution_m": 30, "horizontal_m": None, "vertical_m": None,
                  "note": "水平分辨率 30m（真实）；垂直精度未在本地核验，标注 None"},
        quality_status="cleaned",
        extra={"resolution_m": 30, "vertical_datum": None,
               "vertical_datum_reason": "SRTM 为 EGM96 大地水准面；本地未做转换核验，故不声明"},
    ),
    _entry(
        "srtm_dem", "武汉市 SRTM 30m DEM", "Raster(.hgt)",
        "NASA SRTMGL1", "generated", "public domain",
        ["下载(SRTM .hgt)"],
        source_url="https://doi.org/10.5066/F7K072R7",
        accuracy={"resolution_m": 30, "horizontal_m": None, "vertical_m": None,
                  "note": "水平分辨率 30m（真实）；垂直精度未本地核验"},
        quality_status="cleaned",
        extra={"resolution_m": 30, "vertical_datum": "EGM96（SRTM 官方声明）",
               "nodata": -32768},
    ),
]


def get_manifest() -> List[Dict[str, Any]]:
    return [dict(e) for e in DATASET_MANIFEST]


def manifest_by_id(dataset_id: str) -> Dict[str, Any]:
    for e in DATASET_MANIFEST:
        if e["dataset_id"] == dataset_id:
            return dict(e)
    return {}
