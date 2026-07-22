"""
数据库连接管理
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy import text, inspect
from loguru import logger

from app.core.config import settings
from app.core.base_model import Base  # noqa: F401 - 导出Base供模型使用


system_engine = create_async_engine(
    settings.postgresql_url,
    echo=settings.ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

pgvector_engine = create_async_engine(
    f"postgresql+asyncpg://{settings.PGVECTOR_USER}:{settings.PGVECTOR_PASSWORD}@{settings.PGVECTOR_HOST}:{settings.PGVECTOR_PORT}/{settings.PGVECTOR_DATABASE}",
    echo=settings.ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SystemAsyncSession = async_sessionmaker(
    system_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

PGVectorAsyncSession = async_sessionmaker(
    pgvector_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncSession:
    """获取系统数据库会话（PostgreSQL）"""
    async with SystemAsyncSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_pgvector_session() -> AsyncSession:
    """获取向量数据库会话（PostgreSQL + pgvector）"""
    async with PGVectorAsyncSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库连接"""
    logger.info("初始化数据库连接...")

    import app.models.user  # noqa: F401
    import app.models.datasource  # noqa: F401
    import app.models.metric  # noqa: F401
    import app.models.dimension  # noqa: F401
    import app.models.term  # noqa: F401
    import app.models.llm_config  # noqa: F401
    import app.models.knowledge  # noqa: F401
    import app.models.session  # noqa: F401
    import app.models.audit_log  # noqa: F401

    try:
        async with system_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await _auto_add_columns(conn)
        logger.success("系统数据库（PostgreSQL）表结构创建完成")
    except Exception as e:
        logger.warning(f"系统数据库初始化失败（首次启动可忽略）: {e}")

    try:
        async with pgvector_engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: None)
        logger.success("向量数据库（PostgreSQL + pgvector）连接成功")
    except Exception as e:
        logger.warning(f"向量数据库连接失败（首次启动可忽略）: {e}")


async def _auto_add_columns(conn) -> None:
    """自动为已有表添加新列（如果列不存在）- PostgreSQL 兼容"""

    def _add_missing_columns(sync_conn):
        inspector = inspect(sync_conn)
        if 'messages' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('messages')}
            if 'data_result' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN data_result JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.data_result IS '查询结果数据(JSON)'"
                ))
                logger.info("已为 messages 表添加 data_result 列")
            if 'column_meta' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN column_meta JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.column_meta IS '字段元信息(JSON)'"
                ))
                logger.info("已为 messages 表添加 column_meta 列")
            if 'chart_type' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN chart_type VARCHAR(20) DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.chart_type IS '推荐图表类型'"
                ))
                logger.info("已为 messages 表添加 chart_type 列")
            if 'thinking_steps' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN thinking_steps JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.thinking_steps IS '思考过程步骤(JSON)'"
                ))
                logger.info("已为 messages 表添加 thinking_steps 列")

        if 'applications' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('applications')}
            if 'datasource_ids' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD COLUMN datasource_ids JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN applications.datasource_ids IS '关联数据源ID列表'"
                ))
                logger.info("已为 applications 表添加 datasource_ids 列")

    await conn.run_sync(_add_missing_columns)
