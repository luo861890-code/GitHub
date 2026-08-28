# -*- coding: utf-8 -*-
"""一键启动后端 + 前端，并可选启动看门狗自动重启。

用法：
    python tools/start_all.py            # 启动前后端
    python tools/start_all.py --watch    # 启动前后端并附带看门狗
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import path_utils  # noqa: E402
import process_utils  # noqa: E402

BACKEND_CWD = path_utils.backend_dir()
FRONTEND_CWD = path_utils.frontend_dir()
PY = path_utils.find_python()
NPM = path_utils.find_node()


def start_all(with_watch: bool = False):
    state = process_utils.read_state()
    # 若已有存活进程，先停掉避免端口冲突
    for key in ("backend_pid", "frontend_pid"):
        pid = state.get(key)
        if pid and process_utils.is_alive(pid):
            process_utils.stop_pid(pid)
            print(f"已停止旧进程 {key}: {pid}")

    backend_pid = process_utils.spawn(
        PY + ["-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"],
        BACKEND_CWD,
        os.path.join(BACKEND_CWD, "runtime", "server_out.log"),
        os.path.join(BACKEND_CWD, "runtime", "server_err.log"),
    )
    frontend_pid = process_utils.spawn(
        NPM + ["run", "dev", "--", "--host", "127.0.0.1"],
        FRONTEND_CWD,
        os.path.join(FRONTEND_CWD, "dev.log"),
        os.path.join(FRONTEND_CWD, "dev.err.log"),
    )

    process_utils.write_state({
        "backend_pid": backend_pid,
        "frontend_pid": frontend_pid,
        "watchdog_pid": None,
        "started_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
    })
    print(f"后端 PID: {backend_pid}  -> http://localhost:8080")
    print(f"前端 PID: {frontend_pid}  -> http://127.0.0.1:5173")

    if with_watch:
        watchdog_pid = process_utils.spawn(
            [PY, os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchdog.py")],
            ROOT,
            os.path.join(BACKEND_CWD, "runtime", "watchdog_out.log"),
            os.path.join(BACKEND_CWD, "runtime", "watchdog_err.log"),
        )
        state = process_utils.read_state()
        state["watchdog_pid"] = watchdog_pid
        process_utils.write_state(state)
        print(f"看门狗 PID: {watchdog_pid}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键启动 CartoAgent 前后端")
    parser.add_argument("--watch", action="store_true", help="附带看门狗自动重启")
    args = parser.parse_args()
    start_all(with_watch=args.watch)
