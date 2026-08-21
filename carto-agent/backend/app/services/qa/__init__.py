# -*- coding: utf-8 -*-
"""地图质量验收包（《CartoAgent 武汉四类专题地图质量验收规范 V1.0》）

模块结构：
  metrics.py                    指标/等级/状态/权重/问题分级
  data_quality.py               A. 地理数据质量 200
  completeness.py               B. 数据数量与完整性 100
  topology_quality.py           C. 空间/拓扑/逻辑一致性 100
  temporal_source_quality.py    D. 多源一致性与时效性 80
  generalization_quality.py     E. 地图综合与多尺度表达 180
  symbol_label_quality.py       F. 符号视觉 100 + G. 注记 80
  layout_thematic_fact.py       H. 专题 70 + I. 整饰 50 + J. 事实 40
  map_score.py                  MapQAService（加权评分/等级/状态）
  report.py                     文本报告模板
"""
from .map_score import MapQAService
from .report import to_text

__all__ = ["MapQAService", "to_text"]
