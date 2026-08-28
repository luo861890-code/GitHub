# -*- coding: utf-8 -*-
"""补充武汉湖泊/POI/区县实体到 Neo4j（幂等 MERGE）"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")
from neo4j import GraphDatabase
from app.core.constants import WUHAN_GIS_POI, WUHAN_DISTRICTS

driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=("neo4j", "whu-2401"))

# 从地图数据读湖泊
md = json.load(open("D:/AAA-Study/work/github/carto-agent/data/maps/map_0014776b004f.json", encoding="utf-8"))
lake_layer = next(l for l in md["layers"] if l.get("name") == "湖泊（概览级）")
lakes = [(p.get("name"), p.get("area_km2")) for p in (lake_layer.get("properties") or []) if p.get("name")]

def add_landmark(s, name, ltype, lat=None, lng=None, area=None, source="map_data"):
    props = {"type": ltype, "source": source}
    if lat is not None: props["lat"] = lat
    if lng is not None: props["lng"] = lng
    if area is not None: props["area_km2"] = area
    s.run("MERGE (l:Landmark {name:$name}) SET l += $props", name=name, props=props)
    s.run("MATCH (c:City {name:'武汉市'}), (l:Landmark {name:$name}) MERGE (c)-[:HAS_LANDMARK]->(l)", name=name)

with driver.session() as s:
    # 1) 湖泊
    n_lake = 0
    for name, area in lakes:
        add_landmark(s, name, "lake", area=area)
        n_lake += 1
    # 2) POI
    n_poi = 0
    for p in WUHAN_GIS_POI:
        add_landmark(s, p["name"], p.get("type", "poi"), lat=p.get("lat"), lng=p.get("lng"), source="constants")
        n_poi += 1
    # 3) 区县 -> Location
    n_dist = 0
    for d in WUHAN_DISTRICTS:
        name = d if isinstance(d, str) else d.get("name")
        s.run("MERGE (l:Location {name:$name}) SET l.type='district', l.source='constants'", name=name)
        s.run("MATCH (c:City {name:'武汉市'}), (l:Location {name:$name}) MERGE (c)-[:CONTAINS]->(l)", name=name)
        n_dist += 1
    # 统计
    nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
    rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
    lands = s.run("MATCH (n:Landmark) RETURN count(n) AS c").single()["c"]
    locs = s.run("MATCH (n:Location) RETURN count(n) AS c").single()["c"]
    print(f"补充: 湖泊={n_lake} POI={n_poi} 区县={n_dist}")
    print(f"图谱: nodes={nodes} rels={rels} Landmark={lands} Location={locs}")
driver.close()
