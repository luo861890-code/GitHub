# -*- coding: utf-8 -*-
"""最终 Benchmark：四类武汉地图 × 四尺度 = 16 组完整验收。

每组输出 benchmarks/wuhan/final/<map_type>_<scale>/
  {before, after, metrics, qa, runtime}.json
并汇总 summary.json（评分/门禁/召回/重复/错误）。

用法: python tools/run_final_benchmark.py [--map traffic] [--scale 100000]
"""
import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.map_service import MapService  # noqa: E402
from app.services.qa import MapQAService  # noqa: E402

OUT = os.path.join(ROOT, "benchmarks", "wuhan", "final")

SCALE_ZOOM = {500_000: 8, 250_000: 10, 100_000: 12, 25_000: 14}
MAP_TYPES = ["administrative", "traffic", "tourism", "terrain"]
SCALES = [500_000, 250_000, 100_000, 25_000]


def main():
    parser = argparse.ArgumentParser(description="CartoAgent 16组最终 Benchmark")
    parser.add_argument("--map", default=None, help="仅跑某类地图")
    parser.add_argument("--scale", type=int, default=None, help="仅跑某比例尺")
    parser.add_argument("--summary-only", action="store_true",
                        help="不重新生成地图，仅从 benchmarks/wuhan/final/ 重建 summary.json")
    args = parser.parse_args()

    os.makedirs(OUT, exist_ok=True)
    if args.summary_only:
        summary = []
        for d in sorted(os.listdir(OUT)):
            m_path = os.path.join(OUT, d, "metrics.json")
            q_path = os.path.join(OUT, d, "qa.json")
            r_path = os.path.join(OUT, d, "runtime.json")
            if not (os.path.exists(m_path) and os.path.exists(q_path)):
                continue
            with open(m_path, encoding="utf-8") as f:
                m = json.load(f)
            with open(q_path, encoding="utf-8") as f:
                q = json.load(f)
            runtime = {}
            if os.path.exists(r_path):
                with open(r_path, encoding="utf-8") as f:
                    runtime = json.load(f)
            mt = d.rsplit("_", 1)[0]
            effective_scale = m.get("scale", 0)
            summary.append({
                "map_type": mt,
                "requested_scale": effective_scale,
                "effective_scale": effective_scale,
                "runtime_seconds": runtime.get("runtime_seconds"),
                "dataset_gate": (m.get("gates") or {}).get("dataset_gate"),
                "generalization_gate": (m.get("gates") or {}).get("generalization_gate"),
                "map_gate": (m.get("gates") or {}).get("map_gate"),
                "category_recall": (m.get("recall") or {}).get("category_recall"),
                "entity_recall": (m.get("recall") or {}).get("entity_recall"),
                "overall_recall": (m.get("recall") or {}).get("overall_recall"),
                "final_duplicate_count": m.get("final_duplicate_count"),
                "map_load_score": (m.get("map_load") or {}).get("map_load_score"),
                "qa_score": q.get("total_score"),
                "grade": q.get("grade"),
                "status": q.get("status"),
                "critical_errors": q.get("critical_errors"),
                "major_errors": q.get("major_errors"),
                "minor_errors": q.get("minor_errors"),
            })
        with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=1)
        print(f"summary 重建完成：{len(summary)} 组 -> {os.path.join(OUT, 'summary.json')}")
        return

    ms = MapService(persist_path=os.path.join(ROOT, "data", "maps.json"))
    qa = MapQAService()
    summary = []

    map_types = [args.map] if args.map else MAP_TYPES
    scales = [args.scale] if args.scale else SCALES
    for mt in map_types:
        for scale in scales:
            zoom = SCALE_ZOOM[scale]
            t0 = time.time()
            md = ms.generate_map(mt, "武汉市", zoom=zoom)
            runtime = round(time.time() - t0, 1)
            gm = md.get("generalization_metrics") or {}
            qa_report = qa.generate_report(md)
            effective_scale = gm.get("scale", scale)
            case_dir = os.path.join(OUT, f"{mt}_{effective_scale}")
            os.makedirs(case_dir, exist_ok=True)
            files = {
                "before.json": gm.get("before_counts", {}),
                "after.json": gm.get("after_counts", {}),
                "metrics.json": {
                    "map_load": gm.get("map_load"),
                    "data_loss": gm.get("data_loss"),
                    "recall": gm.get("recall"),
                    "topology": gm.get("topology"),
                    "gates": gm.get("gates"),
                    "blockers": gm.get("blockers"),
                    "final_duplicate_count": gm.get("final_duplicate_count"),
                    "stage_metrics": gm.get("stage_metrics"),
                    "scale": effective_scale,
                },
                "qa.json": qa_report,
                "runtime.json": {
                    "requested_scale": scale,
                    "effective_scale": effective_scale,
                    "zoom": zoom,
                    "runtime_seconds": runtime,
                    "layer_count": len(md.get("layers", [])),
                    "label_metrics": md.get("label_metrics"),
                },
            }
            for fname, data in files.items():
                with open(os.path.join(case_dir, fname), "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
            summary.append({
                "map_type": mt,
                "requested_scale": scale,
                "effective_scale": effective_scale,
                "runtime_seconds": runtime,
                "dataset_gate": (gm.get("gates") or {}).get("dataset_gate"),
                "generalization_gate": (gm.get("gates") or {}).get("generalization_gate"),
                "map_gate": (gm.get("gates") or {}).get("map_gate"),
                "category_recall": (gm.get("recall") or {}).get("category_recall"),
                "entity_recall": (gm.get("recall") or {}).get("entity_recall"),
                "overall_recall": (gm.get("recall") or {}).get("overall_recall"),
                "final_duplicate_count": gm.get("final_duplicate_count"),
                "map_load_score": (gm.get("map_load") or {}).get("map_load_score"),
                "qa_score": qa_report.get("total_score"),
                "grade": qa_report.get("grade"),
                "status": qa_report.get("status"),
                "critical_errors": qa_report.get("critical_errors"),
                "major_errors": qa_report.get("major_errors"),
                "minor_errors": qa_report.get("minor_errors"),
            })
            print(f"[OK] {mt} 1:{effective_scale} "
                  f"gate={ (gm.get('gates') or {}).get('generalization_gate')} "
                  f"dup={gm.get('final_duplicate_count')} "
                  f"recall={(gm.get('recall') or {}).get('overall_recall')} "
                  f"qa={qa_report.get('total_score')} {runtime}s", flush=True)
            ms.flush()

    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    ms.flush()
    print(f"\n输出: {OUT}（{len(summary)} 组）")
    print(f"{'map':<15}{'scale':>8}{'QA':>6}{'grade':>6}{'dup':>5}{'recall':>8}  gate")
    for s in summary:
        print(f"{s['map_type']:<15}{s['effective_scale']:>8}{s['qa_score']:>6}"
              f"{s['grade']:>6}{s['final_duplicate_count']:>5}"
              f"{s['overall_recall']:>8}  {s['generalization_gate']}")


if __name__ == "__main__":
    main()
