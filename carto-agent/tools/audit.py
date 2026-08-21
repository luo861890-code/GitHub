# -*- coding: utf-8 -*-
"""专家验收模式：carto-agent audit --map traffic --scale 100000

输出 Data QA / Topology / Generalization / Symbols / Labels / Theme / Layout / Facts 评分表。
"""
import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.map_service import MapService  # noqa: E402
from app.services.qa import MapQAService  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="CartoAgent 专家验收")
    parser.add_argument("--map", default="traffic", help="administrative/traffic/tourism/terrain")
    parser.add_argument("--scale", type=int, default=100000, help="比例尺分母")
    args = parser.parse_args()

    zoom = {500000: 8, 250000: 10, 100000: 12, 25000: 14}.get(args.scale, 12)
    ms = MapService(persist_path=os.path.join(ROOT, "data", "maps.json"))
    md = ms.generate_map(args.map, "武汉市", zoom=zoom)
    gm = md.get("generalization_metrics") or {}
    qa = MapQAService().generate_report(md)

    print("=" * 50)
    print(f"CartoAgent Map Audit: {md.get('name')}  1:{args.scale}")
    print("=" * 50)
    dims = qa.get("dimensions", {})
    name_map = {
        "data_quality": "Data QA", "completeness": "Completeness", "topology": "Topology",
        "multi_source": "Multi-source", "generalization": "Generalization",
        "symbol_visual": "Symbols", "label": "Labels", "thematic": "Theme",
        "layout": "Layout", "fact": "Facts",
    }
    for key, label in name_map.items():
        d = dims.get(key, {})
        print(f"{label:<16} {d.get('score', 0):>4} / {d.get('max', 0)}")
    total = qa.get("total_score", 0)
    print(f"\nTOTAL {total}/1000  Grade {qa.get('grade')}  Status {qa.get('status')}")
    print(f"Critical {qa.get('critical_errors', 0)}  Major {qa.get('major_errors', 0)}  "
          f"Minor {qa.get('minor_errors', 0)}")
    if gm:
        print(f"exact_dup {gm.get('final_duplicate_count')}  "
              f"cat_recall {gm.get('recall', {}).get('category_recall')}  "
              f"ent_recall {gm.get('recall', {}).get('entity_recall')}  "
              f"gate {gm.get('gates', {}).get('generalization_gate')}")
    print("=" * 50)


if __name__ == "__main__":
    main()
