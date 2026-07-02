"""
数据库连接管理
"""
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from loguru import logger

from app.core.config import settings
from app.core.base_model import Base  # noqa: F401 - 导出Base供模型使用


mysql_engine = create_async_engine(
    settings.mysql_url,
    echo=settings.ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

pg_engine = create_async_engine(
    settings.postgresql_url,
    echo=settings.ENV == "development",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

MySQLAsyncSession = async_sessionmaker(
    mysql_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

PGAsyncSession = async_sessionmaker(
    pg_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_mysql_session() -> AsyncSession:
    """获取MySQL数据库会话"""
    async with MySQLAsyncSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_pg_session() -> AsyncSession:
    """获取PostgreSQL数据库会话"""
    async with PGAsyncSession() as session:
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
    
    # 延迟导入所有模型模块，确保SQLAlchemy能扫描到（避免循环导入）
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
        async with mysql_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # 自动补列：为已有表添加新字段
            await _auto_add_columns(conn)
        logger.success("MySQL 表结构创建完成")
    except Exception as e:
        logger.warning(f"MySQL 初始化失败（首次启动可忽略）: {e}")

    try:
        async with pg_engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: None)
        logger.success("PostgreSQL 连接成功")
    except Exception as e:
        logger.warning(f"PostgreSQL 连接失败（首次启动可忽略）: {e}")


async def _auto_add_columns(conn) -> None:
    """自动为已有表添加新列（如果列不存在）"""
    from sqlalchemy import text, inspect

    def _add_missing_columns(sync_conn):
        inspector = inspect(sync_conn)
        # 检查 messages 表是否缺少 data_result 列
        if 'messages' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('messages')}
            if 'data_result' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN data_result JSON DEFAULT NULL COMMENT '查询结果数据(JSON)'"
                ))
                logger.info("已为 messages 表添加 data_result 列")

    await conn.run_sync(_add_missing_columns)
