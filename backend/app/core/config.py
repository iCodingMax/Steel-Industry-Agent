"""
核心配置模块
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    ENV: str = "development"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "steel_agent"

    # 业务数据库（钢铁生产数据，与系统库分开）
    BUSINESS_DB_HOST: str = ""
    BUSINESS_DB_PORT: int = 0
    BUSINESS_DB_USER: str = ""
    BUSINESS_DB_PASSWORD: str = ""
    BUSINESS_DB_NAME: str = "steel_test"

    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = ""
    PG_DB: str = "steel_agent"

    # 向量数据库（系统库与向量库使用同一PG实例，不同数据库）
    PGVECTOR_HOST: str = ""
    PGVECTOR_PORT: int = 0
    PGVECTOR_USER: str = ""
    PGVECTOR_PASSWORD: str = ""
    PGVECTOR_DATABASE: str = "steel_agent_vector"

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    JWT_SECRET_KEY: str = "default-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    XINFERENCE_BASE_URL: str = "http://172.1.2.198:9997"
    XINFERENCE_EMBED_MODEL: str = "bge-m3"
    XINFERENCE_LLM_MODEL: str = "qwen3"
    XINFERENCE_RERANK_MODEL: str = "bge-reranker-large"
    RERANK_TOP_K: int = 5
    LLM_MAX_TOKENS: int = 20480
    LLM_TEMPERATURE: float = 0.7

    # Skill专用最大输出Token（Skill输出5章节诊断报告需要更长空间）
    # 普通对话 20480 足够，Skill 需要完整报告（含推理说明）建议 ≥32768
    # 仅在模型 context_length 允许时生效，若 context_length 不足则自动下调
    SKILL_MAX_TOKENS: int = 32768

    # 多轮对话：加载到LLM上下文的历史消息条数（10条=5轮对话）
    CHAT_HISTORY_LIMIT: int = 10

    def model_post_init(self, __context) -> None:
        """初始化后处理：PGVECTOR配置默认跟随PG配置"""
        if not self.PGVECTOR_HOST:
            self.PGVECTOR_HOST = self.PG_HOST
        if self.PGVECTOR_PORT == 0:
            self.PGVECTOR_PORT = self.PG_PORT
        if not self.PGVECTOR_USER:
            self.PGVECTOR_USER = self.PG_USER
        if not self.PGVECTOR_PASSWORD:
            self.PGVECTOR_PASSWORD = self.PG_PASSWORD
        if not self.PGVECTOR_DATABASE:
            self.PGVECTOR_DATABASE = self.PG_DB

    @property
    def mysql_url(self) -> str:
        """MySQL异步连接URL"""
        import urllib.parse
        return (
            f"mysql+aiomysql://{self.MYSQL_USER}:{urllib.parse.quote(self.MYSQL_PASSWORD, safe='')}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"
            f"?charset=utf8mb4"
        )

    @property
    def postgresql_url(self) -> str:
        """PostgreSQL异步连接URL"""
        import urllib.parse
        return (
            f"postgresql+asyncpg://{self.PG_USER}:{urllib.parse.quote(self.PG_PASSWORD, safe='')}"
            f"@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"
        )

    @property
    def redis_url(self) -> str:
        """Redis连接URL"""
        if self.REDIS_PASSWORD:
            return (
                f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}"
                f":{self.REDIS_PORT}/{self.REDIS_DB}"
            )
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Settings()
