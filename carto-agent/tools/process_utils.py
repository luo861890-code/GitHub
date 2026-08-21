# -*- coding: utf-8 -*-
"""进程管理公共工具：无窗口派生子进程、读写进程状态文件、存活检测。"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "backend", "runtime", "processes.json")

CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | 0x00000200


def clean_env():
    env = dict(os.environ)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(k, None)
    env["PYTHONUNBUFFERED"] = "1"
    return env


def spawn(cmd, cwd, out_path, err_path):
    """无窗口后台启动进程，返回 PID。"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out = open(out_path, "wb", buffering=0)
    err = open(err_path, "wb", buffering=0)
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=out,
        stderr=err,
        creationflags=CREATE_NO_WINDOW | DETACHED,
        close_fds=True,
        env=clean_env(),
    )
    return proc.pid


def read_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def write_state(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def is_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )
        return f"{pid}" in result.stdout and "没有运行的任务" not in result.stdout and "No tasks" not in result.stdout
    except Exception:
        return False


def stop_pid(pid: int) -> bool:
    if not pid:
        return False
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=10,
        )
        return True
    except Exception:
        return False
