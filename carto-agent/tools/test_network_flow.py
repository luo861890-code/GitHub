# -*- coding: utf-8 -*-
"""CartoAgent 联网功能回归测试（需外网，建议提权/无代理运行）

用法（在仓库根目录，外网可用时）：
    python tools/test_network_flow.py

覆盖此前因无网无法验证的能力：
- LLM 流式对话（DeepSeek）
- 智能体地图生成（本地 + OSM 真实数据）
- OSRM 在线路径规划
- OSM Overpass 数据拉取（添加图层）
- 维基百科查询
- GraphRAG 图检索增强
数据写入 data/test_tmp/，测试结束后自动清理，不触碰生产数据。
"""
import json
import os
import shutil
import sys
import threading
import time
import urllib.request
import urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import uvicorn  # noqa: E402

import app.api.deps as deps  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.services.map_service import MapService  # noqa: E402
from app.services.session_service import SessionService  # noqa: E402

BASE = "http://127.0.0.1:8095"
PORT = 8095
results = []


def call(method, path, payload=None, timeout=360):
    url = BASE + path
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return resp.status, json.loads(body) if body else None


def stream_call(path, payload, timeout=360):
    """读取 SSE 流，返回事件列表"""
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
    )
    events = []
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        buf = b""
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            buf += chunk
            while b"\n\n" in buf:
                raw, buf = buf.split(b"\n\n", 1)
                for line in raw.split(b"\n"):
                    if line.startswith(b"data:"):
                        try:
                            events.append(json.loads(line[5:].decode("utf-8")))
                        except Exception:  # noqa: BLE001
                            pass
    return events


def test(name, fn):
    try:
        ok, detail = fn()
        results.append((name, "PASS" if ok else "FAIL", detail))
        print(("PASS" if ok else "FAIL"), name, "" if ok else detail)
    except Exception as e:  # noqa: BLE001
        results.append((name, "ERROR", str(e)))
        print("ERROR", name, repr(e)[:300])


def main():
    tmpdir = os.path.join(ROOT, "data", "test_tmp")
    if os.path.exists(tmpdir):
        shutil.rmtree(tmpdir)
    os.makedirs(tmpdir)
    print("临时数据目录:", tmpdir)

    # ===== 隔离地图/会话服务 =====
    ms = MapService(
        osm_service=deps.get_osm_service(),
        persist_path=os.path.join(tmpdir, "maps.json"),
    )
    seed_map_id = "map_network_seed"
    ms.put_map(seed_map_id, {
        "map_id": seed_map_id,
        "name": "联网测试地图",
        "map_type": "traffic",
        "region": "武汉市",
        "center": [30.5928, 114.3055],
        "zoom": 12,
        "theme": "amap_normal",
        "created_at": 1700000000,
        "metadata": {"数据来源": "测试"},
        "layers": [
            {
                "id": "seed_road",
                "type": "polyline",
                "name": "道路",
                "coordinates": [[[30.59, 114.30], [30.60, 114.31]]],
                "properties": [{"name": "路1"}],
                "style": {"color": "#3388ff"},
            }
        ],
    })
    deps._map_service = ms

    ss = SessionService()
    ss.sessions_file = os.path.join(tmpdir, "sessions.json")
    ss.sessions = {}
    deps._session_service = ss

    # ===== 启动服务 =====
    cfg = uvicorn.Config(fastapi_app, host="127.0.0.1", port=PORT, log_level="warning")
    server = uvicorn.Server(cfg)
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

    def t_llm_question():
        _, b = call("POST", "/api/chat/sessions", {"title": "联网问答"})
        sid = (b.get("data") or {}).get("session_id")
        events = stream_call(f"/api/chat/sessions/{sid}/stream", {"message": "武汉市一共有多少个行政区？请简要回答。"}, timeout=180)
        types = [e.get("type") for e in events]
        ok = "chunk" in types and "done" in types and "error" not in types
        text = next((e.get("content", "") for e in events if e.get("type") == "chunk"), "")
        return ok, {"events": types[:8], "text_len": len(text)}

    test("LLM流式问答(DeepSeek)", t_llm_question)

    def t_kg_question():
        _, b = call("POST", "/api/chat/sessions", {"title": "知识问答"})
        sid = (b.get("data") or {}).get("session_id")
        events = stream_call(f"/api/chat/sessions/{sid}/stream", {"message": "什么是专题地图？"}, timeout=180)
        types = [e.get("type") for e in events]
        has_ks = any(e.get("type") == "knowledge_sources" for e in events)
        return "chunk" in types and "done" in types and "error" not in types and has_ks, {"events": types[:10]}

    test("KG/RAG知识问答", t_kg_question)

    def t_map_generate():
        _, b = call("POST", "/api/maps/generate", {"map_type": "administrative", "region": "武汉市", "zoom": 10}, timeout=360)
        d = b.get("data") or {}
        return b.get("success") and d.get("map_id") and len(d.get("layers", [])) > 0, {
            "layers": len(d.get("layers", [])),
            "msg": b.get("message"),
        }

    test("行政图生成(本地+OSM)", t_map_generate)

    def t_traffic_generate():
        _, b = call("POST", "/api/maps/generate", {"map_type": "traffic", "region": "武汉市", "zoom": 12}, timeout=360)
        d = b.get("data") or {}
        return b.get("success") and d.get("map_id") and len(d.get("layers", [])) > 0, {
            "layers": len(d.get("layers", [])),
            "msg": b.get("message"),
        }

    test("交通图生成(OSM真实路网)", t_traffic_generate)

    def t_route_real():
        _, b = call(
            "POST",
            f"/api/maps/{seed_map_id}/route",
            {"start": [30.5928, 114.3055], "end": [30.52, 114.36], "profile": "driving"},
            timeout=120,
        )
        d = b.get("data") or {}
        return b.get("success") and d.get("source") == "osrm" and d.get("distance", 0) > 0, {
            "source": d.get("source"),
            "distance": d.get("distance"),
            "steps": len(d.get("steps") or []),
        }

    test("OSRM真实路径规划", t_route_real)

    def t_osm_layer():
        _, b = call(
            "POST",
            f"/api/maps/{seed_map_id}/layers",
            {"layer_type": "point", "name": "医院", "query": "amenity"},
            timeout=180,
        )
        d = b.get("data") or {}
        last = (d.get("layers") or [])[-1] if d.get("layers") else {}
        return b.get("success") and len(last.get("coordinates", [])) > 0, {
            "count": len(last.get("coordinates", [])),
            "msg": b.get("message"),
        }

    test("OSM数据拉取(添加医院图层)", t_osm_layer)

    def t_wiki():
        _, b = call("GET", "/api/maps/wiki?name=%E9%BB%84%E9%B9%A4%E6%A5%BC", timeout=30)
        d = b.get("data") or {}
        return b.get("success") and d.get("found"), {"source": d.get("source"), "extract": (d.get("extract") or "")[:40]}

    test("维基百科查询", t_wiki)

    def t_graphrag():
        _, b = call("POST", "/api/kg/graphrag", {"query": "武汉市有哪些制图相关的知识？"}, timeout=180)
        return b.get("success"), (b.get("data") or {})

    test("GraphRAG图检索增强", t_graphrag)

    def t_question_intent():
        _, b = call("POST", "/api/chat/sessions", {"title": "意图测试"})
        sid = (b.get("data") or {}).get("session_id")
        events = stream_call(f"/api/chat/sessions/{sid}/stream", {"message": "什么是专题地图？"}, timeout=180)
        types = [e.get("type") for e in events]
        # 问句应走知识问答：出现 knowledge_sources 且不生成地图
        has_ks = any(e.get("type") == "knowledge_sources" for e in events)
        no_map = not any(e.get("type") == "map" for e in events)
        return has_ks and no_map and "error" not in types, {"events": types[:10]}

    test("问句意图识别(不误判制图)", t_question_intent)

    server.should_exit = True
    thread.join(timeout=15)

    # 清理临时数据
    try:
        shutil.rmtree(tmpdir)
    except Exception:  # noqa: BLE001
        pass

    fails = [r for r in results if r[1] != "PASS"]
    print("=" * 50)
    print(f"TOTAL={len(results)} PASS={len(results) - len(fails)} FAIL={len(fails)}")
    for r in fails:
        print("FAIL:", r[0], r[2])
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
