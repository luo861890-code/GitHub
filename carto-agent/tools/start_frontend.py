# -*- coding: utf-8 -*-
"""以无窗口方式启动前端 Vite 开发服务器（默认 http://127.0.0.1:5173）

用法：python tools/start_frontend.py
生成 frontend/vue-app/dev.pid 供停止/排查。
"""
import os
import subprocess

frontend = r"D:\AAA-Study\work\github\carto-agent\frontend\vue-app"
node = r"D:\node.js\node.exe"
npm_cli = r"D:\node.js\node_modules\npm\bin\npm-cli.js"

CREATE_NO_WINDOW = 0x08000000
DETACHED = 0x00000008 | 0x00000200

env = dict(os.environ)
for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    env.pop(k, None)
env["PYTHONUNBUFFERED"] = "1"

out = open(os.path.join(frontend, "dev.log"), "wb", buffering=0)
err = open(os.path.join(frontend, "dev.err.log"), "wb", buffering=0)
p = subprocess.Popen(
    [node, npm_cli, "run", "dev", "--", "--host", "127.0.0.1"],
    cwd=frontend,
    stdout=out,
    stderr=err,
    creationflags=CREATE_NO_WINDOW | DETACHED,
    close_fds=True,
    env=env,
)
with open(os.path.join(frontend, "dev.pid"), "w", encoding="utf-8") as f:
    f.write(str(p.pid))
print("frontend pid:", p.pid)
