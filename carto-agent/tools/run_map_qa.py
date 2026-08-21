# -*- coding: utf-8 -*-
"""武汉四类地图自动验收：生成 1000 分制质量报告。

用法:
    python tools/run_map_qa.py [--map-type traffic] [--out outputs/reports]

输出:
    outputs/reports/{map_id}_qa.json   单图验收报告
    outputs/reports/summary.json       四类地图汇总
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.map_qa_service import MapQAService  # noqa: E402
from app.services.map_service import MapService  # noqa: E402


def _latest_by_type(maps: dict, map_type: str):
    """从 maps 摘要索引中取某类型最新一张地图"""
    candidates = [m for m in maps.values() if m.get("map_type") == map_type]
    if not candidates:
        return None
    return max(candidates, key=lambda m: m.get("created_at", 0))


def main():
    parser = argparse.ArgumentParser(description="武汉四类地图自动验收（1000 分制）")
    parser.add_argument("--map-type", default=None, help="仅验收指定类型（administrative/traffic/tourism/terrain）")
    parser.add_argument("--out", default=os.path.join(ROOT, "outputs", "reports"), help="报告输出目录")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    # settings.data_dir 为相对 backend/ 的 "../data"，脚本在项目根运行需显式指定
    map_service = MapService(persist_path=os.path.join(ROOT, "data", "maps.json"))
    summary = []

    types = [args.map_type] if args.map_type else ["administrative", "traffic", "tourism", "terrain"]
    for map_type in types:
        meta = _latest_by_type(map_service.maps, map_type)
        if not meta:
            print(f"[SKIP] 无 {map_type} 地图")
            continue
        map_data = map_service.get_map(meta["map_id"])
        if not map_data:
            print(f"[SKIP] 地图加载失败 {meta['map_id']}")
            continue
        report = MapQAService().generate_report(map_data)
        out_path = os.path.join(args.out, f"{meta['map_id']}_qa.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        summary.append({
            "map_id": meta["map_id"],
            "name": meta.get("name", ""),
            "map_type": map_type,
            "total_score": report["total_score"],
            "grade": report["grade"],
            "status": report["status"],
            "critical": report["critical_errors"],
            "major": report["major_errors"],
            "minor": report["minor_errors"],
        })
        print(f"[OK] {map_type:15s} {report['total_score']:4d}/1000 ({report['grade']}) "
              f"{report['status']} C={report['critical_errors']} M={report['major_errors']} "
              f"m={report['minor_errors']}")

    summary_path = os.path.join(args.out, "summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    print(f"\n报告已输出到: {args.out}")


if __name__ == "__main__":
    main()
