# -*- coding: utf-8 -*-
"""四类武汉地图 Cartographic Profile

《CartoAgent 武汉四类专题地图数据规范》：同一批原始数据不应以同样方式
出现在四张地图里。每个 Profile 定义：
  - required/optional/forbidden 图层
  - 尺度约束矩阵（1:1M / 1:250K / 1:100K / 1:25K 各要素类别显隐）
  - 主题重要性（★ 级）
  - 旅游 POI 分级（P0-P3）与交通桥梁提取规则
"""
from typing import Any, Dict, List


# 尺度档位：与前端 LOD zoom 对应（z<9 概览 / 9-11 市域 / 12-13 城区 / >=14 详图）
SCALE_LEVELS: Dict[str, Dict[str, Any]] = {
    "1_1M":   {"name": "1:1,000,000", "zoom": "<9"},
    "1_250K": {"name": "1:250,000",   "zoom": "9-11"},
    "1_100K": {"name": "1:100,000",   "zoom": "12-13"},
    "1_25K":  {"name": "1:25,000",    "zoom": ">=14"},
}

# 要素类别 → 各尺度显示状态（show / partial / hide）
SCALE_MATRIX: Dict[str, Dict[str, str]] = {
    # 行政
    "admin_boundary":   {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "district_boundary": {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "street_boundary":  {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    "district_name":    {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "street_name":      {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    # 交通
    "motorway":         {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "trunk_road":       {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "primary_road":     {"1_1M": "hide", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "secondary_road":   {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    "minor_road":       {"1_1M": "hide", "1_250K": "hide", "1_100K": "partial", "1_25K": "show"},
    "railway":          {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "metro":            {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "bridge":           {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "transit_station":  {"1_1M": "partial", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    # 水系 / 自然
    "major_water":      {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "minor_water":      {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    # 旅游
    "core_poi":         {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "normal_poi":       {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    "service_poi":      {"1_1M": "hide", "1_250K": "hide", "1_100K": "partial", "1_25K": "show"},
    # 地势
    "dem_tint":         {"1_1M": "show", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "contour_major":    {"1_1M": "partial", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
    "contour_minor":    {"1_1M": "hide", "1_250K": "partial", "1_100K": "show", "1_25K": "show"},
    "peak":             {"1_1M": "partial", "1_250K": "show", "1_100K": "show", "1_25K": "show"},
}


def scale_for_zoom(zoom: int) -> str:
    """zoom → 尺度档位"""
    if zoom is None:
        return "1_250K"
    if zoom < 9:
        return "1_1M"
    if zoom <= 11:
        return "1_250K"
    if zoom <= 13:
        return "1_100K"
    return "1_25K"


def scale_state(category: str, zoom: int) -> str:
    """要素类别在指定缩放下的显示状态"""
    level = scale_for_zoom(zoom)
    return SCALE_MATRIX.get(category, {}).get(level, "show")


# ============ partial 尺度取舍（C8） ============
# 类别 → 各尺度 partial 时"按 importance 取前 K"（K 越大显示越多）
PARTIAL_TOP_K: Dict[str, Dict[str, int]] = {
    "street_boundary": {"1_250K": 8},
    "street_name": {"1_250K": 8},
    "secondary_road": {"1_1M": 6},
    "minor_road": {"1_100K": 12},
    "minor_water": {"1_250K": 10},
    "normal_poi": {"1_250K": 10},
    "service_poi": {"1_100K": 12},
    "contour_major": {"1_1M": 6},
    "contour_minor": {"1_250K": 10},
    "peak": {"1_1M": 5},
    "transit_station": {"1_1M": 6},
}


def partial_top_k(category: str, zoom: int, default: int = 8) -> int:
    """partial 状态下的"取前 K 重要要素"参数（C8）。"""
    level = scale_for_zoom(zoom)
    return PARTIAL_TOP_K.get(category, {}).get(level, default)


def resolve_scale_behavior(category: str, zoom: int):
    """返回要素在某尺度的显示行为：
    "show" / "hide" / ("partial", top_k)，供综合层统一取舍。
    """
    state = scale_state(category, zoom)
    if state == "show":
        return "show"
    if state == "hide":
        return "hide"
    return ("partial", partial_top_k(category, zoom))


# ============ 旅游 POI 分级（P0-P3） ============
# 图层名/类别关键字 → (等级, importance 权重, 说明)
TOURISM_POI_LEVELS: Dict[str, tuple] = {
    "核心景点": ("P0", 1.0, "国家级/城市级核心景区与地标"),
    "文化设施": ("P1", 0.9, "博物馆/文化场馆/纪念馆"),
    "博物馆": ("P1", 0.9, "博物馆"),
    "历史遗迹": ("P1", 0.85, "历史建筑/遗迹/纪念碑"),
    "自然景观": ("P2", 0.8, "自然景区/湖山"),
    "宗教场所": ("P2", 0.7, "宗教文化场所"),
    "公园绿地": ("P2", 0.5, "公园/绿地（普通）"),
    "休闲娱乐": ("P2", 0.6, "商圈/文娱/主题乐园"),
    "旅游服务": ("P3", 0.3, "游客中心/酒店/停车/卫生间"),
    "酒店": ("P3", 0.3, "酒店/宾馆"),
    "服务设施": ("P3", 0.25, "服务设施"),
}

# 图层名 → 类别（用于尺度矩阵与主题重要性）
LAYER_CATEGORY: Dict[str, str] = {
    # 行政
    "武汉市域边界": "admin_boundary", "湖北周边城市边界": "admin_boundary",
    "区县界": "district_boundary", "乡镇边界": "street_boundary",
    "区县名称标注": "district_name", "乡镇名称标注": "street_name", "市级名称标注": "district_name",
    # 交通
    "道路-高速公路主线": "motorway", "道路-城市干线主干道": "trunk_road",
    "道路-城市主干道": "primary_road", "道路-城市次干道": "secondary_road",
    "道路-三级道路（次要道路）": "minor_road", "道路-居民区街区道路": "minor_road",
    "轨道交通线路": "metro", "轨道交通站点": "transit_station", "铁路": "railway",
    "主要桥梁": "bridge",
    # 水系
    "主要河流": "major_water", "长江": "major_water", "汉江": "major_water",
    "河流中心线（主要）": "major_water", "支流溪流": "minor_water",
    "河流中心线（支流）": "minor_water", "湖泊": "major_water",
    # 旅游
    "重点地标": "core_poi", "地标名称": "core_poi",
    # 地势
    "等高线（计曲线）": "contour_major", "等高线（首曲线）": "contour_minor",
    "山峰": "peak", "山峰注记": "peak", "陆地底图": "dem_tint",
}


class CartographicProfile:
    """单类地图的制图约束"""

    def __init__(
        self,
        profile_id: str,
        name: str,
        purpose: str,
        required: List[str],
        optional: List[str],
        forbidden: List[str],
        theme_importance: Dict[str, int],
    ):
        self.id = profile_id
        self.name = name
        self.purpose = purpose
        self.required = required
        self.optional = optional
        self.forbidden = forbidden
        self.theme_importance = theme_importance

    def layer_forbidden(self, layer_name: str) -> bool:
        """图层是否被该 Profile 禁止"""
        return any(p in layer_name for p in self.forbidden)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "purpose": self.purpose,
            "required_layers": self.required,
            "optional_layers": self.optional,
            "forbidden_layers": self.forbidden,
            "theme_importance": self.theme_importance,
            "scale_rules": SCALE_MATRIX,
        }


# ============ 四套 Profile ============

PROFILES: Dict[str, CartographicProfile] = {
    "administrative": CartographicProfile(
        profile_id="administrative",
        name="武汉行政区划图",
        purpose="让用户快速识别武汉行政空间结构、区与区关系及主要地理背景",
        required=["区县政区", "武汉市域边界", "区县界", "区县名称标注"],
        optional=["市级名称标注", "区县行政中心", "主要河流", "高速公路", "主干道", "重点地名"],
        forbidden=["支路", "三级道路", "居民区街区", "银行", "餐厅", "快餐", "ATM", "公交站",
                    "轨道交通站点", "学校", "医院", "商圈", "酒店", "叠加结果", "湖泊点符号"],
        theme_importance={"admin_boundary": 5, "district_boundary": 5, "street_boundary": 3,
                          "district_name": 5, "major_water": 3, "motorway": 2, "trunk_road": 2,
                          "minor_road": 0},
    ),
    "traffic": CartographicProfile(
        profile_id="traffic",
        name="武汉综合交通图",
        purpose="交通网络专题：路网等级、轨道/铁路/桥梁关系正确、跨江交通突出",
        required=["道路", "轨道交通线路", "主要桥梁", "长江"],
        optional=["轨道交通站点", "铁路", "公交站", "交通枢纽", "区县界", "主要湖泊"],
        forbidden=["湖泊点符号", "银行", "餐厅", "快餐", "ATM", "超市", "便利店",
                    "学校", "医院", "警察局", "叠加结果"],
        theme_importance={"motorway": 5, "trunk_road": 4, "primary_road": 4,
                          "secondary_road": 3, "minor_road": 1, "railway": 5, "metro": 5,
                          "bridge": 5, "major_water": 4, "transit_station": 4},
    ),
    "tourism": CartographicProfile(
        profile_id="tourism",
        name="武汉旅游图",
        purpose="回答'武汉哪里值得去、怎么组织景点'：景点有等级、区域有结构、POI 不过载",
        required=["核心景点", "博物馆", "历史遗迹", "自然景观"],
        optional=["公园绿地", "宗教场所", "休闲娱乐", "旅游服务", "主要河流", "轨道交通"],
        forbidden=["道路-居民区街区道路", "三级道路", "加油站", "ATM", "银行", "超市",
                    "叠加结果", "湖泊点符号"],
        theme_importance={"core_poi": 5, "normal_poi": 3, "service_poi": 1,
                          "major_water": 4, "metro": 3},
    ),
    "terrain": CartographicProfile(
        profile_id="terrain",
        name="武汉地势图",
        purpose="连续地形表面：DEM 可靠、山水关系正确、高程连续、地形不过度夸张",
        required=["等高线", "陆地底图", "水系"],
        optional=["山峰", "山峰注记", "区县界", "高速公路"],
        forbidden=["银行", "餐厅", "快餐", "ATM", "超市", "便利店", "学校", "医院",
                    "公交站", "轨道交通站点", "叠加结果"],
        theme_importance={"dem_tint": 5, "contour_major": 5, "contour_minor": 3,
                          "major_water": 5, "peak": 4},
    ),
}


def get_profile(map_type: str) -> CartographicProfile:
    return PROFILES.get(map_type, CartographicProfile(
        profile_id=map_type, name=map_type, purpose="通用地图",
        required=[], optional=[], forbidden=[], theme_importance={},
    ))


def get_tourism_level(layer_name: str) -> tuple:
    """旅游图层名 → (P0-P3, importance, 说明)"""
    for key, val in TOURISM_POI_LEVELS.items():
        if key in layer_name:
            return val
    return ("P2", 0.6, "一般旅游要素")


def is_major_bridge(name: str) -> bool:
    """是否为武汉主要跨江/跨河桥梁（名称含'大桥'或'桥'且非道路名）"""
    if not name:
        return False
    # 排除道路名（以路/街/大道/巷结尾）
    if name.endswith(("路", "街", "大道", "巷", "大道辅路")):
        return False
    if "大桥" in name:
        return True
    # 著名桥梁名单
    KNOWN = ("武汉长江大桥", "长江二桥", "二七长江大桥", "白沙洲大桥", "杨泗港大桥",
             "天兴洲大桥", "军山大桥", "阳逻大桥", "青山大桥", "古田桥", "月湖桥",
             "晴川桥", "江汉桥", "知音桥", "长丰桥", "汉江湾桥")
    return any(k in name for k in KNOWN)
