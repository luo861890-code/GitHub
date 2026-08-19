# -*- coding: utf-8 -*-
"""看门狗：每 15 秒检查后端/前端进程与端口健康，异常（退出或端口不可用）时自动重启。"""
import os
import socket
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import process_utils  # noqa: E402

PY = r"D:\python\py3.12.8\python.exe"
NODE = r"D:\node.js\node.exe"
NPM_CLI = r"D:\node.js\node_modules\npm\bin\npm-cli.js"
BACKEND_CWD = os.path.join(ROOT, "backend")
FRONTEND_CWD = os.path.join(ROOT, "frontend", "vue-app")

PORT_BACKEND = 8080
PORT_FRONTEND = 5173

# 进程启动后允许的服务就绪宽限期（秒）：后端含 LLM/知识图谱初始化，前端含 Vite 冷启动
BOOT_GRACE_SECONDS = 120


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 1.5) -> bool:
    """探测端口是否可连接（进程存活但 accept 挂死时端口会不可用）。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_service(state: dict, pid_key: str, boot_key: str, port: int):
    """检查服务健康，返回 (state, 健康, 原因)。

    进程不在 -> exited；端口可连 -> ok；
    端口不可用但处于启动宽限期（首次发现时开始计时） -> booting；
    端口不可用且超过宽限期 -> port-dead（需重启）。
    """
    pid = state.get(pid_key)
    boot_ts = state.get(boot_key) or 0
    if not pid or not process_utils.is_alive(pid):
        return state, False, "exited"
    if port_open(port):
        return state, True, "ok"
    if not boot_ts:
        # 首次发现端口未就绪：开始宽限计时，避免误杀刚启动的进程
        state[boot_key] = time.time()
        return state, True, "booting(0s)"
    elapsed = time.time() - boot_ts
    if elapsed < BOOT_GRACE_SECONDS:
        return state, True, f"booting({int(elapsed)}s)"
    return state, False, "port-dead"


def ensure_backend(state):
    pid = state.get("backend_pid")
    state, healthy, reason = check_service(state, "backend_pid", "backend_boot_ts", PORT_BACKEND)
    if healthy:
        return state
    if pid:
        print(f"[watchdog] 后端进程 {pid} 健康检查失败（{reason}），正在重启...")
        process_utils.stop_pid(pid)
    else:
        print("[watchdog] 后端进程不存在，正在启动...")
    new_pid = process_utils.spawn(
        [PY, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--log-level", "info"],
        BACKEND_CWD,
        os.path.join(BACKEND_CWD, "runtime", "server_out.log"),
        os.path.join(BACKEND_CWD, "runtime", "server_err.log"),
    )
    state["backend_pid"] = new_pid
    state["backend_boot_ts"] = time.time()
    print(f"[watchdog] 后端已重启: {new_pid}")
    return state


def ensure_frontend(state):
    pid = state.get("frontend_pid")
    state, healthy, reason = check_service(state, "frontend_pid", "frontend_boot_ts", PORT_FRONTEND)
    if healthy:
        return state
    if pid:
        print(f"[watchdog] 前端进程 {pid} 健康检查失败（{reason}），正在重启...")
        process_utils.stop_pid(pid)
    else:
        print("[watchdog] 前端进程不存在，正在启动...")
    new_pid = process_utils.spawn(
        [NODE, NPM_CLI, "run", "dev", "--", "--host", "127.0.0.1"],
        FRONTEND_CWD,
        os.path.join(FRONTEND_CWD, "dev.log"),
        os.path.join(FRONTEND_CWD, "dev.err.log"),
    )
    state["frontend_pid"] = new_pid
    state["frontend_boot_ts"] = time.time()
    print(f"[watchdog] 前端已重启: {new_pid}")
    return state


def main():
    print("[watchdog] 看门狗已启动")
    while True:
        try:
            state = process_utils.read_state()
            if not state:
                time.sleep(15)
                continue
            state = ensure_backend(state)
            state = ensure_frontend(state)
            process_utils.write_state(state)
        except Exception as e:  # noqa: BLE001
            print(f"[watchdog] 异常: {e}")
        time.sleep(15)


if __name__ == "__main__":
    main()
