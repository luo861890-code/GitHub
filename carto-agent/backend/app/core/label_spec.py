# -*- coding: utf-8 -*-
"""地图注记规范（Label Specification）

依据《地图注记规范》落地：
- 注记优先级分级 P0/P1/P2/P3（P0 市名/核心河流/核心枢纽，P1 区名/主要道路/铁路/核心景区，
  P2 次要道路/一般景点/普通地名，P3 普通 POI/辅助信息）；
- 字体层级：P0 大号粗体（黑体）、P1 中号半粗（宋体）、P2 常规（宋体）、P3 小号（宋体），
  同一等级字体一致、不随地图随机变化；
- 颜色层级：核心注记 > 普通注记 > 背景，注记颜色不强于主题要素；
- 尺度范围：每个 label 带 scale_range（分母），小比例尺只显示 P0/P1；
- 注记对象字段：label_id / text / feature_type / priority / anchor / font / size / weight /
  color / scale_range（对应规范 §23 JSON 结构）。
"""
from typing import Any, Dict, List


# ============ 注记优先级（规范 §二） ============
P0 = 100   # 市名、核心行政区、核心河流、核心交通枢纽
P1 = 80    # 区名、主要道路、主要铁路、核心景区
P2 = 50    # 次要道路、一般景点、普通地名
P3 = 20    # 普通 POI、辅助信息

# ============ 字体层级（规范 §十六） ============
# font: black=黑体粗 / bold=半粗 / song=宋体常规
LABEL_STYLE: Dict[int, Dict[str, Any]] = {
    P0: {"font": "black", "size": 20, "weight": 800, "color": "#1F2937"},
    P1: {"font": "bold",  "size": 15, "weight": 700, "color": "#1F2937"},
    P2: {"font": "song",  "size": 12, "weight": 500, "color": "#374151"},
    P3: {"font": "song",  "size": 10, "weight": 400, "color": "#6B7280"},
}

# 颜色层级修正（规范 §十七：主题要素 > 核心注记 > 普通注记 > 背景）：
# 水系注记参考高德地图样式：蓝色 #2E6FA3 + 斜体 + 白色描边（halo），
# 交通注记用深灰，仍弱于主题符号
FEATURE_COLOR_OVERRIDE: Dict[str, str] = {
    "water": "#2E6FA3",   # 水系注记（高德蓝，弱于水体填充但清晰）
    "transport": "#374151",  # 道路/轨道注记（深灰，弱于道路符号）
    "admin": "#1F2937",   # 行政注记（深灰黑）
    "peak": "#7A5230",    # 山峰注记（棕褐）
    "poi": "#B91C1C",     # 旅游 POI 注记（红，强于普通标签、弱于符号）
}

# ============ 尺度范围（规范 §十） ============
# min_zoom → scale_range（分母区间 [小比例尺分母, 大比例尺分母]）
# zoom→scale 映射（map_service._zoom_to_scale）：<9→1M、≤10→250k、≤12→100k、≥14→25k
SCALE_RANGE_BY_MIN_ZOOM: Dict[int, List[int]] = {
    6:  [1000000, 25000],   # 市名全尺度
    7:  [1000000, 25000],   # 特大型湖泊（≥100km²）
    8:  [1000000, 25000],   # 区名/大湖 1:100万 起
    9:  [250000, 25000],    # 山峰/轨道 1:25万 起
    10: [100000, 25000],    # 地标/主干道 1:10万 起
    12: [100000, 25000],    # 小湖/支流 1:10万 起
    13: [25000, 25000],     # 次干道 1:2.5万
    14: [25000, 25000],     # 支路 1:2.5万
}

# ============ 锚点类型（规范 §三/四/五） ============
ANCHOR_POINT = "point"
ANCHOR_LINE = "line"
ANCHOR_AREA = "area"


def scale_range_for(min_zoom: int) -> List[int]:
    """min_zoom → scale_range（无档位时取全尺度）"""
    return list(SCALE_RANGE_BY_MIN_ZOOM.get(min_zoom, [1000000, 25000]))


def style_for(priority: int) -> Dict[str, Any]:
    """按优先级取字体/字号/字重/字色规格（同一等级完全一致）"""
    return dict(LABEL_STYLE.get(priority, LABEL_STYLE[P3]))


def make_label_meta(
    label_id: str,
    text: str,
    feature_type: str,
    priority: int,
    anchor: str,
    min_zoom: int,
    feature_color_key: str = "",
) -> Dict[str, Any]:
    """构建注记对象字段（规范 §23 JSON 结构 + 系统扩展字段）"""
    style = style_for(priority)
    font = style["font"]
    color = FEATURE_COLOR_OVERRIDE.get(feature_color_key, style["color"])
    halo = False
    if feature_color_key == "water":
        # 高德式水系注记：宋体斜体 + 白色描边
        font = "italic"
        halo = True
    meta: Dict[str, Any] = {
        "label_id": label_id,
        "name": text,
        "feature_type": feature_type,
        "priority": priority,
        "anchor": anchor,
        "font": font,
        "size": style["size"],
        "fontSize": style["size"],
        "weight": style["weight"],
        "color": color,
        "halo": halo,
        "scale_range": scale_range_for(min_zoom),
        "min_zoom": min_zoom,
        "visibility": True,
    }
    return meta


def priority_label(priority: int) -> str:
    return {P0: "P0", P1: "P1", P2: "P2", P3: "P3"}.get(priority, "P3")
