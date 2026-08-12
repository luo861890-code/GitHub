"""Pydantic Settings配置 - 从.env读取多LLM和环境配置"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


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

    # DeepSeek（已内置默认Key，无需额外配置；.env中的DEEPSEEK_API_KEY优先级更高）
    deepseek_api_key: str = "sk-3e5bec1588c546179a139ae610de5604"
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

    # ========== 服务 ==========
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    data_dir: str = "../data"

    @property
    def overpass_server_list(self) -> List[str]:
        """获取Overpass服务器列表"""
        return [s.strip() for s in self.overpass_servers.split(",") if s.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
