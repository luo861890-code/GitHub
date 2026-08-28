# -*- coding: utf-8 -*-
"""将 Neo4j 图谱中的全部制图知识规则同步进 RAG 知识库（cartography_kb.json），提升知识问答双通道覆盖（幂等）"""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
from neo4j import GraphDatabase

KB_PATH = "../data/kg/cartography_kb.json"
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "whu-2401")
driver = GraphDatabase.driver(URI, auth=AUTH)

# 制图术语词典：用于从 question/answer 提取检索关键词
TERMS = [
    "等高线", "地形图", "分层设色", "晕渲", "地貌", "DEM", "坡度", "坡向", "遥感", "影像",
    "电子地图", "WebGIS", "瓦片", "矢量切片", "LOD", "分幅", "图幅", "编号", "图式", "图例",
    "投影", "椭球", "基准面", "高斯", "墨卡托", "圆锥", "变形", "中央经线", "分带",
    "视觉变量", "符号", "符号学", "注记", "字体", "字号", "字隔", "配色", "色彩", "色相",
    "综合", "取舍", "简化", "合并", "移位", "专题", "分级", "等值线", "点值", "范围法", "动线法",
    "拓扑", "属性", "字段", "坐标", "EPSG", "WGS84", "捕捉", "顶点", "编辑", "撤销",
    "比例尺", "缩放", "详细程度", "制图", "地图", "交通图", "旅游图", "校园图", "行政区划图",
    "量算", "精度", "现势", "误差", "插值", "克里金", "Voronoi", "Delaunay", "栅格", "矢量",
    "GeoJSON", "Shapefile", "GeoPackage", "地图集", "指北针", "磁偏", "定向", "经纬网",
    "图层", "渲染", "交互", "抽稀", "压盖", "避让", "优先级", "视觉变量", "图面", "整饰",
]

def extract_keywords(question, answer):
    kws = []
    text = question + answer
    for t in TERMS:
        if t in text and t not in kws:
            kws.append(t)
    # 补充 question 中的短词（长度 2-4，非停用）
    import re
    for seg in re.findall(r"[\u4e00-\u9fff]{2,4}", question):
        if len(seg) >= 2 and seg not in kws and seg not in ("哪些", "如何", "怎么", "是什么", "有哪些", "原则", "要点", "方法", "规则", "应该", "多少", "什么", "怎样"):
            kws.append(seg)
        if len(kws) >= 10:
            break
    return kws

def run():
    # 1) 从图谱读取全部规则
    rules = []
    with driver.session() as s:
        rows = s.run(
            "MATCH (n) WHERE n.question IS NOT NULL "
            "RETURN n.name AS name, n.question AS question, n.answer AS answer, "
            "n.category AS category, labels(n)[0] AS label ORDER BY n.name"
        ).values()
        for name, question, answer, category, label in rows:
            rules.append({"id": name, "question": question, "answer": answer,
                          "category": category or label or "制图学", "label": label})
    print(f"图谱规则共 {len(rules)} 条")

    # 2) 合并进 RAG 知识库
    with open(KB_PATH, encoding="utf-8") as f:
        kb = json.load(f)
    existing_ids = {k["id"] for k in kb}
    added = 0
    for r in rules:
        if r["id"] in existing_ids:
            continue
        kb.append({
            "id": r["id"],
            "category": r["category"],
            "question": r["question"],
            "answer": r["answer"],
            "keywords": extract_keywords(r["question"], r["answer"]),
        })
        existing_ids.add(r["id"])
        added += 1
    with open(KB_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)
    print(f"RAG 知识库新增 {added} 条，现有 {len(kb)} 条")
    print(f"图谱知识覆盖率: {added} 条图谱规则已同步，剩余未同步: {len(rules) - added}")
    driver.close()

run()
