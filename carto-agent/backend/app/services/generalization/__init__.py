# -*- coding: utf-8 -*-
"""制图综合引擎（GeneralizationEngine）

Selection / Simplification / Aggregation / Displacement / Collapse / Exaggeration
Scale-aware（ScaleRule）+ MapLoadMetrics + ImportantFeatureRecall + DataLoss + Topology。
"""
from .engine import GeneralizationEngine
from .scale_rules import ScaleRule, get_scale_rule, SCALES

__all__ = ["GeneralizationEngine", "ScaleRule", "get_scale_rule", "SCALES"]
