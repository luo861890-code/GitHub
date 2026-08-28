# -*- coding: utf-8 -*-
"""分离式启动 carto-agent 后端服务（无窗口、脱离会话，禁用 reload 以保证稳定）。

路径自动推导，Python 优先使用 backend/.venv（可通过 CARTO_PYTHON 覆盖）。
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import path_utils

backend = path_utils.backend_dir()
runtime = path_utils.ensure_dir(os.path.join(backend, "runtime"))
py_cmd = path_utils.find_python()
port = os.environ.get("PORT", "8080")
host = os.environ.get("HOST", "0.0.0.0")

out = open(os.path.join(runtime, "server_out.log"), "wb", buffering=0)
err = open(os.path.join(runtime, "server_err.log"), "wb", buffering=0)
CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | 0x00000200
env = dict(os.environ)
env["PYTHONUNBUFFERED"] = "1"

cmd = py_cmd + ["-m", "uvicorn", "app.main:app",
                "--host", host, "--port", port, "--log-level", "info"]
p = subprocess.Popen(
    cmd, cwd=backend, stdout=out, stderr=err,
    creationflags=CREATE_NO_WINDOW | DETACHED, close_fds=True, env=env,
)
with open(os.path.join(runtime, "server.pid"), "w") as f:
    f.write(str(p.pid))
print("server pid:", p.pid, "| port:", port)
