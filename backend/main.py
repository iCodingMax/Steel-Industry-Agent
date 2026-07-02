"""
钢铁行业智能问答系统 - FastAPI 应用入口
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.middlewares.exception_handler import (
    custom_exception_handler,
    global_exception_handler,
    BusinessException,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("=" * 60)
    logger.info("钢铁行业智能问答系统启动中...")
    logger.info(f"运行环境: {settings.ENV}")
    logger.info("=" * 60)

    await init_db()

    from app.services.auth_service import auth_service
    from app.core.database import MySQLAsyncSession
    async with MySQLAsyncSession() as db:
        await auth_service.init_default_admin(db)

    logger.success("系统启动成功!")
    yield
    logger.info("系统关闭中...")

    # 优雅关闭数据库连接池
    from app.core.database import mysql_engine, pg_engine
    await mysql_engine.dispose()
    await pg_engine.dispose()
    logger.info("数据库连接池已关闭")


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    app = FastAPI(
        title="Steel Industry AI Assistant API",
        description="钢铁行业智能问答系统 - RAG + ChatBI 融合推理",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(BusinessException, custom_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    app.include_router(api_router, prefix=settings.API_PREFIX)

    @app.get("/health", summary="健康检查")
    async def health_check():
        return {"status": "ok", "service": "steel-industry-agent"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )
