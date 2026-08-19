# -*- coding: utf-8 -*-
"""智能体意图识别测试（关键词/问句优先逻辑）。"""
import pytest

from app.services.agent_service import AgentService


def _agent():
    a = AgentService.__new__(AgentService)
    a.llm_service = None
    return a


@pytest.mark.parametrize("message,expected", [
    ("什么是专题地图？", "question"),
    ("武汉市一共有多少个行政区？", "question"),
    ("武汉有哪些区？", "question"),
    ("地图制图有哪些基本原则？", "question"),
    ("生成一份武汉市交通图", "map_generation"),
    ("画一张武汉市旅游图", "map_generation"),
    ("武汉市交通图", "map_generation"),
    ("把道路改成红色", "map_modification"),
    ("添加一个医院图层", "map_modification"),
])
def test_detect_intent(message, expected):
    assert _agent()._detect_intent(message, []) == expected
