# -*- coding: utf-8 -*-
"""以无代理方式启动后端（清除代理环境变量，保证 OSM 抓取可用）。

路径自动从脚本位置推导，Python 优先使用 backend/.venv（可通过 CARTO_PYTHON 覆盖）。
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
for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    env.pop(k, None)
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
