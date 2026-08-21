# -*- coding: utf-8 -*-
"""Generalization Benchmark：对四类武汉地图生成 before/after/metrics/qa JSON

用法: python tools/run_generalization_benchmark.py
输出: benchmarks/wuhan/generalization/<map_type>_<scale>/{before,after,metrics,qa}.json
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.map_service import MapService  # noqa: E402
from app.services.qa import MapQAService  # noqa: E402

OUT = os.path.join(ROOT, "benchmarks", "wuhan", "generalization")

# map_type, zoom（zoom 决定尺度）
CASES = [
    ("administrative", 10),
    ("traffic", 12),
    ("tourism", 12),
    ("terrain", 11),
]


def main():
    os.makedirs(OUT, exist_ok=True)
    ms = MapService(persist_path=os.path.join(ROOT, "data", "maps.json"))
    qa = MapQAService()
    summary = []
    for map_type, zoom in CASES:
        md = ms.generate_map(map_type, "武汉市", zoom=zoom)
        gm = md.get("generalization_metrics") or {}
        if "error" in gm:
            print(f"[SKIP] {map_type}: {gm['error']}")
            continue
        scale = gm.get("scale", 0)
        case_dir = os.path.join(OUT, f"{map_type}_{scale}")
        os.makedirs(case_dir, exist_ok=True)
        before = gm.get("before_counts", {})
        after = gm.get("after_counts", {})
        metrics = {
            "map_load": gm.get("map_load"),
            "data_loss": gm.get("data_loss"),
            "recall": gm.get("recall"),
            "topology": gm.get("topology"),
            "gates": gm.get("gates"),
            "blockers": gm.get("blockers"),
        }
        qa_report = qa.generate_report(md)
        files = {
            "before.json": before,
            "after.json": after,
            "metrics.json": metrics,
            "qa.json": qa_report,
        }
        for fname, data in files.items():
            with open(os.path.join(case_dir, fname), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        summary.append({
            "map_type": map_type, "scale": scale,
            "dataset_gate": gm.get("gates", {}).get("dataset_gate"),
            "generalization_gate": gm.get("gates", {}).get("generalization_gate"),
            "map_gate": gm.get("gates", {}).get("map_gate"),
            "source_blockers": gm.get("blockers", {}).get("source_blockers"),
            "category_recall": gm.get("recall", {}).get("category_recall"),
            "entity_recall": gm.get("recall", {}).get("entity_recall"),
            "recall": gm.get("recall", {}).get("overall_recall"),
            "map_load_score": (gm.get("map_load") or {}).get("map_load_score"),
            "qa_score": qa_report.get("total_score"),
        })
        print(f"[OK] {map_type} 1:{scale} gates={gm.get('gates',{}).get('dataset_gate')}/"
              f"{gm.get('gates',{}).get('generalization_gate')} "
              f"recall={gm.get('recall',{}).get('overall_recall')} "
              f"load={(gm.get('map_load') or {}).get('map_load_score')} qa={qa_report.get('total_score')}")
    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    ms.flush()
    print(f"\n输出: {OUT}")


if __name__ == "__main__":
    main()
