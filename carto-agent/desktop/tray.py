"""系统托盘图标管理

在桌面模式下提供系统托盘图标，支持：
- 显示/隐藏主窗口
- 打开数据目录
- 退出程序
"""
import logging
import os
import webbrowser
from typing import Callable, Optional

logger = logging.getLogger("carto-agent.desktop.tray")


class SystemTray:
    """系统托盘管理器

    优先使用原生托盘（pywebview 不内置，需用 pystray + Pillow）。
    若依赖未安装则降级为无托盘模式，不影响主功能。
    """

    def __init__(
        self,
        on_show_window: Callable[[], None],
        on_quit: Callable[[], None],
        base_url: str = "",
        data_dir: str = "",
    ):
        self.on_show_window = on_show_window
        self.on_quit = on_quit
        self.base_url = base_url
        self.data_dir = data_dir
        self._tray_icon = None
        self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def create(self) -> bool:
        """创建系统托盘图标。返回是否成功创建。"""
        try:
            import pystray
            from PIL import Image, ImageDraw
        except ImportError:
            logger.info("pystray/Pillow 未安装，跳过系统托盘")
            return False

        # 生成简单的地图图标（蓝色定位针样式）
        image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # 圆形底
        draw.ellipse([8, 8, 56, 56], fill=(59, 130, 246, 255))
        # 内部白色地图符号（简化为 M）
        draw.text((22, 18), "M", fill="white")

        def on_show(icon, item):
            self.on_show_window()

        def on_open_browser(icon, item):
            if self.base_url:
                webbrowser.open(self.base_url + "/app")

        def on_open_data(icon, item):
            if self.data_dir and os.path.exists(self.data_dir):
                os.startfile(self.data_dir)  # type: ignore[attr-defined]

        def on_quit(icon, item):
            icon.stop()
            self.on_quit()

        menu = pystray.Menu(
            pystray.MenuItem("显示主窗口", on_show, default=True),
            pystray.MenuItem("在浏览器中打开", on_open_browser),
            pystray.MenuItem("打开数据目录", on_open_data),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit),
        )

        self._tray_icon = pystray.Icon(
            "cartoagent",
            image,
            "CartoAgent 地图制图智能体",
            menu,
        )
        self._available = True
        return True

    def run_detached(self) -> None:
        """在独立线程中运行托盘图标（非阻塞）"""
        if not self._tray_icon:
            return

        import threading

        def _run():
            try:
                self._tray_icon.run()
            except Exception:
                logger.exception("系统托盘运行失败")

        threading.Thread(target=_run, name="carto-tray", daemon=True).start()

    def stop(self) -> None:
        """停止托盘图标"""
        if self._tray_icon:
            try:
                self._tray_icon.stop()
            except Exception:
                pass
