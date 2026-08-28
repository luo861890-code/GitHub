"""安全模块 - API 鉴权与轻量级限流

- verify_api_key:   校验请求中的 Bearer Token 或 X-API-Key（依赖 settings.api_token）。
                    未配置 API_TOKEN 时放行（本地/开发），并在启动时告警。
- RateLimiter:      内存滑动窗口限流器，按 (IP, 限流组) 统计，超限返回 429。
                    线程安全，进程内有效；多实例部署请改用 Redis 或网关限流。
"""
import logging
import secrets
import threading
import time
from typing import Optional

from fastapi import Request, HTTPException
from starlette.datastructures import Headers

logger = logging.getLogger("carto-agent.security")


def _extract_token(authorization: Optional[str], x_api_key: Optional[str]) -> Optional[str]:
    """从请求头提取令牌。"""
    if x_api_key:
        return x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


def verify_api_key(request: Request) -> None:
    """FastAPI 依赖：校验 API 令牌（Bearer / X-API-Key）。

    当 settings.api_token 为空时不强制校验（开发模式）。
    """
    from app.core.config import settings  # 延迟导入避免循环依赖

    expected = settings.api_token
    if not expected:
        return
    auth: Optional[str] = request.headers.get("authorization")
    key: Optional[str] = request.headers.get("x-api-key")
    provided = _extract_token(auth, key)
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="无效的 API 令牌")


class RateLimiter:
    """简单的内存滑动窗口限流器。"""

    def __init__(self, limit: int, window_seconds: int):
        self._limit = limit
        self._window = window_seconds
        self._hits: dict = {}  # (ip, group) -> [timestamps]
        self._lock = threading.Lock()

    def check(self, ip: str, group: str = "") -> bool:
        """返回是否允许本次请求（在允许额度内）。"""
        now = time.monotonic()
        key = (ip, group)
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < self._window]
            if len(hits) >= self._limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True

    @property
    def limit(self) -> int:
        return self._limit

    @property
    def window(self) -> int:
        return self._window


# 全局限流器：默认 120 次/分钟/IP；LLM 敏感路径更严格 15 次/分钟/IP
DEFAULT_LIMITER = RateLimiter(limit=120, window_seconds=60)
LLM_LIMITER = RateLimiter(limit=15, window_seconds=60)

# 触发 LLM 的高成本路径前缀（限流更严）
_LLM_PATH_PREFIXES = (
    "/api/chat",
    "/api/kg/query",
    "/api/kg/graphrag",
    "/api/maps/export",
    "/api/maps/import",
)


def apply_request_policy(request: Request) -> None:
    """请求级策略：限流。鉴权由 verify_api_key 依赖负责。

    供全局中间件调用；/health、/docs、静态资源不限流。
    """
    client_ip = request.client.host if request.client else "unknown"
    path = request.url.path

    # 对 LLM 高成本路径使用更严格限制
    limiter = LLM_LIMITER if path.startswith(_LLM_PATH_PREFIXES) else DEFAULT_LIMITER
    if not limiter.check(client_ip, group=path.split("/")[2] if path.startswith("/api/") else "static"):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
