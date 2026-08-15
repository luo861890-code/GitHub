"""FastAPI主入口 - 地图制图智能体API

集成大语言模型与知识图谱的在线地图制图智能体系统。
挂载对话、地图、知识图谱、设置四组API路由，提供CORS跨域支持与健康检查。
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings
from app.api.chat import router as chat_router
from app.api.maps import router as maps_router
from app.api.knowledge import router as kg_router
from app.api.settings import router as settings_router
from app.models.schemas import ApiResponse

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("carto-agent")

# 前端静态文件根目录（frontend/，包含config.js和src/）
FRONTEND_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
FRONTEND_SRC = os.path.join(FRONTEND_ROOT, "src")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 - 启动与关闭时执行相应逻辑"""
    # ===== 启动 =====
    logger.info("=" * 60)
    logger.info("地图制图智能体API 服务已启动")
    logger.info("  监听地址: http://%s:%s", settings.host, settings.port)
    logger.info("  API文档:  http://%s:%s/docs", settings.host, settings.port)
    logger.info("  当前LLM:  %s", settings.llm_provider)
    logger.info("  调试模式:  %s", "开启" if settings.debug else "关闭")
    logger.info("=" * 60)
    yield
    # ===== 关闭 =====
    # 安全落盘：确保防抖写入的数据在服务关闭前持久化
    try:
        from app.api.deps import get_session_service, get_map_service
        get_session_service().flush()
        get_map_service().flush()
    except Exception as e:
        logger.warning("关闭时数据落盘失败: %s", e)
    logger.info("地图制图智能体API 服务已停止")


# 创建FastAPI应用实例
app = FastAPI(
    title="地图制图智能体API",
    version="1.0.0",
    description="集成大语言模型与知识图谱的在线地图制图智能体系统",
    lifespan=lifespan,
)

# 添加CORS中间件 - 允许跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载API路由
app.include_router(chat_router)
app.include_router(maps_router)
app.include_router(kg_router)
app.include_router(settings_router)


@app.get("/", response_model=ApiResponse, summary="根路由")
async def root():
    """根路由 - 返回服务欢迎信息与入口指引"""
    return ApiResponse(
        success=True,
        message="欢迎使用地图制图智能体API",
        data={
            "name": "地图制图智能体",
            "version": "1.0.0",
            "description": "集成大语言模型与知识图谱的在线地图制图智能体系统",
            "docs": "/docs",
            "health": "/health",
            "endpoints": {
                "chat": "/api/chat",
                "maps": "/api/maps",
                "knowledge_graph": "/api/kg",
                "settings": "/api/settings",
            },
        },
    )


@app.get("/health", response_model=ApiResponse, summary="健康检查")
async def health_check():
    """健康检查接口 - 用于服务探活"""
    return ApiResponse(
        success=True,
        message="服务运行正常",
        data={"status": "ok"},
    )


# ========== 前端静态文件服务 ==========

if os.path.exists(FRONTEND_ROOT):
    # /app 路由必须在 mount("/") 之前定义，否则会被静态文件拦截
    @app.get("/app", summary="前端页面入口")
    async def serve_frontend():
        """提供前端主页面 - 重定向到/src/index.html确保相对路径正确解析"""
        return RedirectResponse(url="/src/index.html")

    # 挂载frontend目录到根路径（API路由和/app已注册，会优先匹配）
    # 这样 /config.js、/src/js/*.js 等相对路径资源都能正确访问
    app.mount("/", StaticFiles(directory=FRONTEND_ROOT, html=True), name="frontend")

    logger.info("  前端页面: http://%s:%s/app", settings.host, settings.port)
    logger.info("  前端页面: http://%s:%s/src/index.html", settings.host, settings.port)
else:
    logger.warning("前端目录不存在: %s，跳过静态文件服务", FRONTEND_ROOT)
