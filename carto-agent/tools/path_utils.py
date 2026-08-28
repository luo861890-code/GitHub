# -*- coding: utf-8 -*-
"""启动/运维脚本的路径工具：从脚本位置推导仓库结构，优先使用 backend/.venv。

所有 tools/*.py 应通过本模块获取路径，避免硬编码绝对路径导致的可移植性问题。
支持环境变量覆盖：
  CARTO_PYTHON  - 指定 Python 可执行文件（或 "py" 启动器 + 版本）
  CARTO_NODE    - 指定 Node.js 可执行文件
"""
import os
import shutil
import sys

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def repo_root() -> str:
    return os.path.dirname(TOOLS_DIR)


def backend_dir() -> str:
    return os.path.join(repo_root(), "backend")


def frontend_dir() -> str:
    return os.path.join(repo_root(), "frontend", "vue-app")


def find_python() -> list:
    """返回用于启动后端的 Python 命令参数列表（优先 venv，支持 CARTO_PYTHON 覆盖）。"""
    override = os.environ.get("CARTO_PYTHON", "").strip()
    if override:
        return override.split()
    venv_py = os.path.join(backend_dir(), ".venv", "Scripts", "python.exe")
    if os.path.exists(venv_py):
        return [venv_py]
    # 回退：py 启动器优先选 3.12，其次当前解释器
    py_launcher = shutil.which("py")
    if py_launcher:
        return [py_launcher, "-3.12"]
    return [sys.executable]


def find_node() -> list:
    """返回用于启动前端的 Node/npm 命令。优先 npm.cmd（Windows）。"""
    override = os.environ.get("CARTO_NODE", "").strip()
    if override:
        return [override]
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm:
        return [npm]
    return ["npm"]


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path
