# -*- coding: utf-8 -*-
"""CartoAgent 全量接口回归测试脚本

用法（在仓库根目录）：
    python tools/test_api_flow.py

说明：
- 服务在进程内启动（127.0.0.1:8099），测试结束后自动关闭；
- 地图/会话数据写入临时目录，绝不触碰 data/maps.json 与 data/sessions.json；
- 覆盖会话、地图、图层（增/查/改/删/排序/分组/复制/几何）、标注、质检、
  导出（GeoJSON/SVG/PNG/布局PNG）、知识图谱、设置、百科、路径规划、
  自然语言修改、地图生成等 25 项接口。
"""
import base64
import json
import os
import sys
import tempfile
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import uvicorn  # noqa: E402

import app.api.deps as deps  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.map_service import MapService  # noqa: E402
from app.services.session_service import SessionService  # noqa: E402

BASE = "http://127.0.0.1:8099"
PORT = 8099
results = []


def call(method, path, payload=None, timeout=240):
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.status, json.loads(body) if body else None, time.time() - t0


def test(name, fn):
    try:
        ok, detail = fn()
        results.append((name, "PASS" if ok else "FAIL", detail))
        print(("PASS" if ok else "FAIL"), name, "" if ok else detail)
    except Exception as e:  # noqa: BLE001
        results.append((name, "ERROR", str(e)))
        print("ERROR", name, repr(e)[:300])


def main():
    tmpdir = tempfile.mkdtemp(prefix="carto_test_")
    print("临时数据目录:", tmpdir)

    # ===== 隔离服务实例（不写生产数据） =====
    ms = MapService(persist_path=os.path.join(tmpdir, "maps.json"))
    map_id = "map_test_0001"
    ms.put_map(map_id, {
        "map_id": map_id,
        "name": "测试地图",
        "map_type": "traffic",
        "region": "武汉市",
        "center": [30.5928, 114.3055],
        "zoom": 12,
        "theme": "amap_normal",
        "created_at": 1700000000,
        "metadata": {"数据来源": "本地测试数据", "坐标系": "WGS84", "地图类型": "交通地图"},
        "legend": {"title": "图例", "items": [{"label": "道路", "type": "line", "color": "#3388ff"}]},
        "layers": [
            {
                "id": "layer_road",
                "type": "polyline",
                "name": "道路",
                "coordinates": [[[30.59, 114.30], [30.60, 114.31], [30.61, 114.32]]],
                "properties": [{"name": "路1", "subtype": "primary"}],
                "style": {"color": "#3388ff", "weight": 3},
            },
            {
                "id": "layer_lake",
                "type": "polygon",
                "name": "湖泊",
                "coordinates": [[[30.58, 114.28], [30.58, 114.29], [30.59, 114.29], [30.59, 114.28]]],
                "properties": [{"name": "湖1"}],
                "style": {"fillColor": "#60a5fa", "fillOpacity": 0.6},
            },
        ],
    })
    deps._map_service = ms

    ss = SessionService()
    ss.sessions_file = os.path.join(tmpdir, "sessions.json")
    ss.sessions = {}
    deps._session_service = ss

    # ===== 启动服务 =====
    server_cfg = uvicorn.Config(fastapi_app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(server_cfg)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(80):
        try:
            call("GET", "/health", timeout=3)
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    else:
        print("服务启动失败")
        return 1

    # ===== 测试用例 =====
    test("健康检查", lambda: ((call("GET", "/health")[1] or {}).get("success") is True, ""))

    def t_sessions():
        _, b, _ = call("POST", "/api/chat/sessions", {"title": "回归测试"})
        sid = (b.get("data") or {}).get("session_id")
        _, b2, _ = call("DELETE", f"/api/chat/sessions/{sid}")
        return bool(sid) and b2.get("success"), ""

    test("会话创建/删除", t_sessions)

    def t_maps():
        _, b, _ = call("GET", "/api/maps")
        _, b2, _ = call("GET", "/api/maps/map_test_0001")
        return (
            b.get("success") and len(b.get("data") or []) == 1
            and b2.get("success") and len((b2.get("data") or {}).get("layers", [])) == 2,
            "",
        )

    test("地图列表/详情", t_maps)

    def t_add_layer_data():
        _, b, _ = call("POST", "/api/maps/map_test_0001/layers", {
            "layer_type": "circleMarker",
            "name": "分析结果点",
            "coordinates": [[30.595, 114.305]],
            "properties": [{"name": "p"}],
            "style": {"color": "#ef4444"},
            "group": "分析结果",
        })
        d = b.get("data") or {}
        return (
            b.get("success")
            and d.get("layers", [])[-1].get("coordinates") == [[30.595, 114.305]],
            b.get("message"),
        )

    test("添加自定义数据图层", t_add_layer_data)

    def t_duplicate():
        _, b, _ = call("POST", "/api/maps/map_test_0001/layers/layer_road/duplicate")
        d = b.get("data") or {}
        return b.get("success") and any("副本" in n for n in [l.get("name") for l in d.get("layers", [])]), ""

    test("复制图层", t_duplicate)

    def t_reorder():
        _, b, _ = call("POST", "/api/maps/map_test_0001/layers/reorder", {"layer_ids": ["layer_lake", "layer_road"]})
        d = b.get("data") or {}
        return b.get("success") and d.get("layers", [])[0].get("id") == "layer_lake", ""

    test("图层重排", t_reorder)

    def t_patch_group():
        _, b, _ = call("PATCH", "/api/maps/map_test_0001/layers/layer_road", {"group": "交通组"})
        d = b.get("data") or {}
        lr = next((l for l in d.get("layers", []) if l.get("id") == "layer_road"), {})
        return b.get("success") and lr.get("group") == "交通组", lr.get("group")

    test("图层分组持久化", t_patch_group)

    def t_visible():
        _, b, _ = call("PUT", "/api/maps/map_test_0001/layers/layer_lake/visible", {"visible": False})
        d = b.get("data") or {}
        ll = next((l for l in d.get("layers", []) if l.get("id") == "layer_lake"), {})
        return b.get("success") and ll.get("visible") is False, ""

    test("图层显隐", t_visible)

    def t_geometry():
        _, b, _ = call("PUT", "/api/maps/map_test_0001/layers/layer_road/geometry", {
            "coordinates": [[[30.59, 114.30], [30.62, 114.33]]],
        })
        d = b.get("data") or {}
        lr = next((l for l in d.get("layers", []) if l.get("id") == "layer_road"), {})
        return b.get("success") and len(lr.get("coordinates", [[]])[0]) == 2, ""

    test("编辑保存几何", t_geometry)

    def t_marker():
        _, b, _ = call("POST", "/api/maps/map_test_0001/marker", {"name": "测试标注点", "lat": 30.60, "lng": 114.31})
        return b.get("success"), b.get("message")

    test("添加标注", t_marker)

    def t_quality():
        _, b, _ = call("GET", "/api/maps/map_test_0001/quality")
        ok = b.get("success") and "items" in (b.get("data") or {})
        _, b2, _ = call("POST", "/api/maps/map_test_0001/quality/accept")
        meta = (b2.get("data") or {}).get("metadata", {})
        return ok and b2.get("success") and meta.get("质检结论") == "已接受（人工确认）", ""

    test("质量检测+接受", t_quality)

    def t_export(fmt, layout=None):
        payload = {"format": fmt}
        if layout:
            payload["layout"] = layout
        _, b, _ = call("POST", "/api/maps/map_test_0001/export", payload)
        d = b.get("data")
        if fmt == "geojson":
            return b.get("success") and isinstance(d, str) and d.lstrip().startswith("{"), len(d or "")
        if fmt == "svg":
            return b.get("success") and isinstance(d, str) and "<svg" in d, len(d or "")
        raw = base64.b64decode(d.split(",")[1]) if isinstance(d, str) and d.startswith("data:image/png;base64,") else b""
        return b.get("success") and len(raw) > 5000, len(raw)

    test("导出GeoJSON", lambda: t_export("geojson"))
    test("导出SVG", lambda: t_export("svg"))
    test("导出PNG(真实图像)", lambda: t_export("png"))
    test(
        "布局导出PNG",
        lambda: t_export("png", {
            "pageSize": "A4",
            "orientation": "landscape",
            "dpi": 150,
            "showTitle": True,
            "showLegend": True,
            "showScaleBar": True,
            "showNorthArrow": True,
            "showGrid": True,
            "title": "测试布局",
            "legendPosition": "bottomright",
        }),
    )

    def t_kg():
        _, b, _ = call("GET", "/api/kg/graph?limit=50")
        d = b.get("data") or {}
        return b.get("success") and len(d.get("nodes", [])) > 0, {"nodes": len(d.get("nodes", [])), "links": len(d.get("links", []))}

    test("知识图谱图数据", t_kg)
    test("KG自然语言查询", lambda: (call("POST", "/api/kg/query", {"question": "什么是专题地图？"})[1].get("success"), ""))
    test("制图约束", lambda: (call("GET", "/api/kg/constraints")[1].get("success"), ""))
    test("样式推荐", lambda: (call("GET", "/api/kg/styles/traffic")[1].get("success"), ""))
    test("本体概要", lambda: (call("GET", "/api/kg/ontology")[1].get("success"), ""))

    def t_settings():
        _, b, _ = call("GET", "/api/settings/llm/providers")
        d = b.get("data") or {}
        _, b2, _ = call("GET", "/api/settings/map/themes")
        return (
            b.get("success") and "providers" in d
            and b2.get("success") and len(b2.get("data") or []) >= 5,
            {"providers": len(d.get("providers", [])), "themes": len(b2.get("data") or [])},
        )

    test("设置接口", t_settings)
    test("百科查询", lambda: (call("GET", "/api/maps/wiki?name=%E9%BB%84%E9%B9%A4%E6%A5%BC")[1].get("success"), ""))

    def t_route():
        _, b, _ = call("POST", "/api/maps/map_test_0001/route", {
            "start": [30.5928, 114.3055],
            "end": [30.52, 114.36],
            "profile": "walking",
        })
        d = b.get("data") or {}
        return b.get("success") and d.get("coordinates"), {"distance": d.get("distance"), "source": d.get("source")}

    test("路径规划(降级)", t_route)
    test(
        "自然语言修改地图",
        lambda: (call("POST", "/api/maps/map_test_0001/modify", {"instruction": "把道路图层颜色改成红色"})[1].get("success"), ""),
    )

    def t_generate():
        _, b, _ = call("POST", "/api/maps/generate", {"map_type": "administrative", "region": "武汉市", "zoom": 10})
        d = b.get("data") or {}
        return b.get("success") and d.get("map_id") and len(d.get("layers", [])) > 0, {"layers": len(d.get("layers", [])), "msg": b.get("message")}

    test("地图生成(本地数据)", t_generate)

    server.should_exit = True
    thread.join(timeout=10)

    # ===== 汇总 =====
    fails = [r for r in results if r[1] != "PASS"]
    print("=" * 50)
    print(f"TOTAL={len(results)} PASS={len(results) - len(fails)} FAIL={len(fails)}")
    for r in fails:
        print("FAIL:", r[0], r[2])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
