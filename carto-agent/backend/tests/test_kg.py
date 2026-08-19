# -*- coding: utf-8 -*-
"""知识图谱服务测试：连接失败降级内存模式 + 自动重连不崩溃。"""
from app.services.kg_service import KGService


def test_memory_fallback_and_reconnect_safe():
    kg = KGService()
    assert kg.get_constraints()  # 无论 Neo4j 是否可用，至少返回内置/库内约束
    # 强制触发重连尝试（Neo4j 不可用时应安全保持内存模式）
    kg._last_connect_attempt = 0.0
    kg._ensure_connected()
    graph = kg.get_graph_data(limit=5)
    assert "nodes" in graph and "links" in graph
