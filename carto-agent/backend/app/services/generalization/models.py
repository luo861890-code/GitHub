# -*- coding: utf-8 -*-
"""GeneralizationEngine 统一输入/输出模型"""
from typing import Any, Dict, List, Optional


class GeneralizationInput:
    """单一要素综合输入"""

    def __init__(
        self,
        feature_id: str,
        map_type: str,
        scale: int,
        feature_class: str,
        importance: float = 0.5,
        geometry: Optional[Dict[str, Any]] = None,
        source_crs: str = "EPSG:4326",
        target_crs: str = "EPSG:4547",
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.feature_id = feature_id
        self.map_type = map_type
        self.scale = scale
        self.feature_class = feature_class
        self.importance = importance
        self.geometry = geometry
        self.source_crs = source_crs
        self.target_crs = target_crs
        self.properties = properties or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "map_type": self.map_type,
            "scale": self.scale,
            "feature_class": self.feature_class,
            "importance": self.importance,
        }


class GeneralizationResult:
    """单一要素综合输出"""

    def __init__(
        self,
        feature_id: str,
        operation: str,
        original_geometry: Optional[Dict[str, Any]],
        generalized_geometry: Optional[Dict[str, Any]],
        parameters: Optional[Dict[str, Any]] = None,
        reason: str = "",
        important_feature: bool = False,
        quality_metrics: Optional[Dict[str, Any]] = None,
    ):
        self.feature_id = feature_id
        self.operation = operation
        self.original_geometry = original_geometry
        self.generalized_geometry = generalized_geometry
        self.parameters = parameters or {}
        self.reason = reason
        self.important_feature = important_feature
        self.quality_metrics = quality_metrics or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "operation": self.operation,
            "original_geometry": self.original_geometry,
            "generalized_geometry": self.generalized_geometry,
            "parameters": self.parameters,
            "reason": self.reason,
            "important_feature": self.important_feature,
            "quality_metrics": self.quality_metrics,
        }
