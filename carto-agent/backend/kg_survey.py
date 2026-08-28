# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase
d = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=("neo4j", "whu-2401"))
with d.session() as s:
    labels = s.run("MATCH (n) RETURN labels(n)[0] AS l, count(n) AS c ORDER BY c DESC").values()
    print("=== 标签分布 ===")
    for l, c in labels:
        print(f"  {l}: {c}")
    rules = s.run("MATCH (n) WHERE n.question IS NOT NULL RETURN n.name AS name ORDER BY n.name").values()
    names = [r[0] for r in rules]
    print("=== 规则总数:", len(names))
    print("=== 主题关键词覆盖检查 ===")
    for kw in ["等高线","地貌","地形图","遥感","影像","电子地图","WebGIS","瓦片","分幅","编号","图式","基准面","椭球","图集","量算","坡度","DEM","分层设色","晕渲","视觉变量","符号学","注记字体","要素分类","定向","磁偏","配置","地图语言","制图专家","地貌表示","专题","误差","精度","地图概括","感受","图形","视知觉","格式塔"]:
        hit = [n for n in names if kw in n]
        print(f"  [{kw}]: " + ("有 " + str(len(hit)) if hit else "缺"))
d.close()
