# -*- coding: utf-8 -*-
"""一键数据流水线（计划 0.5）：依次执行本地地理数据准备脚本"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import path_utils

ROOT = path_utils.repo_root()
SCRIPTS = os.path.join(path_utils.backend_dir(), "scripts")
PY = path_utils.find_python()

STEPS = [
    ("prepare_local_data.py", "本地行政区划/旅游/轨道数据准备"),
    ("prepare_local_geo.py", "本地水系/路网数据准备"),
    ("clean_water_data.py", "水系数据清洗（去重/合并/规范化）"),
    ("optimize_geo_data.py", "几何数据优化（Douglas-Peucker 化简）"),
]


def main():
    for script, desc in STEPS:
        path = os.path.join(SCRIPTS, script)
        if not os.path.exists(path):
            print(f"[跳过] {script} 不存在")
            continue
        print(f"[运行] {desc} ({script})")
        code = subprocess.call(PY + [path])
        if code != 0:
            print(f"[失败] {script} 退出码 {code}")
            return code
    print("数据流水线完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
