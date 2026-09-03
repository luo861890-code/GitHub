"""桌面应用路径管理 - 适配开发模式与 PyInstaller 打包模式

资源路径（只读，随程序发布）：
  - 开发模式：项目根目录
  - 打包模式：PyInstaller _MEIPASS 临时目录

数据路径（可写，用户数据）：
  - 始终指向用户目录下的 CartoAgent/
  - Windows: %APPDATA%/CartoAgent/
  - macOS: ~/Library/Application Support/CartoAgent/
  - Linux: ~/.local/share/CartoAgent/
"""
import os
import sys


def _project_root() -> str:
    """开发模式下的项目根目录（desktop/ 的上一级）"""
    # __file__ = <project>/desktop/paths.py
    # 上两级 = 项目根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _is_frozen() -> bool:
    """是否为 PyInstaller 打包后的运行模式"""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def get_resource_path(*rel_parts: str) -> str:
    """获取只读资源的绝对路径（适配打包/开发两种模式）

    打包后资源在 sys._MEIPASS 中，开发时在项目根目录。
    """
    if _is_frozen():
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        base = _project_root()
    return os.path.join(base, *rel_parts)


def get_backend_dir() -> str:
    """后端代码目录"""
    if _is_frozen():
        return os.path.join(sys._MEIPASS, "backend")  # type: ignore[attr-defined]
    return os.path.join(_project_root(), "backend")


def get_frontend_dist() -> str:
    """前端构建产物目录"""
    return get_resource_path("frontend", "vue-app", "dist")


def get_user_data_dir() -> str:
    """获取用户数据目录（可写），不存在则创建

    存放：用户地图、会话、配置、缓存等。
    权限不足时降级到临时目录。
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    data_dir = os.path.join(base, "CartoAgent")

    try:
        os.makedirs(data_dir, exist_ok=True)
        for sub in ("users", "users/local", "system_maps", "kg", "cache", "logs"):
            os.makedirs(os.path.join(data_dir, sub), exist_ok=True)
    except (PermissionError, OSError):
        import tempfile
        data_dir = os.path.join(tempfile.gettempdir(), "CartoAgent")
        os.makedirs(data_dir, exist_ok=True)
        for sub in ("users", "users/local", "system_maps", "kg", "cache", "logs"):
            os.makedirs(os.path.join(data_dir, sub), exist_ok=True)

    return data_dir


def get_geo_data_dir() -> str:
    """GeoJSON 地理数据目录（只读资源）"""
    return get_resource_path("backend", "data", "geo")


def get_dem_data_dir() -> str:
    """DEM 高程数据目录（只读资源）"""
    return get_resource_path("backend", "data", "dem")


def get_runtime_cache_dir() -> str:
    """运行时缓存目录（可写，OSM 缓存等）"""
    cache_dir = os.path.join(get_user_data_dir(), "cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


def get_log_dir() -> str:
    """日志目录"""
    log_dir = os.path.join(get_user_data_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def get_config_file() -> str:
    """用户配置文件路径（.env 格式）"""
    return os.path.join(get_user_data_dir(), "config.env")


# 运行时信息
APP_NAME = "CartoAgent"
APP_VERSION = "1.0.0"
DESKTOP_MODE = _is_frozen()
