"""内嵌后端服务器管理

在独立线程中启动 FastAPI/uvicorn，桌面窗口通过 HTTP 与后端通信。
启动完成后通过 callback 通知前端可以加载页面。
"""
import os
import sys
import threading
import time
import logging
from typing import Callable, Optional

logger = logging.getLogger("carto-agent.desktop.server")


class BackendServer:
    """内嵌后端服务器管理器

    负责：
    1. 注入桌面模式的环境变量（数据目录、端口等）
    2. 在子线程中启动 uvicorn
    3. 等待服务就绪（健康检查轮询）
    4. 优雅关闭
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8765,
        data_dir: Optional[str] = None,
        ready_callback: Optional[Callable[[], None]] = None,
        error_callback: Optional[Callable[[str], None]] = None,
    ):
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.ready_callback = ready_callback
        self.error_callback = error_callback
        self._server_thread: Optional[threading.Thread] = None
        self._uvicorn_config = None
        self._server = None
        self._running = False
        self._ready = False

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def is_ready(self) -> bool:
        return self._ready

    def start(self) -> None:
        """启动后端服务器（非阻塞，在后台线程运行）"""
        if self._running:
            return

        self._running = True
        self._server_thread = threading.Thread(
            target=self._run_server,
            name="carto-backend",
            daemon=True,
        )
        self._server_thread.start()

        # 启动就绪检测线程
        threading.Thread(
            target=self._wait_for_ready,
            name="carto-ready-check",
            daemon=True,
        ).start()

    def _run_server(self) -> None:
        """在子线程中运行 uvicorn"""
        try:
            # 注入桌面模式环境变量
            os.environ["HOST"] = self.host
            os.environ["PORT"] = str(self.port)
            os.environ["DEBUG"] = "false"
            if self.data_dir:
                os.environ["DATA_DIR"] = self.data_dir

            # 确保后端代码在路径中
            # server.py 位于 <project>/desktop/server.py
            # 上一级 = 项目根
            project_root = os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))
            )
            backend_dir = os.path.join(project_root, "backend")
            if backend_dir not in sys.path:
                sys.path.insert(0, backend_dir)

            import uvicorn
            from uvicorn.config import Config

            self._uvicorn_config = Config(
                "app.main:app",
                host=self.host,
                port=self.port,
                log_level="info",
                reload=False,
                workers=1,
            )
            self._server = uvicorn.Server(self._uvicorn_config)
            logger.info("启动后端服务: %s", self.base_url)
            self._server.run()

        except Exception as e:
            logger.exception("后端服务启动失败")
            if self.error_callback:
                self.error_callback(str(e))
            self._running = False

    def _wait_for_ready(self) -> None:
        """轮询健康检查接口，等待服务就绪"""
        import urllib.request
        max_wait = 60  # 最多等 60 秒
        interval = 0.5
        waited = 0.0

        while waited < max_wait and self._running:
            try:
                req = urllib.request.Request(f"{self.base_url}/health")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    if resp.status == 200:
                        self._ready = True
                        logger.info("后端服务就绪 (%.1fs)", waited)
                        if self.ready_callback:
                            self.ready_callback()
                        return
            except Exception:
                pass
            time.sleep(interval)
            waited += interval

        logger.warning("后端服务就绪超时 (%.0fs)", max_wait)
        if self.error_callback:
            self.error_callback(f"服务启动超时（{max_wait}秒）")

    def stop(self) -> None:
        """停止后端服务器"""
        if not self._running:
            return

        logger.info("正在停止后端服务...")
        self._running = False
        self._ready = False

        if self._server:
            try:
                self._server.should_exit = True
                # 给点时间优雅关闭
                time.sleep(1)
            except Exception:
                pass

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=5)

        logger.info("后端服务已停止")
