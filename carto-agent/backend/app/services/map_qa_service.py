# -*- coding: utf-8 -*-
"""地图质量验收服务（兼容入口）

实现已迁移至 app.services.qa 包（《CartoAgent 武汉四类专题地图质量验收规范 V1.0》），
本模块保留 MapQAService 名称供 API/旧调用向后兼容。
"""
from app.services.qa import MapQAService, to_text

__all__ = ["MapQAService", "to_text"]
