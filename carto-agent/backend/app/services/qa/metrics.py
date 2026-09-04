# -*- coding: utf-8 -*-
"""质量验收公共指标与工具（《CartoAgent 武汉四类专题地图质量验收规范 V1.0》）

- 十项一级指标（A-J，合计 1000 分）
- 问题分级：C0 Critical / C1 Major / C2 Minor / C3 Suggestion
- 等级：S≥900 / A 850-899 / B 750-849 / C 650-749 / D 600-649 / E<600
- 状态：PASS / CONDITIONAL_PASS / REWORK / FAIL（致命错误门槛）
"""
from typing import Any, Dict, List, Tuple

from app.utils.geometry import _ring_area_km2

# 武汉市域近似范围（由 wuhan_districts.geojson 实测：
# lat 29.969~31.361，lng 113.702~115.082；仅用于越界/归属检测，勿用于精确空间分析）
WUHAN_BBOX = {"min_lat": 29.96, "max_lat": 31.37, "min_lng": 113.69, "max_lng": 115.09}
WUHAN_DISTRICT_COUNT = 13
WUHAN_DISTRICTS = {
    "江岸区", "江汉区", "硚口区", "汉阳区", "武昌区", "青山区",
    "洪山区", "东西湖区", "汉南区", "蔡甸区", "江夏区", "黄陂区", "新洲区",
}

# 十项一级指标（规范 §二）
DIMENSIONS: Dict[str, Dict[str, Any]] = {
    "data_quality":       {"name": "A. 地理数据质量", "max": 200},
    "completeness":       {"name": "B. 数据数量与完整性", "max": 100},
    "topology":           {"name": "C. 空间/拓扑/逻辑一致性", "max": 100},
    "multi_source":       {"name": "D. 多源一致性与时效性", "max": 80},
    "generalization":     {"name": "E. 地图综合与多尺度表达", "max": 180},
    "symbol_visual":      {"name": "F. 符号系统与视觉层级", "max": 100},
    "label":              {"name": "G. 注记与冲突处理", "max": 80},
    "thematic":           {"name": "H. 专题信息质量", "max": 70},
    "layout":             {"name": "I. 地图整饰与版式", "max": 50},
    "fact":               {"name": "J. 事实与语义正确性", "max": 40},
}

# 等级区间
GRADE_BANDS: List[Tuple[int, str]] = [
    (900, "S"), (850, "A"), (750, "B"), (650, "C"), (600, "D"), (0, "E"),
]

# 四类地图专项权重（规范 §21）：{维度: 权重系数}，缺失维度补 0
MAP_TYPE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "administrative": {
        "data_quality": 0.35, "topology": 0.20, "generalization": 0.15,
        "symbol_visual": 0.10, "label": 0.10, "layout": 0.10,
    },
    "traffic": {
        "data_quality": 0.35, "generalization": 0.25, "symbol_visual": 0.15,
        "label": 0.10, "multi_source": 0.10, "layout": 0.05,
    },
    "tourism": {
        "thematic": 0.30, "data_quality": 0.20, "generalization": 0.15,
        "symbol_visual": 0.15, "label": 0.10, "fact": 0.10,
    },
    "terrain": {
        "data_quality": 0.35, "thematic": 0.20, "generalization": 0.15,
        "symbol_visual": 0.15, "multi_source": 0.10, "layout": 0.05,
    },
}

# 四类地图关键专题图层（B1 覆盖检测）
THEMATIC_EXPECTED: Dict[str, List[str]] = {
    "administrative": ["区县政区", "武汉市域边界", "区县界", "区县名称标注", "区县行政中心"],
    "traffic": ["道路", "轨道交通", "高速", "主干道", "主要桥梁", "长江"],
    "tourism": ["地标", "公园", "博物馆", "历史遗迹"],
    "terrain": ["等高线", "陆地底图", "水系"],
}

# 各图类型对每项指标的最低通过线（规范 §27：最低分/推荐目标）
PASS_THRESHOLDS: Dict[str, Dict[str, int]] = {
    "administrative": {"min": 850, "target": 920},
    "traffic": {"min": 850, "target": 930},
    "tourism": {"min": 800, "target": 900},
    "terrain": {"min": 850, "target": 920},
}

# 整饰检查项（I 类，各 5 分）
DECORATION_ITEMS: List[Tuple[str, str]] = [
    ("title", "标题"), ("legend", "图例"), ("scale_bar", "比例尺"), ("north_arrow", "指北针"),
    ("frame", "图廓"), ("graticule", "经纬网"), ("source", "数据来源"), ("time", "数据时间"),
    ("crs", "坐标/投影说明"), ("made_at", "制图时间"),
]


def grade_of(score: int) -> str:
    """按总分返回等级"""
    for threshold, g in GRADE_BANDS:
        if score >= threshold:
            return g
    return "E"


def status_of(score: int, critical: int, map_type: str = "") -> str:
    """按总分/致命错误/用途返回验收状态"""
    if critical > 0:
        return "FAIL" if critical >= 2 else "REWORK"
    threshold = PASS_THRESHOLDS.get(map_type, {}).get("min", 750)
    if score >= threshold:
        return "PASS"
    if score >= 650:
        return "CONDITIONAL_PASS"
    return "REWORK"


def point_in_bbox(lat: float, lng: float) -> bool:
    """点是否在武汉市域近似范围内"""
    return (WUHAN_BBOX["min_lat"] <= lat <= WUHAN_BBOX["max_lat"]
            and WUHAN_BBOX["min_lng"] <= lng <= WUHAN_BBOX["max_lng"])


def area_km2(ring: Any) -> float:
    """安全计算环面积（km²）"""
    try:
        if isinstance(ring, list) and len(ring) >= 4:
            return _ring_area_km2(ring)
    except Exception:
        pass
    return 0.0


def valid_pt(c: Any) -> bool:
    """坐标点是否合法"""
    return (isinstance(c, list) and len(c) >= 2
            and isinstance(c[0], (int, float)) and isinstance(c[1], (int, float))
            and -90 <= float(c[0]) <= 90 and -180 <= float(c[1]) <= 180)
