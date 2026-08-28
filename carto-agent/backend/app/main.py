"""FastAPI主入口 - 地图制图智能体API

集成大语言模型与知识图谱的在线地图制图智能体系统。
挂载对话、地图、知识图谱、设置四组API路由，提供CORS跨域支持与健康检查。
"""
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.security import apply_request_policy, DEFAULT_LIMITER, LLM_LIMITER
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

# 前端构建产物目录（frontend/vue-app/dist/，由 `npm run build` 生成）
FRONTEND_DIST = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "frontend", "vue-app", "dist",
)


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
    if not settings.api_token:
        logger.warning("  [安全] 未配置 API_TOKEN，API 未启用鉴权（仅建议本地/开发使用；生产请设置 API_TOKEN）")
    else:
        logger.info("  [安全] API 鉴权已启用（Bearer Token / X-API-Key）")
    logger.info("  [安全] 全局限流已启用（%s/分钟/IP，LLM 路径 %s/分钟/IP）", DEFAULT_LIMITER.limit, LLM_LIMITER.limit)
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
    # 关闭外部资源（Neo4j 驱动等），避免连接泄漏
    try:
        from app.api.deps import get_kg_service
        get_kg_service().close()
    except Exception as e:
        logger.warning("关闭时 Neo4j 连接释放失败: %s", e)
    logger.info("地图制图智能体API 服务已停止")


# 创建FastAPI应用实例
app = FastAPI(
    title="地图制图智能体API",
    version="1.0.0",
    description="集成大语言模型与知识图谱的在线地图制图智能体系统",
    lifespan=lifespan,
)

# 添加CORS中间件 - 允许跨域访问（默认仅允许本机前端来源；可通过 CORS_ORIGINS 覆盖）
_allow_origins = (
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if settings.cors_origins
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局限流 + 鉴权中间件：对 /api 路径限流，并在配置 API_TOKEN 时校验令牌
_HTTP_EXEMPT_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc", "/static")


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    path = request.url.path
    if path.startswith("/api") and not path.startswith(_HTTP_EXEMPT_PREFIXES):
        # 1) 限流
        try:
            apply_request_policy(request)
        except Exception as e:
            return JSONResponse(status_code=429, content={"success": False, "message": str(e)})
        # 2) 鉴权（仅在配置了 API_TOKEN 时生效）
        if settings.api_token:
            expected = settings.api_token
            auth = request.headers.get("authorization")
            xkey = request.headers.get("x-api-key")
            provided = xkey or (auth[7:].strip() if auth and auth.lower().startswith("bearer ") else None)
            if not provided or not secrets.compare_digest(provided, expected):
                return JSONResponse(status_code=401, content={"success": False, "message": "无效的 API 令牌"})
    return await call_next(request)

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
# 前端为 Vue 3（frontend/vue-app/）。开发时由 Vite 独立启动（默认 5173，
# 经 vite.config.ts 将 /api、/ws 代理到本后端）；生产部署先执行
# `cd frontend/vue-app && npm run build`，产物落在 dist/ 后由下方托管。

if os.path.exists(os.path.join(FRONTEND_DIST, "index.html")):
    # /app 路由必须在 mount("/") 之前定义，否则会被静态文件拦截
    @app.get("/app", summary="前端页面入口")
    async def serve_frontend():
        """提供前端主页面（Vue 构建产物）"""
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))

    # 挂载 dist 目录到根路径（API 路由和 /app 已注册，会优先匹配）
    # 静态资源禁用缓存，确保每次更新（如 legacy/map.js）能立即在浏览器生效
    class _NoCacheStaticFiles(StaticFiles):
        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            if path.endswith((".js", ".css", ".html", ".map.js", ".json")):
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
                response.headers["Pragma"] = "no-cache"
            return response

    app.mount("/", _NoCacheStaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

    logger.info("  前端页面: http://%s:%s/app", settings.host, settings.port)
else:
    logger.info(
        "前端为 Vue/Vite：开发时请 `cd frontend/vue-app && npm run dev`（默认 5173）；"
        "生产部署先 `npm run build` 生成 dist/ 后再启动后端。"
    )
