# -*- coding: utf-8 -*-
"""ScaleRule：按比例尺 + 要素类别动态决定 tolerance/selection/aggregation/displacement。

简化容差按制图规范“图上最小可辨 0.2mm”折算实地米数：
  tolerance_m = 0.2mm × scale_denominator / 1000
  1:1M → 200m，1:500K → 100m，1:250K → 50m，1:100K → 20m，1:50K → 10m，1:25K → 5m
并按要素类别乘以系数（道路/水系保留更多细节，居民地/等高线可更粗）。
"""
from typing import Dict


SCALES: Dict[int, str] = {
    1_000_000: "1_1M",
    500_000: "1_500K",
    250_000: "1_250K",
    100_000: "1_100K",
    50_000: "1_50K",
    25_000: "1_25K",
}

# 图上最小可辨距离（mm）
MIN_RESOLUTION_MM = 0.2

# 要素类别 → 简化容差系数（>1 更粗，<1 更精细）
FEATURE_TOLERANCE_FACTOR: Dict[str, float] = {
    "admin_boundary": 1.0,
    "district_boundary": 0.8,
    "motorway": 0.5,
    "trunk_road": 0.6,
    "primary_road": 0.7,
    "secondary_road": 0.8,
    "minor_road": 1.0,
    "railway": 0.6,
    "metro": 0.5,
    "riverline": 0.4,
    "water": 0.5,
    "contour_major": 1.2,
    "contour_minor": 1.5,
    "builtup": 1.0,
    "poi": 1.0,
}


class ScaleRule:
    """单一尺度规则"""

    def __init__(self, scale_denominator: int):
        self.scale_denominator = scale_denominator
        self.base_tolerance_m = MIN_RESOLUTION_MM * scale_denominator / 1000.0

    def tolerance_m(self, feature_class: str) -> float:
        factor = FEATURE_TOLERANCE_FACTOR.get(feature_class, 1.0)
        return round(self.base_tolerance_m * factor, 2)

    def aggregation_distance_m(self, feature_class: str) -> float:
        # 聚合距离 = 图上 0.5mm（POI 聚类）或 1mm（线合并）
        base = 0.5 if feature_class in ("poi", "service_poi", "normal_poi") else 1.0
        return round(base * self.scale_denominator / 1000.0, 2)

    def displacement_distance_m(self, feature_class: str) -> float:
        # 位移 = 图上 0.3mm，解决符号压盖
        return round(0.3 * self.scale_denominator / 1000.0, 2)

    def to_dict(self) -> Dict[str, float]:
        return {
            "scale": self.scale_denominator,
            "base_tolerance_m": round(self.base_tolerance_m, 2),
        }


def get_scale_rule(scale_denominator: int) -> ScaleRule:
    if scale_denominator not in SCALES:
        # 就近匹配已知档位
        scale_denominator = min(SCALES.keys(), key=lambda s: abs(s - scale_denominator))
    return ScaleRule(scale_denominator)
