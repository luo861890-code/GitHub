# -*- coding: utf-8 -*-
"""Phase 3.1 Generalization QA：GroundTruth recall / Topology gate / Benchmark / Terrain 等高距"""
import json
import os

from app.services.generalization.ground_truth import (
    EXPECTED_FEATURES, compute_recall, compute_all_recall,
)
from app.services.generalization.metrics import TopologyCheck
from app.services.generalization.terrain_scale_rules import contour_interval, select_contours


def test_expected_features_defined_for_four_types():
    for t in ("administrative", "traffic", "tourism", "terrain"):
        assert EXPECTED_FEATURES[t], t


def test_admin_districts_ground_truth_is_13():
    assert len(EXPECTED_FEATURES["administrative"]["districts"]) == 13


def test_recall_full_match():
    layers = [{"name": "x", "properties": [{"name": "a"}, {"name": "b"}]}]
    assert compute_recall("t", layers, "cat", ["a", "b"])["recall"] == 1.0


def test_recall_partial():
    layers = [{"properties": [{"name": "a"}]}]
    r = compute_recall("t", layers, "cat", ["a", "b"])
    assert r["recall"] == 0.5 and r["missed"] == ["b"]


def test_recall_empty_expected():
    assert compute_recall("t", [], "cat", [])["recall"] == 1.0


def test_recall_collects_feature_properties():
    layers = [{"features": [{"properties": {"name": "黄鹤楼"}}]}]
    assert compute_recall("tourism", layers, "core_attractions", ["黄鹤楼"])["recall"] == 1.0


def test_compute_all_recall_administrative():
    layers = [
        {"name": "武汉市域边界"},
        {"name": "区县政区", "features": [{"properties": {"name": n}}
                  for n in EXPECTED_FEATURES["administrative"]["districts"]]},
    ]
    r = compute_all_recall("administrative", layers)
    assert r["overall_recall"] == 1.0


def test_recall_terrain_index_contour():
    layers = [{"name": "等高线（计曲线）"}]
    assert compute_recall("terrain", layers, "index_contours", ["等高线（计曲线）"])["recall"] == 1.0


def test_recall_traffic_bridge():
    layers = [{"name": "主要桥梁"}]
    assert compute_recall("traffic", layers, "bridges", ["主要桥梁"])["recall"] == 1.0


def test_recall_tourism_from_landmarks():
    from app.core.constants import WUHAN_LANDMARKS
    names = [l["name"] for l in WUHAN_LANDMARKS]
    layers = [{"properties": [{"name": n} for n in names]}]
    r = compute_recall("tourism", layers, "core_attractions",
                       EXPECTED_FEATURES["tourism"]["core_attractions"])
    assert r["recall"] >= 0.5


def _poly(ring):
    return {"type": "Polygon", "coordinates": [ring]}


def test_topology_polygons_no_overlap():
    tc = TopologyCheck()
    a = _poly([[114.30, 30.55], [114.31, 30.55], [114.31, 30.56], [114.30, 30.55]])
    b = _poly([[114.32, 30.55], [114.33, 30.55], [114.33, 30.56], [114.32, 30.55]])
    assert tc.check_polygons([a, b])["significant_overlap_count"] == 0


def test_topology_polygons_overlap():
    tc = TopologyCheck()
    a = _poly([[114.30, 30.55], [114.32, 30.55], [114.32, 30.57], [114.30, 30.55]])
    b = _poly([[114.31, 30.56], [114.33, 30.56], [114.33, 30.58], [114.31, 30.56]])
    assert tc.check_polygons([a, b])["significant_overlap_count"] >= 1


def test_topology_polygons_invalid():
    tc = TopologyCheck()
    bad = {"type": "Polygon", "coordinates": [[[114.30, 30.55], [114.31, 30.55]]]}
    assert tc.check_polygons([bad])["invalid_count"] >= 1


def test_topology_line_components():
    tc = TopologyCheck()
    lines = [[(114.30, 30.55), (114.31, 30.55)], [(114.40, 30.55), (114.41, 30.55)]]
    assert tc.check_line_connectivity(lines)["components"] == 2


def test_topology_dangling():
    tc = TopologyCheck()
    lines = [[(114.30, 30.55), (114.31, 30.55)]]
    assert tc.check_line_connectivity(lines)["dangling_endpoints"] == 2


def test_topology_duplicate_lines():
    tc = TopologyCheck()
    lines = [[(114.30, 30.55), (114.31, 30.55)], [(114.30, 30.55), (114.31, 30.55)]]
    assert tc.check_duplicate_lines(lines) == 1


def test_topology_poi_containment():
    tc = TopologyCheck()
    poly = _poly([[114.30, 30.55], [114.32, 30.55], [114.32, 30.57], [114.30, 30.55]])
    assert tc.check_poi_containment([(114.31, 30.56)], [poly])["outside_polygons"] == 0
    assert tc.check_poi_containment([(114.40, 30.60)], [poly])["outside_polygons"] == 1


def test_topology_contour_validity():
    tc = TopologyCheck()
    assert tc.check_contour_validity([[(114.3, 30.5), (114.31, 30.5)]])["invalid_contours"] == 0
    assert tc.check_contour_validity([[(114.3, 30.5)]])["invalid_contours"] == 1


def test_gate_pass():
    assert TopologyCheck().gate({})["status"] == "PASS"


def test_gate_fail_overlap():
    assert TopologyCheck().gate({"polygons": {"overlap_count": 1}})["status"] == "FAIL"


def test_gate_fail_poi_outside():
    assert TopologyCheck().gate({"poi": {"outside_polygons": 1}})["status"] == "FAIL"


# ==================== Terrain 等高距 ====================

def test_contour_interval_scale_decreases():
    assert contour_interval(500_000, 30, 100) > contour_interval(100_000, 30, 100)


def test_contour_interval_multiple_of_20():
    for s in (500_000, 250_000, 100_000):
        assert contour_interval(s, 30, 100) % 20 == 0


def test_contour_interval_relief_increases():
    assert contour_interval(100_000, 30, 700) >= contour_interval(100_000, 30, 50)


def test_contour_interval_capped():
    assert contour_interval(500_000, 30, 1000) <= 100


def test_contour_interval_min_20():
    assert contour_interval(25_000, 30, 10) >= 20


def test_select_contours_keeps_interval():
    kept, removed, _ = select_contours([20, 40, 60, 80, 100, 120, 140], 40)
    assert set(kept) == {40, 80, 120}
    assert len(removed) == 4


def test_select_contours_reason():
    _, _, reason = select_contours([20, 40, 60], 40)
    assert "等高距" in reason and "保留" in reason


def test_contour_interval_250k():
    assert contour_interval(250_000, 30, 100) == 40


def test_contour_interval_relief_tiers():
    low = contour_interval(100_000, 30, 50)
    high = contour_interval(100_000, 30, 700)
    assert high >= low


# ==================== Benchmark ====================

def _benchmark_root():
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "benchmarks", "wuhan", "generalization")


def test_benchmark_summary_exists():
    root = _benchmark_root()
    assert os.path.isdir(root)
    summary = os.path.join(root, "summary.json")
    assert os.path.exists(summary)
    with open(summary, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) >= 4


def test_benchmark_case_files():
    root = _benchmark_root()
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    assert len(dirs) >= 4
    case = os.path.join(root, dirs[0])
    for fname in ("before.json", "after.json", "metrics.json", "qa.json"):
        assert os.path.exists(os.path.join(case, fname)), fname


def test_benchmark_metrics_structure():
    root = _benchmark_root()
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    with open(os.path.join(root, dirs[0], "metrics.json"), encoding="utf-8") as f:
        m = json.load(f)
    for k in ("recall", "topology", "map_load", "data_loss"):
        assert k in m


def test_benchmark_qa_structure():
    root = _benchmark_root()
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    with open(os.path.join(root, dirs[0], "qa.json"), encoding="utf-8") as f:
        q = json.load(f)
    assert "total_score" in q and "dimensions" in q


def test_benchmark_before_after_counts():
    root = _benchmark_root()
    dirs = [d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))]
    case = os.path.join(root, dirs[0])
    with open(os.path.join(case, "before.json"), encoding="utf-8") as f:
        before = json.load(f)
    with open(os.path.join(case, "after.json"), encoding="utf-8") as f:
        after = json.load(f)
    assert "features" in before and "features" in after
