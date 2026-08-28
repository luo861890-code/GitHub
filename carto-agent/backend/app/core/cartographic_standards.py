# -*- coding: utf-8 -*-
"""《地图学制图规范》统一主表（Cartographic Standards）

依据中国国家基本比例尺地图图式（GB/T 20257 系列精神）与通用地图学原理，
将散落在各模块的优先级 / 颜色 / 符号 / 尺度规则收敛为**单一来源**，供制图生成、
综合、注记与验收统一引用。核心设计原则：

- 色系：水系=蓝、地貌/等高线=棕、植被=绿、道路=红/橙/黄、境界=黑/红/灰、居民地=灰。
- 分级：要素统一分为 0(最高)…7(最低) 八级，尺度 / 符号 / 注记 / 优先级全部由此派生。
- 点符号语义：圆=政区/居民点，三角=山峰，方形=交通枢纽/车站，星=核心地标/景区，
  十字/圆点=一般 POI；禁止 LLM 随机配色与随机形状。
- 注记：按要素等级定字号，按尺度设密度上限，水系/道路/等高线有显式避让矩阵。
"""
from typing import Any, Dict, List, Optional

# ============ 一、国标式色系（单一来源） ============
GB_COLORS: Dict[str, str] = {
    "water_fill": "#AED6F1",      # 水系面填充（浅蓝）
    "water_line": "#2E6FA3",      # 河流线（深蓝）
    "water_contour": "#1E90FF",   # 水系轮廓
    "relief_fill": "#EFE6D8",     # 地貌面/晕渲（浅棕）
    "contour_index": "#8B4513",   # 计曲线（深棕）
    "contour_intermediate": "#C89B6A",  # 首曲线（中棕）
    "peak": "#8B4513",            # 山峰（棕）
    "vegetation": "#7CB342",      # 植被（绿）
    "builtup": "#C8C8C8",         # 居民地/建筑（灰）
    "road_motorway": "#C0392B",   # 高速（红）
    "road_trunk": "#E67E22",      # 国道/干线（橙）
    "road_primary": "#F1C40F",    # 省道/主干道（黄）
    "road_secondary": "#F4D03F",  # 次干道（浅黄）
    "road_minor": "#D5D8DC",      # 支路（浅灰）
    "boundary_national": "#111111",  # 国界（黑）
    "boundary_city": "#D62728",   # 市界（红）
    "boundary_district": "#8A8A8A",  # 区县界（灰）
    "railway": "#555555",         # 铁路（深灰）
    "metro": "#0066CC",           # 地铁（蓝）
    "transport_hub": "#D97706",   # 交通枢纽（橙）
    "poi": "#B91C1C",             # 一般 POI（红）
    "core_landmark": "#E11D48",   # 核心地标（亮红）
    "annotation_water": "#2E6FA3",
    "annotation_transport": "#374151",
    "annotation_admin": "#1F2937",
    "annotation_peak": "#7A5230",
    "annotation_poi": "#B91C1C",
}

# ============ 二、要素等级（0=最高 … 7=最低） ============
L0, L1, L2, L3, L4, L5, L6, L7 = 0, 1, 2, 3, 4, 5, 6, 7

# 行政层级：市 > 区县 > 乡镇
ADMIN_LEVEL: Dict[str, int] = {
    "national_boundary": L0, "city_boundary": L1, "district_boundary": L2,
    "street_boundary": L3, "city_name": L0, "district_name": L2, "street_name": L4,
}

# ============ 三、点符号形状语义（B6） ============
# shape: circle / triangle / square / star / cross / dot
POINT_SHAPE: Dict[str, str] = {
    "city_center": "circle",      # 政区/中心
    "district_center": "circle",
    "peak": "triangle",           # 山峰 → 三角
    "transport_hub": "square",    # 车站/枢纽 → 方
    "airport": "square",
    "core_landmark": "star",      # 核心地标/5A 景区 → 星
    "attraction": "star",         # 景点
    "museum": "square",           # 文化场馆 → 方
    "hospital": "cross",          # 医疗 → 十字
    "school": "square",           # 学校 → 方
    "poi": "dot",                 # 一般 POI → 圆点
    "default": "dot",
}


def point_shape_for(category: str, name: str = "") -> str:
    """要素类别/名称 → 规范几何符号形状（禁止随机）。"""
    if "山峰" in (name or ""):
        return "triangle"
    return POINT_SHAPE.get(category, POINT_SHAPE["default"])


# ============ 四、要素主表（C7：收敛多套优先级/尺度/符号） ============
# key: 要素类别（对应 LAYER_CATEGORY）；value: 主表记录
#   level        统一等级（0-7）
#   geometry     point / line / polygon
#   symbol       符号 id（与 symbols/registry.py 对齐）
#   color_key    GB_COLORS 键
#   shape        点符号形状
#   scale_min    最小显示比例尺分母（更大分母=更小比例尺不显示）
#   min_len_m    线要素最小显示长度（实地米，短于则不显示）
#   label_min_km 注记阈值（面积 km² 或长度 km，达到才注记）
#   ann_priority 注记优先级（对应 label_spec P0-P3）
FEATURE_SPEC: Dict[str, Dict[str, Any]] = {
    # 行政
    "admin_boundary": {"level": L1, "geometry": "line", "symbol": "boundary.city",
                       "color_key": "boundary_city", "scale_min": 1000000,
                       "min_len_m": 0, "label_min_km": 0, "ann_priority": 100},
    "district_boundary": {"level": L2, "geometry": "line", "symbol": "boundary.district",
                          "color_key": "boundary_district", "scale_min": 1000000,
                          "min_len_m": 0, "label_min_km": 0, "ann_priority": 80},
    "street_boundary": {"level": L3, "geometry": "line", "symbol": "boundary.district",
                        "color_key": "boundary_district", "scale_min": 250000,
                        "min_len_m": 0, "label_min_km": 0, "ann_priority": 50},
    "district_name": {"level": L2, "geometry": "area", "symbol": None,
                      "color_key": "annotation_admin", "scale_min": 1000000,
                      "min_len_m": 0, "label_min_km": 0, "ann_priority": 80},
    "street_name": {"level": L4, "geometry": "area", "symbol": None,
                    "color_key": "annotation_admin", "scale_min": 250000,
                    "min_len_m": 0, "label_min_km": 0, "ann_priority": 50},
    # 交通
    "motorway": {"level": L0, "geometry": "line", "symbol": "road.motorway",
                 "color_key": "road_motorway", "scale_min": 1000000,
                 "min_len_m": 400, "label_min_km": 4, "ann_priority": 100},
    "trunk_road": {"level": L1, "geometry": "line", "symbol": "road.trunk",
                   "color_key": "road_trunk", "scale_min": 1000000,
                   "min_len_m": 400, "label_min_km": 3, "ann_priority": 80},
    "primary_road": {"level": L2, "geometry": "line", "symbol": "road.primary",
                     "color_key": "road_primary", "scale_min": 500000,
                     "min_len_m": 300, "label_min_km": 3, "ann_priority": 80},
    "secondary_road": {"level": L3, "geometry": "line", "symbol": "road.secondary",
                       "color_key": "road_secondary", "scale_min": 250000,
                       "min_len_m": 250, "label_min_km": 2, "ann_priority": 50},
    "minor_road": {"level": L4, "geometry": "line", "symbol": "road.minor",
                   "color_key": "road_minor", "scale_min": 100000,
                   "min_len_m": 200, "label_min_km": 1, "ann_priority": 20},
    "railway": {"level": L1, "geometry": "line", "symbol": "railway.main",
                "color_key": "railway", "scale_min": 1000000,
                "min_len_m": 500, "label_min_km": 5, "ann_priority": 80},
    "metro": {"level": L1, "geometry": "line", "symbol": "metro.line",
              "color_key": "metro", "scale_min": 1000000,
              "min_len_m": 500, "label_min_km": 3, "ann_priority": 80},
    "bridge": {"level": L1, "geometry": "line", "symbol": "bridge.major",
               "color_key": "road_motorway", "scale_min": 1000000,
               "min_len_m": 0, "label_min_km": 0, "ann_priority": 90},
    "transit_station": {"level": L2, "geometry": "point", "symbol": "hub.transport",
                        "color_key": "transport_hub", "shape": "square", "scale_min": 1000000,
                        "min_len_m": 0, "label_min_km": 0, "ann_priority": 80},
    # 水系
    "major_water": {"level": L1, "geometry": "polygon", "symbol": "water.lake",
                    "color_key": "water_fill", "scale_min": 1000000,
                    "min_len_m": 0, "label_min_km": 30, "ann_priority": 100},
    "minor_water": {"level": L3, "geometry": "line", "symbol": "water.river",
                    "color_key": "water_line", "scale_min": 100000,
                    "min_len_m": 300, "label_min_km": 1, "ann_priority": 50},
    "riverline": {"level": L2, "geometry": "line", "symbol": "water.river",
                  "color_key": "water_line", "scale_min": 250000,
                  "min_len_m": 300, "label_min_km": 2, "ann_priority": 80},
    # 旅游
    "core_poi": {"level": L1, "geometry": "point", "symbol": "poi.attraction",
                 "color_key": "core_landmark", "shape": "star", "scale_min": 500000,
                 "min_len_m": 0, "label_min_km": 0, "ann_priority": 100},
    "normal_poi": {"level": L3, "geometry": "point", "symbol": "poi.attraction",
                   "color_key": "poi", "shape": "dot", "scale_min": 100000,
                   "min_len_m": 0, "label_min_km": 0, "ann_priority": 50},
    "service_poi": {"level": L4, "geometry": "point", "symbol": "poi.attraction",
                    "color_key": "poi", "shape": "dot", "scale_min": 25000,
                    "min_len_m": 0, "label_min_km": 0, "ann_priority": 20},
    # 地势
    "dem_tint": {"level": L1, "geometry": "polygon", "symbol": None,
                 "color_key": "relief_fill", "scale_min": 1000000,
                 "min_len_m": 0, "label_min_km": 0, "ann_priority": 0},
    "contour_major": {"level": L2, "geometry": "line", "symbol": "terrain.contour",
                      "color_key": "contour_index", "scale_min": 250000,
                      "min_len_m": 0, "label_min_km": 0, "ann_priority": 0},
    "contour_minor": {"level": L4, "geometry": "line", "symbol": "terrain.contour",
                      "color_key": "contour_intermediate", "scale_min": 100000,
                      "min_len_m": 0, "label_min_km": 0, "ann_priority": 0},
    "peak": {"level": L2, "geometry": "point", "symbol": "terrain.peak",
             "color_key": "peak", "shape": "triangle", "scale_min": 250000,
             "min_len_m": 0, "label_min_km": 0, "ann_priority": 80},
}


def feature_spec(category: str) -> Optional[Dict[str, Any]]:
    return dict(FEATURE_SPEC.get(category) or {})


def feature_level(category: str) -> int:
    spec = FEATURE_SPEC.get(category)
    return spec["level"] if spec else L7


def feature_scale_min(category: str) -> int:
    spec = FEATURE_SPEC.get(category)
    return spec["scale_min"] if spec else 25000


def feature_min_display_len(category: str) -> int:
    """线要素最小显示长度（实地米）。"""
    spec = FEATURE_SPEC.get(category)
    return spec["min_len_m"] if spec else 0


def feature_label_threshold(category: str, geometry: str) -> float:
    """注记阈值：polygon→面积 km²，line/point→长度 km 或恒注记。"""
    spec = FEATURE_SPEC.get(category)
    return spec["label_min_km"] if spec else 0.0


def feature_color(category: str) -> str:
    spec = FEATURE_SPEC.get(category)
    return GB_COLORS.get(spec["color_key"], "#888888") if spec else "#888888"


def feature_shape(category: str) -> str:
    spec = FEATURE_SPEC.get(category)
    return spec.get("shape", "dot") if spec else "dot"


# ============ 五、注记密度控制（A2） ============
# 比例尺分母 → 每屏（1680×950）最大注记条数
# 用户要求"所有注记都要完整存在"，故上限按"全要素注记"放宽（原 40~170 过于保守，
# 会误判武汉全要素注记（约 220 条）为超标而建议裁剪，与用户需求冲突）
LABEL_DENSITY_LIMIT: Dict[int, int] = {
    1_000_000: 120,
    500_000: 180,
    250_000: 260,
    100_000: 360,
    50_000: 460,
    25_000: 560,
}


def label_density_limit(scale_denominator: int) -> int:
    """按比例尺返回每屏注记上限；未匹配取最近档位。"""
    if scale_denominator in LABEL_DENSITY_LIMIT:
        return LABEL_DENSITY_LIMIT[scale_denominator]
    nearest = min(LABEL_DENSITY_LIMIT.keys(), key=lambda s: abs(s - scale_denominator))
    return LABEL_DENSITY_LIMIT[nearest]


def zoom_to_scale_denominator(zoom) -> int:
    """zoom → 比例尺分母（与 map_service._zoom_to_scale 对齐）：
    <9→1:1M、≤10→1:250K、≤12→1:100K、≥13→1:25K。"""
    if zoom is None:
        return 250_000
    if zoom < 9:
        return 1_000_000
    if zoom <= 10:
        return 250_000
    if zoom <= 12:
        return 100_000
    return 25_000


def trim_labels_by_density(
    labels: List[Dict[str, Any]], scale_denominator: int
) -> List[Dict[str, Any]]:
    """按密度上限裁剪注记：超过上限时从低优先级逐条移除，P0/P1 尽量保留。"""
    limit = label_density_limit(scale_denominator)
    if len(labels) <= limit:
        return list(labels)
    # 优先级数值取 label 的 priority（P0=100…P3=20），越高越优先保留
    ordered = sorted(labels, key=lambda lb: -int(lb.get("priority", 0) or 0))
    kept = ordered[:limit]
    # 保持原始顺序返回
    ids = {id(lb) for lb in kept}
    return [lb for lb in labels if id(lb) in ids]


# ============ 六、注记避让/冲突矩阵（A3） ============
# 行=被遮挡要素类别，值=允许被更高/同优先级类别压盖的容忍度
# 数值越大越"舍得让"（低容忍=优先保证显示）。
# 水系与等高线注记宜相互避让；道路注记可与水系注记共享但不重叠文字。
ANNOTATION_CONFLICT_PRIORITY: Dict[str, int] = {
    # 类别 → 相对优先级（越高越优先显示）
    "admin": 100,
    "core_place": 90,
    "transport": 80,
    "water": 70,
    "peak": 60,
    "poi": 50,
    "normal": 30,
}

# 禁止同格网并存的注记类别对（成对，任一方向均冲突）
ANNOTATION_MUTUAL_EXCLUSION: List[tuple] = [
    ("water", "peak"),      # 水系注记与山峰注记不同格共存（避免水系/高程混淆）
]


def annotation_conflict(cat_a: str, cat_b: str) -> bool:
    """两注记类别在碰撞格网内是否互斥（相同格网内两注记不能共存）。"""
    if (cat_a, cat_b) in ANNOTATION_MUTUAL_EXCLUSION or (cat_b, cat_a) in ANNOTATION_MUTUAL_EXCLUSION:
        return True
    return False


# ============ 七、线要素最小显示长度判定（C9） ============
def should_display_line(category: str, length_m: float) -> bool:
    """线要素是否达到最小显示长度（图上 0.5mm 折算；短于不显示）。"""
    min_len = feature_min_display_len(category)
    return length_m >= min_len


# ============ 八、partial 尺度取舍（C8） ============
def select_partial(
    items: List[Dict[str, Any]],
    category_key: str,
    top_k: int,
    importance_field: str = "importance",
) -> List[Dict[str, Any]]:
    """尺度矩阵中 partial 状态：按要素 importance 降序取前 top_k，返回保留项。"""
    if not items:
        return []
    ranked = sorted(items, key=lambda it: -float(it.get(importance_field, 0) or 0))
    return ranked[:top_k]
