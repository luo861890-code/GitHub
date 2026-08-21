# -*- coding: utf-8 -*-
"""统一 GIS 数据质量层（DataQualityEngine）

模块：
  geometry.py    几何/拓扑/位置校验
  attribute.py   属性/完整性/元数据/来源校验
  engine.py      DataQualityEngine（统一入口，输出 DataQualityReport JSON）
"""
from .engine import DataQualityEngine

__all__ = ["DataQualityEngine"]
