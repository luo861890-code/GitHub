# -*- coding: utf-8 -*-
"""导出服务测试：PNG 必须为真实图像而非占位图。"""
import base64
import io

from PIL import Image

from app.services.export_service import ExportService


MAP = {
    "map_id": "m", "name": "测试", "map_type": "traffic",
    "layers": [
        {"id": "l1", "type": "polygon", "name": "湖泊", "coordinates": [[[30.58, 114.28], [30.58, 114.29], [30.59, 114.29]]],
         "style": {"fillColor": "#60a5fa", "fillOpacity": 0.5}},
        {"id": "l2", "type": "polyline", "name": "道路", "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
         "style": {"color": "#3388ff", "weight": 3}},
        {"id": "l3", "type": "circleMarker", "name": "景点", "coordinates": [[30.595, 114.305]],
         "style": {"color": "#dc2626", "radius": 6}},
    ],
}


def test_png_is_real_image():
    png = ExportService().export_png(MAP)
    assert png.startswith("data:image/png;base64,")
    raw = base64.b64decode(png.split(",")[1])
    assert len(raw) > 5000
    img = Image.open(io.BytesIO(raw))
    assert img.size[0] > 100 and img.size[1] > 100


def test_layout_png():
    png = ExportService().export_layout_png(MAP, {
        "pageSize": "A4", "orientation": "landscape", "dpi": 150,
        "showTitle": True, "showLegend": True, "showScaleBar": True,
        "showNorthArrow": True, "showGrid": False, "title": "布局测试",
    })
    assert png.startswith("data:image/png;base64,")
    assert len(base64.b64decode(png.split(",")[1])) > 5000


def test_svg_and_geojson():
    svc = ExportService()
    svg = svc.export_svg(MAP)
    assert "<svg" in svg
    gj = svc.export_geojson(MAP)
    assert gj.lstrip().startswith("{")
    assert '"FeatureCollection"' in gj
