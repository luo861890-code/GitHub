# -*- coding: utf-8 -*-
"""导入制图知识语料到知识图谱（计划 1.3）

读取 data/kg/carto_knowledge_base.jsonl，逐条创建 CartographyRule 实体。
Neo4j 可用时写入图数据库；否则仅打印（内存模式）。

用法：python tools/import_carto_knowledge.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from app.services.kg_service import KGService  # noqa: E402


def main():
    path = os.path.join(ROOT, "data", "kg", "carto_knowledge_base.jsonl")
    if not os.path.exists(path):
        print(f"语料文件不存在: {path}")
        return 1
    kg = KGService()
    if kg.driver is None:
        print("Neo4j 未连接（内存模式），跳过写入；启动 Neo4j 后重试")
        return 0
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            try:
                kg.create_entity(
                    label=entry.get("label", "CartographyRule"),
                    properties={
                        "name": f"rule_{count}",
                        "content": entry.get("content", ""),
                        "category": entry.get("category", ""),
                        "source": entry.get("source", ""),
                    },
                )
                count += 1
            except Exception as e:
                print(f"导入失败: {e}")
    print(f"已导入 {count} 条制图规则")
    return 0


if __name__ == "__main__":
    sys.exit(main())
