# -*- coding: utf-8 -*-
"""工具生态测试（计划 2.5）"""
from app.services.tool_registry import (
    ToolRegistry,
    SimplifyGeometryTool,
    DecorationTool,
    BufferAnalysisTool,
    OverlayAnalysisTool,
    ExportFormatTool,
)


def test_tool_registry_registration():
    reg = ToolRegistry()
    reg.register(SimplifyGeometryTool())
    reg.register(DecorationTool("add_title"))
    reg.register(BufferAnalysisTool())
    reg.register(OverlayAnalysisTool())
    assert reg.tool_count >= 4
    names = reg.list_tools()
    assert "simplify_geometry" in names
    assert "add_title" in names


def test_simplify_and_buffer():
    simp = SimplifyGeometryTool().execute(
        coordinates=[[[30.59, 114.30], [30.591, 114.301], [30.60, 114.31]]],
        tolerance=0.001,
    )
    assert simp["success"] is True
    buf = BufferAnalysisTool().execute(coordinates=[[30.59, 114.30]], distance_km=1)
    assert buf["success"] is True
    assert len(buf["result"]["buffer_coords"]) >= 3


def test_export_format_tool():
    tool = ExportFormatTool(None, "geojson")
    assert tool.definition.name.startswith("export_")
