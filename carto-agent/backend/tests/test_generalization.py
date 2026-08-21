# -*- coding: utf-8 -*-
"""GeneralizationEngine 测试：scale-aware、selection、simplification、aggregation、
displacement、collapse、exaggeration、metrics、四类真实武汉地图"""
import os

from app.services.generalization import GeneralizationEngine, get_scale_rule, SCALES
from app.services.generalization.selection import Selection, road_importance
from app.services.generalization.aggregation import Aggregation
from app.services.generalization.displacement import Displacement
from app.services.generalization.metrics import MapLoadMetrics, ImportantFeatureRecall, DataLossMetrics


def _engine():
    return GeneralizationEngine()


# ==================== ScaleRule ====================

def test_six_scales_defined():
    assert len(SCALES) == 6
    assert 1_000_000 in SCALES and 25_000 in SCALES


def test_tolerance_decreases_with_scale():
    assert get_scale_rule(1_000_000).tolerance_m("motorway") > get_scale_rule(100_000).tolerance_m("motorway")
    assert get_scale_rule(100_000).tolerance_m("motorway") > get_scale_rule(25_000).tolerance_m("motorway")


def test_tolerance_varies_by_feature_class():
    r = get_scale_rule(100_000)
    assert r.tolerance_m("contour_minor") > r.tolerance_m("motorway")
    assert r.tolerance_m("riverline") < r.tolerance_m("contour_minor")


def test_aggregation_distance_scales():
    assert get_scale_rule(1_000_000).aggregation_distance_m("poi") > get_scale_rule(100_000).aggregation_distance_m("poi")


def test_displacement_distance_scales():
    assert get_scale_rule(250_000).displacement_distance_m("road") > get_scale_rule(25_000).displacement_distance_m("road")


# ==================== Selection ====================

def test_road_importance_highway_over_residential():
    assert road_importance("motorway", 10000, 5) > road_importance("residential", 10000, 5)


def test_select_features_by_importance():
    sel = Selection(get_scale_rule(100_000))
    items = [{"id": i, "importance": i / 10.0} for i in range(10)]
    kept = sel.select_features(items, budget=5, importance_key="importance")
    assert len(kept) == 5
    assert max(k["importance"] for k in kept) >= 0.9


def test_budget_minor_road_scale():
    sel = Selection(get_scale_rule(1_000_000))
    assert sel.budget_for_scale("minor_road", 100) == 0
    sel = Selection(get_scale_rule(25_000))
    assert sel.budget_for_scale("minor_road", 100) == 100


def test_select_pois_keeps_high_importance():
    sel = Selection(get_scale_rule(100_000))
    pois = [{"importance": 0.2}, {"importance": 0.9}, {"importance": 0.5}]
    kept, removed = sel.select_pois(pois, budget=2)
    assert len(kept) == 2
    assert any(p["importance"] == 0.9 for p in kept)
    assert all(p["importance"] < 0.9 for p in removed)


# ==================== Simplification ====================

def test_simplify_reduces_vertices():
    e = _engine()
    line = [(114.30, 30.55)]
    for i in range(1, 20):
        line.append((114.30 + i * 0.0003, 30.55 + (0.000004 if i % 2 else -0.000004)))
    out = e.crs.simplify_meters(line, 15.0)
    assert len(out) < len(line)


def test_simplify_preserves_endpoints():
    e = _engine()
    line = [(114.30, 30.55), (114.31, 30.56), (114.32, 30.55)]
    out = e.crs.simplify_meters(line, 200.0)
    assert abs(out[0][0] - line[0][0]) < 1e-9
    assert abs(out[-1][0] - line[-1][0]) < 1e-9


def test_simplify_length_change_small():
    e = _engine()
    line = [(114.30, 30.55)]
    for i in range(1, 50):
        line.append((114.30 + i * 0.0001, 30.55 + (0.000002 if i % 2 else -0.000002)))
    before = e.crs.length_meters(line)
    after = e.crs.length_meters(e.crs.simplify_meters(line, 10.0))
    assert abs((after - before) / before) < 0.05


def test_larger_tolerance_more_simplification():
    e = _engine()
    line = [(114.30, 30.55)]
    for i in range(1, 30):
        line.append((114.30 + i * 0.0004, 30.55 + (0.000005 if i % 2 else -0.000005)))
    s10 = e.crs.simplify_meters(line, 10.0)
    s50 = e.crs.simplify_meters(line, 50.0)
    assert len(s50) <= len(s10)


# ==================== Aggregation ====================

def test_linemerge_by_name():
    agg = Aggregation()
    geoms = [
        {"type": "LineString", "coordinates": [[114.30, 30.55], [114.31, 30.55]]},
        {"type": "LineString", "coordinates": [[114.31, 30.55], [114.32, 30.55]]},
    ]
    out = agg.merge_linestrings_by_name(geoms, ["长江", "长江"])
    assert len(out) == 1
    assert len(out[0]["coordinates"]) >= 3


def test_cluster_points_reduces_count():
    agg = Aggregation()
    pts = [(114.30 + i * 0.0002, 30.55) for i in range(20)]
    clusters = agg.cluster_points(pts, 200.0)
    assert len(clusters) < len(pts)
    assert all(c["member_count"] >= 1 for c in clusters)


def test_larger_distance_fewer_clusters():
    agg = Aggregation()
    pts = [(114.30 + i * 0.001, 30.55) for i in range(20)]
    c_small = agg.cluster_points(pts, 100.0)
    c_large = agg.cluster_points(pts, 1000.0)
    assert len(c_large) <= len(c_small)


# ==================== Displacement ====================

def test_displace_changes_secondary_line():
    d = Displacement()
    primary = [(114.30, 30.55), (114.31, 30.55)]
    secondary = [(114.30, 30.5505), (114.31, 30.5505)]
    displaced = d.displace(primary, secondary, 200.0)
    assert displaced != secondary


def test_displace_increases_separation():
    d = Displacement()
    primary = [(114.30, 30.55), (114.31, 30.55)]
    secondary = [(114.30, 30.5505), (114.31, 30.5505)]
    displaced = d.displace(primary, secondary, 500.0)
    from shapely.geometry import LineString
    before = LineString(d.crs.to_projected(secondary)).distance(LineString(d.crs.to_projected(primary)))
    after = LineString(d.crs.to_projected(displaced)).distance(LineString(d.crs.to_projected(primary)))
    assert after > before


def test_resolve_parallel_primary_untouched():
    d = Displacement()
    lines = [
        {"coordinates": [(114.30, 30.55), (114.31, 30.55)], "importance": 1.0},
        {"coordinates": [(114.30, 30.5505), (114.31, 30.5505)], "importance": 0.5},
    ]
    out = d.resolve_parallel(lines, 200.0)
    assert out[0]["coordinates"] == lines[0]["coordinates"]


# ==================== Collapse / Exaggeration ====================

def test_collapse_small_polygon():
    from app.services.generalization.collapse import Collapse
    c = Collapse()
    small = {"type": "Polygon", "coordinates": [[[114.30, 30.55], [114.3001, 30.55],
                                                  [114.3001, 30.5501], [114.30, 30.55]]]}
    assert c.should_collapse(small, 100_000.0)
    pt = c.collapse_to_point(small)
    assert pt["type"] == "Point"


def test_no_collapse_large_polygon():
    from app.services.generalization.collapse import Collapse
    c = Collapse()
    big = {"type": "Polygon", "coordinates": [[[114.30, 30.55], [114.32, 30.55],
                                               [114.32, 30.57], [114.30, 30.55]]]}
    assert not c.should_collapse(big, 100_000.0)


def test_exaggeration_keeps_small_polygon():
    from app.services.generalization.exaggeration import Exaggeration
    e = Exaggeration()
    small = {"type": "Polygon", "coordinates": [[[114.30, 30.55], [114.3001, 30.55],
                                                 [114.3001, 30.5501], [114.30, 30.55]]]}
    r = e.min_area_protect(small, 1_000_000.0)
    assert r["keep"] is True and r["exaggerated"] is True


# ==================== Metrics ====================

def test_map_load_metrics_fields():
    ml = MapLoadMetrics()
    layers = [{"type": "circleMarker", "coordinates": [[30.55, 114.30], [30.56, 114.31]]},
              {"type": "polyline", "coordinates": [[[30.55, 114.30], [30.56, 114.31]]]}]
    r = ml.compute(layers)
    for k in ("point_density", "line_density", "polygon_density", "label_density", "collision_density", "map_load_score"):
        assert k in r
    assert 0 <= r["map_load_score"] <= 100


def test_important_feature_recall():
    rec = ImportantFeatureRecall().compute(["a", "b", "c"], ["a", "b", "c", "d"])
    assert rec["recall"] == 0.75
    assert rec["missed"] == ["d"]


def test_data_loss_metrics():
    dl = DataLossMetrics().compute(100, 90, 1000, 800, 10000, 9000, 5000, 5000)
    assert dl["feature_loss_rate"] == 0.1
    assert dl["vertex_loss_rate"] == 0.2
    assert dl["length_change"] == -0.1


def test_topology_no_overlap():
    from app.services.generalization.metrics import TopologyCheck
    tc = TopologyCheck()
    polys = [{"type": "Polygon", "coordinates": [[[114.30, 30.55], [114.31, 30.55],
                                                   [114.31, 30.56], [114.30, 30.55]]]},
             {"type": "Polygon", "coordinates": [[[114.32, 30.55], [114.33, 30.55],
                                                   [114.33, 30.56], [114.32, 30.55]]]}]
    assert tc.check_polygons(polys)["significant_overlap_count"] == 0


# ==================== Engine 集成（真实武汉地图） ====================

def test_engine_four_map_types_no_error():
    from app.services.map_service import MapService
    ms = MapService(persist_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "maps.json"))
    for mt, z, scale in [("administrative", 10, 100_000), ("traffic", 12, 100_000),
                         ("tourism", 12, 100_000), ("terrain", 11, 100_000)]:
        md = ms.generate_map(mt, "武汉市", zoom=z)
        gm = md.get("generalization_metrics") or {}
        assert "error" not in gm
        assert "map_load" in gm and "data_loss" in gm


def test_engine_administrative_recall_100():
    from app.services.map_service import MapService
    ms = MapService(persist_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "maps.json"))
    md = ms.generate_map("administrative", "武汉市", zoom=10)
    gm = md.get("generalization_metrics") or {}
    # 行政区 recall：districts（13 区）+ city_boundary（市界）均 1.0
    assert gm["recall"]["districts"]["recall"] == 1.0
    assert gm["recall"]["city_boundary"]["recall"] == 1.0


def test_engine_traffic_feature_loss_reasonable():
    from app.services.map_service import MapService
    ms = MapService(persist_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "maps.json"))
    md = ms.generate_map("traffic", "武汉市", zoom=12)
    gm = md.get("generalization_metrics") or {}
    assert gm["data_loss"]["feature_loss_rate"] <= 0.2


def test_engine_tourism_clusters():
    from app.services.map_service import MapService
    ms = MapService(persist_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "maps.json"))
    md = ms.generate_map("tourism", "武汉市", zoom=12)
    # 存在被聚类的 POI 图层
    assert any("cluster_count" in l for l in md["layers"])


# ==================== 负例 ====================

def test_negative_empty_layers():
    e = _engine()
    result = e.generalize("traffic", [], 100_000)
    assert result["layers"] == []


def test_negative_empty_coords():
    e = _engine()
    layer = {"name": "道路-高速公路主线", "type": "polyline", "coordinates": []}
    out = e._generalize_roads(layer, "motorway", get_scale_rule(100_000))
    assert out["coordinates"] == []


def test_negative_invalid_scale_matches_nearest():
    r = get_scale_rule(123_456)
    assert r.scale_denominator in SCALES


def test_negative_invalid_geometry_no_crash():
    e = _engine()
    layer = {"name": "湖泊", "type": "polygon", "coordinates": [[[114.30, 30.55]]]}  # 不足 4 点
    out = e._generalize_polygons(layer, "water", get_scale_rule(100_000))
    assert "coordinates" in out
