"""Pydantic Settings配置 - 从.env读取多LLM和环境配置"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv


# 将 backend/.env 注入进程环境变量（供 os.getenv 读取，如 AMAP_KEY / TIANDITU_KEY）
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_ENV_FILE = os.path.join(_BACKEND_ROOT, ".env")
load_dotenv(_ENV_FILE)


class Settings(BaseSettings):
    """应用配置"""

    # ========== LLM配置 ==========
    llm_provider: str = Field(default="deepseek", description="默认LLM提供者")

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:8b"

    # 通义千问
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # DeepSeek：必须通过 backend/.env 的 DEEPSEEK_API_KEY 配置，禁止硬编码密钥到源码
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com/v1"

    # 智谱
    zhipu_api_key: str = ""
    zhipu_model: str = "glm-4"
    zhipu_base_url: str = "https://open.bigmodel.cn/api/paas/v4"

    # ========== Neo4j ==========
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "neo4j123"

    # ========== 地图数据 ==========
    overpass_servers: str = "https://maps.mail.ru/osm/tools/overpass/api/interpreter,https://overpass-api.de/api/interpreter,https://z.overpass-api.de/api/interpreter,https://lz4.overpass-api.de/api/interpreter"
    amap_api_key: str = ""
    # 多源数据融合适配器（兼容旧键名 AMAP_API_KEY）
    amap_key: str = ""
    tianditu_key: str = ""

    # ========== 服务 ==========
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    # 数据目录（maps.json/sessions.json/kg 知识库）。默认锚定到仓库根目录的 data/，
    # 与 CWD 无关；可通过环境变量 DATA_DIR 覆盖。
    data_dir: str = Field(
        default_factory=lambda: os.path.join(
            os.path.dirname(_BACKEND_ROOT), "data"
        )
    )

    # ========== 数据分层存储 ==========
    # 无登录系统，本地默认用户标识。用户聊天记录 / 生成地图 / 操作数据存于
    # data/users/<uid>/ 下；系统预置备用地图存于 data/system_maps/ 下。
    default_user_id: str = Field(default="local", description="默认用户ID")

    @property
    def users_dir(self) -> str:
        """所有用户数据根目录：data/users/"""
        return os.path.join(self.data_dir, "users")

    @property
    def current_user_dir(self) -> str:
        """当前用户数据目录：data/users/<uid>/"""
        return os.path.join(self.users_dir, self.default_user_id)

    @property
    def user_sessions_file(self) -> str:
        """当前用户聊天会话文件：data/users/<uid>/sessions.json"""
        return os.path.join(self.current_user_dir, "sessions.json")

    @property
    def system_maps_dir(self) -> str:
        """系统备用地图目录：data/system_maps/"""
        return os.path.join(self.data_dir, "system_maps")

    # ========== 安全 ==========
    # API 鉴权令牌（Bearer/X-API-Key）。为空表示不强制鉴权（仅本地/开发），
    # 生产部署务必设置 API_TOKEN。
    api_token: str = ""
    # 允许的跨域来源（逗号分隔）。为空则允许所有来源（不建议生产使用）。
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    @property
    def overpass_server_list(self) -> List[str]:
        """获取Overpass服务器列表"""
        return [s.strip() for s in self.overpass_servers.split(",") if s.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
