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

    PG_HOST: str = "localhost"
    PG_PORT: int = 5432
    PG_USER: str = "postgres"
    PG_PASSWORD: str = ""
    PG_DB: str = "steel_agent_vector"

    # pgvector专用配置（默认跟随PG配置，可单独覆盖）
    PGVECTOR_HOST: str = ""
    PGVECTOR_PORT: int = 0
    PGVECTOR_USER: str = ""
    PGVECTOR_PASSWORD: str = ""
    PGVECTOR_DATABASE: str = ""

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    JWT_SECRET_KEY: str = "default-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    XINFERENCE_BASE_URL: str = "http://172.1.2.198:9997"
    XINFERENCE_EMBED_MODEL: str = "bge-m3"
    XINFERENCE_RERANK_MODEL: str = "bge-reranker-large"
    RERANK_TOP_K: int = 5

    NEWAPI_BASE_URL: str = "http://172.1.8.152:3000"
    NEWAPI_API_KEY: str = ""
    NEWAPI_MODEL: str = "glm-5.1-fp8"
    LLM_MAX_TOKENS: int = 20480
    LLM_TEMPERATURE: float = 0.7

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
