# -*- coding: utf-8 -*-
"""一键停止后端、前端与看门狗。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import process_utils  # noqa: E402


def stop_all():
    state = process_utils.read_state()
    for key in ("watchdog_pid", "backend_pid", "frontend_pid"):
        pid = state.get(key)
        if pid and process_utils.is_alive(pid):
            process_utils.stop_pid(pid)
            print(f"已停止 {key}: {pid}")
    process_utils.write_state({})
    print("全部进程已停止")


if __name__ == "__main__":
    stop_all()
