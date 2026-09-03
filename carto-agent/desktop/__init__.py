"""CartoAgent 桌面应用包

使用 PyWebView 将 FastAPI 后端 + Vue 前端打包为桌面程序。
"""
from .paths import (
    get_resource_path,
    get_user_data_dir,
    get_backend_dir,
    get_frontend_dist,
    get_geo_data_dir,
    get_runtime_cache_dir,
    get_log_dir,
    get_config_file,
    APP_NAME,
    APP_VERSION,
    DESKTOP_MODE,
)

__all__ = [
    "get_resource_path",
    "get_user_data_dir",
    "get_backend_dir",
    "get_frontend_dist",
    "get_geo_data_dir",
    "get_runtime_cache_dir",
    "get_log_dir",
    "get_config_file",
    "APP_NAME",
    "APP_VERSION",
    "DESKTOP_MODE",
]
