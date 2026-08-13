"""
数据库连接管理
"""
import os
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
            # 若业务代码已显式提交/回滚则跳过；否则统一提交，确保改动落库
            if session.is_active:
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise
        finally:
            await session.close()


async def get_pgvector_session() -> AsyncSession:
    """获取向量数据库会话（PostgreSQL + pgvector）"""
    async with PGVectorAsyncSession() as session:
        try:
            yield session
            if session.is_active:
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库连接"""
    logger.info("初始化数据库连接...")

    import app.models.user  # noqa: F401
    import app.models.chat_user  # noqa: F401
    import app.models.oauth_config  # noqa: F401
    import app.models.datasource  # noqa: F401
    import app.models.metric  # noqa: F401
    import app.models.dimension  # noqa: F401
    import app.models.term  # noqa: F401
    import app.models.llm_config  # noqa: F401
    import app.models.knowledge  # noqa: F401
    import app.models.session  # noqa: F401
    import app.models.audit_log  # noqa: F401
    import app.models.tool_config  # noqa: F401

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
            if 'tool_calls' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN tool_calls JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.tool_calls IS '工具调用信息(JSON)'"
                ))
                logger.info("已为 messages 表添加 tool_calls 列")
            if 'tool_results' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE messages ADD COLUMN tool_results JSONB DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN messages.tool_results IS '工具调用结果(JSON)'"
                ))
                logger.info("已为 messages 表添加 tool_results 列")

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
            if 'tool_config_ids' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD COLUMN tool_config_ids JSONB DEFAULT '[]'::jsonb"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN applications.tool_config_ids IS '关联工具配置ID列表(MCP/Skills)'"
                ))
                logger.info("已为 applications 表添加 tool_config_ids 列")
            if 'access_hash' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD COLUMN access_hash VARCHAR(16)"
                ))
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD CONSTRAINT applications_access_hash_key UNIQUE (access_hash)"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN applications.access_hash IS '公开访问hash（16位随机十六进制）'"
                ))
                logger.info("已为 applications 表添加 access_hash 列")
            if 'score_threshold' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD COLUMN score_threshold FLOAT DEFAULT 0.6"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN applications.score_threshold IS '检索相似度阈值(0-1之间)'"
                ))
                logger.info("已为 applications 表添加 score_threshold 列")
            if 'top_k' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE applications ADD COLUMN top_k INTEGER DEFAULT 3"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN applications.top_k IS '引用分段数(1-10之间)'"
                ))
                logger.info("已为 applications 表添加 top_k 列")

        # users 表添加 user_source 字段
        if 'users' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('users')}
            if 'user_source' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE users ADD COLUMN user_source VARCHAR(20) DEFAULT 'local'"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN users.user_source IS '用户来源: local/oauth2'"
                ))
                logger.info("已为 users 表添加 user_source 列")

        # chat_users 表添加密码相关字段
        if 'chat_users' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('chat_users')}
            if 'password_hash' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE chat_users ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN chat_users.password_hash IS '密码哈希（用于账号密码登录）'"
                ))
                logger.info("已为 chat_users 表添加 password_hash 列")
            if 'force_change_password' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE chat_users ADD COLUMN force_change_password BOOLEAN DEFAULT FALSE"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN chat_users.force_change_password IS '是否强制改密（OAuth首次登录后设置密码）'"
                ))
                logger.info("已为 chat_users 表添加 force_change_password 列")

        # sessions 表添加 chat_user_id 字段（用于嵌入模式对话用户数据隔离）
        if 'sessions' in inspector.get_table_names():
            existing_cols = {col['name'] for col in inspector.get_columns('sessions')}
            if 'chat_user_id' not in existing_cols:
                sync_conn.execute(text(
                    "ALTER TABLE sessions ADD COLUMN chat_user_id INTEGER DEFAULT NULL"
                ))
                sync_conn.execute(text(
                    "ALTER TABLE sessions ADD CONSTRAINT sessions_chat_user_id_fkey "
                    "FOREIGN KEY (chat_user_id) REFERENCES chat_users(id)"
                ))
                sync_conn.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_sessions_chat_user_id ON sessions (chat_user_id)"
                ))
                sync_conn.execute(text(
                    "COMMENT ON COLUMN sessions.chat_user_id IS '对话用户ID(嵌入模式使用，可为空)'"
                ))
                logger.info("已为 sessions 表添加 chat_user_id 列")

        # tool_configs 表：将绝对路径迁移为相对路径
        # 旧数据使用 os.getcwd() 存储绝对路径，需转换为相对于项目根目录的路径
        # 同时修复Windows驱动器路径缺少反斜杠的损坏数据（如 "E:path" → "E:\path"）
        if 'tool_configs' in inspector.get_table_names():
            try:
                result = sync_conn.execute(text(
                    "SELECT id, skill_file_path FROM tool_configs WHERE skill_file_path IS NOT NULL AND skill_file_path != ''"
                ))
                rows = result.fetchall()
                from app.services.tool_config_service import to_relative_path
                for row in rows:
                    old_path = row[1]
                    if not old_path:
                        continue
                    # 修复损坏的驱动器路径（E:path → E:\path）
                    fixed_path = old_path
                    if len(old_path) >= 2 and old_path[1] == ':' and old_path[0].isalpha():
                        if len(old_path) > 2 and old_path[2] not in ('\\', '/'):
                            fixed_path = old_path[0] + ':\\' + old_path[2:]
                            logger.info(f"修复损坏路径: id={row[0]}, {old_path[:30]}... → {fixed_path[:30]}...")
                    # 转换绝对路径为相对路径
                    if fixed_path and os.path.isabs(fixed_path):
                        new_path = to_relative_path(fixed_path)
                        if new_path != old_path:
                            sync_conn.execute(text(
                                "UPDATE tool_configs SET skill_file_path = :new_path WHERE id = :tool_id"
                            ), {"new_path": new_path, "tool_id": row[0]})
                            logger.info(f"迁移Skill路径: id={row[0]}, {old_path} → {new_path}")
                if rows:
                    sync_conn.commit()
                    logger.info(f"Skill文件路径迁移完成，共处理 {len(rows)} 条记录")
            except Exception as e:
                logger.warning(f"Skill文件路径迁移失败: {e}")

    await conn.run_sync(_add_missing_columns)
