"""CartoAgent 桌面应用主入口

启动流程：
1. 初始化用户数据目录
2. 在后台线程启动 FastAPI 后端
3. 创建 PyWebView 窗口加载前端
4. （可选）系统托盘
5. 窗口关闭时优雅停止后端
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

# 确保能导入 desktop 包
_desktop_dir = os.path.dirname(os.path.abspath(__file__))
if _desktop_dir not in sys.path:
    sys.path.insert(0, _desktop_dir)

from paths import (
    get_user_data_dir,
    get_log_dir,
    get_config_file,
    get_frontend_dist,
    APP_NAME,
    APP_VERSION,
    DESKTOP_MODE,
)
from server import BackendServer


def _setup_logging() -> None:
    """配置桌面应用日志（同时输出到文件和控制台）

    文件日志在权限不足时自动降级为仅控制台输出。
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # 文件日志（权限不足时降级）
    try:
        log_dir = get_log_dir()
        log_file = os.path.join(log_dir, "carto-agent-desktop.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)
    except (PermissionError, OSError) as e:
        # 降级：尝试临时目录
        try:
            import tempfile
            log_file = os.path.join(tempfile.gettempdir(), "carto-agent-desktop.log")
            file_handler = RotatingFileHandler(
                log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(fmt)
            root_logger.addHandler(file_handler)
        except Exception:
            pass  # 最终降级：仅控制台

    # 控制台日志
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root_logger.addHandler(console)


logger = logging.getLogger("carto-agent.desktop")


class CartoAgentDesktopApp:
    """桌面应用主类

    负责协调后端服务器、主窗口、系统托盘的生命周期。
    """

    def __init__(self):
        self.server: BackendServer | None = None
        self.window = None
        self.tray = None
        self._quitting = False

    def start(self) -> None:
        """启动桌面应用"""
        logger.info("=" * 60)
        logger.info("%s 桌面版 v%s", APP_NAME, APP_VERSION)
        logger.info("  运行模式: %s", "打包版" if DESKTOP_MODE else "开发模式")
        logger.info("  数据目录: %s", get_user_data_dir())
        logger.info("  配置文件: %s", get_config_file())
        logger.info("  前端目录: %s", get_frontend_dist())
        logger.info("=" * 60)

        # 启动后端服务器
        self._start_backend()

        # 创建主窗口
        self._create_window()

    def _start_backend(self) -> None:
        """启动内嵌后端服务器"""
        data_dir = get_user_data_dir()

        def on_ready():
            logger.info("后端就绪，加载前端页面")
            # 后端就绪后加载页面
            if self.window:
                try:
                    self.window.load_url(self.server.base_url + "/app")
                except Exception as e:
                    logger.warning("加载页面失败: %s", e)

        def on_error(msg: str):
            logger.error("后端错误: %s", msg)
            if self.window:
                try:
                    self.window.evaluate_js(
                        f'document.body.innerHTML = '
                        f'"<div style=\'padding:40px;font-family:sans-serif;color:#dc2626\'>'
                        f'<h2>服务启动失败</h2><p>{msg}</p></div>"'
                    )
                except Exception:
                    pass

        self.server = BackendServer(
            host="127.0.0.1",
            port=8765,
            data_dir=data_dir,
            ready_callback=on_ready,
            error_callback=on_error,
        )
        self.server.start()

    def _create_window(self) -> None:
        """创建 PyWebView 主窗口"""
        try:
            import webview
        except ImportError:
            logger.error("pywebview 未安装，无法启动桌面窗口")
            print("错误：请先安装 pywebview：pip install pywebview")
            sys.exit(1)

        # 启动时先显示加载页，后端就绪后再切换
        loading_html = self._loading_page()

        self.window = webview.create_window(
            title=f"{APP_NAME} - 地图制图智能体",
            html=loading_html,
            width=1400,
            height=900,
            min_size=(1024, 680),
            resizable=True,
            fullscreen=False,
            text_select=True,
            background_color="#ffffff",
        )

        # 绑定窗口事件
        self.window.events.closed += self._on_window_closed

        # 启动系统托盘（可选）
        self._setup_tray()

        # 阻塞式运行 WebView 消息循环
        webview.start(
            debug=False,
            func=self._on_webview_started,
        )

    def _loading_page(self) -> str:
        """生成加载中页面"""
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{APP_NAME}</title>
<style>
  body {{
    margin: 0;
    height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5a87 100%);
    color: white;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  .logo {{
    font-size: 48px;
    font-weight: 300;
    margin-bottom: 16px;
    letter-spacing: 4px;
  }}
  .subtitle {{
    font-size: 16px;
    opacity: 0.8;
    margin-bottom: 40px;
  }}
  .spinner {{
    width: 40px;
    height: 40px;
    border: 3px solid rgba(255,255,255,0.2);
    border-top-color: white;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }}
  .status {{
    margin-top: 24px;
    font-size: 14px;
    opacity: 0.7;
  }}
  @keyframes spin {{
    to {{ transform: rotate(360deg); }}
  }}
</style>
</head>
<body>
  <div class="logo">{APP_NAME}</div>
  <div class="subtitle">地图制图智能体 · v{APP_VERSION}</div>
  <div class="spinner"></div>
  <div class="status" id="status">正在启动服务...</div>
</body>
</html>"""

    def _setup_tray(self) -> None:
        """设置系统托盘（可选依赖）"""
        try:
            from tray import SystemTray
            self.tray = SystemTray(
                on_show_window=self._show_window,
                on_quit=self.quit,
                base_url=self.server.base_url if self.server else "",
                data_dir=get_user_data_dir(),
            )
            if self.tray.create():
                self.tray.run_detached()
                logger.info("系统托盘已创建")
        except Exception as e:
            logger.info("系统托盘不可用: %s", e)

    def _show_window(self) -> None:
        """显示并激活主窗口"""
        if self.window:
            try:
                self.window.show()
            except Exception:
                pass

    def _on_webview_started(self) -> None:
        """WebView 启动完成后的回调"""
        logger.info("桌面窗口已创建")

    def _on_window_closed(self) -> None:
        """主窗口关闭事件"""
        logger.info("主窗口已关闭")
        # 窗口关闭时不退出（托盘还在），除非明确选择退出
        # 但为了简单，当前版本窗口关闭即退出
        if not self._quitting:
            self.quit()

    def quit(self) -> None:
        """退出应用（停止后端+关闭窗口+停止托盘）"""
        if self._quitting:
            return
        self._quitting = True

        logger.info("正在退出应用...")

        # 停止后端
        if self.server:
            self.server.stop()

        # 停止托盘
        if self.tray:
            self.tray.stop()

        # 关闭窗口
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass

        logger.info("应用已退出")


def main():
    """桌面应用入口函数"""
    _setup_logging()

    try:
        app = CartoAgentDesktopApp()
        app.start()
    except KeyboardInterrupt:
        logger.info("收到中断信号，退出中...")
    except Exception:
        logger.exception("应用启动失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
