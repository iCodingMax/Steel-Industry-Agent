"""
数据源服务模块
管理数据源的CRUD操作和表结构同步
支持多种数据库类型：MySQL、PostgreSQL、SQL Server

主要功能：
1. 数据源管理：创建、查询、更新、删除
2. 连接测试：验证数据源配置是否正确
3. 表结构同步：从业务数据库同步表结构到系统数据库
"""
import json
import re
from typing import List, Optional
from sqlalchemy import select, delete as sa_delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.datasource import DataSource, TableSchema
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate, TestConnectionRequest
from app.middlewares.exception_handler import BusinessException


class DataSourceService:
    """
    数据源服务类
    负责数据源的生命周期管理和表结构同步
    支持MySQL、PostgreSQL、SQL Server三种数据库类型
    """

    @staticmethod
    async def create(db: AsyncSession, data: DataSourceCreate, user_id: Optional[int] = None) -> DataSource:
        """
        创建数据源

        :param db: 数据库会话
        :param data: 数据源创建参数
        :param user_id: 创建者ID（可选）
        :return: 创建的数据源对象
        """
        logger.debug(f"创建数据源: name={data.name}, type={data.type}, host={data.host}")
        ds = DataSource(
            name=data.name,
            type=data.type,
            host=data.host,
            port=data.port,
            database=data.database,
            username=data.username,
            password=data.password,
            charset=data.charset,
            pool_size=data.poolSize,
            max_overflow=data.maxOverflow,
            description=data.description,
            created_by=user_id,
        )
        db.add(ds)
        await db.commit()
        await db.refresh(ds)
        logger.info(f"创建数据源成功: {ds.name} (ID: {ds.id})")
        return ds

    @staticmethod
    async def get_by_id(db: AsyncSession, ds_id: int) -> Optional[DataSource]:
        """
        根据ID获取数据源

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: 数据源对象（不存在返回None）
        """
        stmt = select(DataSource).where(DataSource.id == ds_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DataSource]:
        """
        获取所有数据源列表

        :param db: 数据库会话
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数）
        :return: 数据源列表
        """
        stmt = select(DataSource).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db: AsyncSession, ds_id: int, data: DataSourceUpdate) -> Optional[DataSource]:
        """
        更新数据源

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param data: 更新参数（仅包含需要更新的字段）
        :return: 更新后的数据源对象
        :raises BusinessException: 数据源不存在时抛出
        """
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(ds, key):
                setattr(ds, key, value)

        await db.commit()
        await db.refresh(ds)
        logger.info(f"更新数据源成功: {ds.name} (ID: {ds.id})")
        return ds

    @staticmethod
    async def delete(db: AsyncSession, ds_id: int) -> None:
        """
        删除数据源

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :raises BusinessException: 数据源不存在时抛出
        """
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        await db.delete(ds)
        await db.commit()
        logger.info(f"删除数据源成功: {ds.name} (ID: {ds_id})")

    @staticmethod
    async def test_connection(db: AsyncSession, data: TestConnectionRequest) -> dict:
        """
        测试数据库连接
        根据数据库类型使用对应的驱动进行连接测试

        :param db: 数据库会话（未使用，保持接口一致性）
        :param data: 连接测试参数
        :return: 测试结果，包含success和message字段
        :raises BusinessException: 不支持的数据库类型时抛出
        """
        logger.debug(f"测试数据库连接: type={data.type}, host={data.host}, database={data.database}")
        try:
            if data.type == "mysql":
                import aiomysql
                conn = await aiomysql.connect(
                    host=data.host,
                    port=data.port,
                    user=data.username,
                    password=data.password or "",
                    db=data.database,
                    charset=data.charset or "utf8mb4",
                )
                conn.close()
                logger.debug("MySQL连接测试成功")
            elif data.type == "postgresql":
                import asyncpg
                conn = await asyncpg.connect(
                    host=data.host,
                    port=data.port,
                    user=data.username,
                    password=data.password or "",
                    database=data.database,
                )
                await conn.close()
                logger.debug("PostgreSQL连接测试成功")
            elif data.type == "sqlserver":
                import asyncio
                import pyodbc
                connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={data.host},{data.port};DATABASE={data.database};UID={data.username};PWD={data.password or ''}"
                loop = asyncio.get_event_loop()
                conn = await loop.run_in_executor(None, pyodbc.connect, connection_string)
                cursor = conn.cursor()
                await loop.run_in_executor(None, cursor.execute, "SELECT 1")
                cursor.close()
                conn.close()
                logger.debug("SQL Server连接测试成功")
            else:
                raise BusinessException(code=400, message=f"不支持的数据库类型: {data.type}")

            logger.info(f"数据库连接测试成功: {data.type}://{data.host}:{data.port}/{data.database}")
            return {"success": True, "message": "连接成功"}
        except Exception as e:
            logger.error(f"数据库连接测试失败: {data.type}://{data.host}:{data.port}/{data.database}, error={e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    async def sync_schema(db: AsyncSession, ds_id: int) -> List[TableSchema]:
        """
        同步数据源表结构
        从业务数据库读取所有表结构信息，同步到系统数据库的table_schemas表

        同步流程：
        1. 获取数据源配置
        2. 清除该数据源的旧表结构记录（避免重复）
        3. 重置PostgreSQL序列（避免主键冲突）
        4. 根据数据库类型读取表和字段信息
        5. 将表结构数据写入系统数据库

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: 同步后的表结构列表
        :raises BusinessException: 数据源不存在或同步失败时抛出
        """
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        logger.info(f"开始同步数据源表结构: ID={ds_id}, name={ds.name}, type={ds.type}")

        try:
            # 步骤1：清除该数据源的旧表结构记录
            await db.execute(sa_delete(TableSchema).where(TableSchema.datasource_id == ds_id))
            await db.commit()
            logger.debug("已清除旧表结构记录")
            
            # 步骤2：重置PostgreSQL序列，避免主键冲突
            max_id_result = await db.execute(text("SELECT COALESCE(MAX(id), 0) FROM table_schemas"))
            max_id = max_id_result.scalar() or 0
            await db.execute(text(f"ALTER SEQUENCE table_schemas_id_seq RESTART WITH {max_id + 1}"))
            await db.commit()
            logger.debug(f"序列已重置: table_schemas_id_seq -> {max_id + 1}")

            tables = []

            # 步骤3：根据数据库类型读取表结构
            if ds.type == "mysql":
                logger.debug("开始读取MySQL表结构")
                import aiomysql
                conn = await aiomysql.connect(
                    host=ds.host,
                    port=ds.port or 3306,
                    user=ds.username,
                    password=ds.password or "",
                    db=ds.database,
                    charset=ds.charset or "utf8mb4",
                )
                async with conn.cursor() as cursor:
                    # 获取所有表名
                    await cursor.execute("SHOW TABLES")
                    table_names = await cursor.fetchall()
                    logger.debug(f"MySQL数据库共有 {len(table_names)} 张表")

                    for (table_name,) in table_names:
                        # 获取建表SQL（用于提取表注释）
                        await cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                        create_result = await cursor.fetchone()
                        create_sql = create_result[1] if create_result else ""

                        # 提取表注释
                        table_comment = None
                        comment_match = re.search(r"COMMENT\s*=\s*'([^']*)'", create_sql, re.IGNORECASE)
                        if comment_match:
                            table_comment = comment_match.group(1)

                        # 通过 INFORMATION_SCHEMA 获取列信息（更可靠）
                        await cursor.execute(f"""
                            SELECT
                                COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_KEY,
                                COLUMN_DEFAULT, COLUMN_COMMENT
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                            ORDER BY ORDINAL_POSITION
                        """, (ds.database, table_name))
                        col_rows = await cursor.fetchall()
                        columns = []
                        for col in col_rows:
                            columns.append({
                                "name": col[0],
                                "type": col[1],
                                "nullable": col[2] == "YES",
                                "primaryKey": col[3] == "PRI",
                                "default": col[4],
                                "comment": col[5] or "",
                            })

                        # 创建表结构记录
                        table_schema = TableSchema(
                            datasource_id=ds_id,
                            table_name=table_name,
                            table_comment=table_comment or "",
                            columns=json.dumps(columns, ensure_ascii=False),
                        )
                        db.add(table_schema)
                        tables.append(table_schema)
                conn.close()

            elif ds.type == "postgresql":
                logger.debug("开始读取PostgreSQL表结构")
                import asyncpg
                conn = await asyncpg.connect(
                    host=ds.host,
                    port=ds.port,
                    user=ds.username,
                    password=ds.password or "",
                    database=ds.database,
                )
                rows = await conn.fetch("""
                    SELECT table_name, obj_description((table_schema || '.' || table_name)::regclass, 'pg_class')
                    FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
                """)
                logger.debug(f"PostgreSQL数据库共有 {len(rows)} 张表")

                for row in rows:
                    table_name = row['table_name']
                    table_comment = row['obj_description']
                    cols = await conn.fetch(f"""
                        SELECT column_name, data_type, is_nullable, column_default
                        FROM information_schema.columns
                        WHERE table_name = '{table_name}'
                    """)
                    columns = []
                    for col in cols:
                        columns.append({
                            "name": col['column_name'],
                            "type": col['data_type'],
                            "nullable": col['is_nullable'] == 'YES',
                            "default": col['column_default'],
                        })
                    table_schema = TableSchema(
                        datasource_id=ds_id,
                        table_name=table_name,
                        table_comment=table_comment,
                        columns=json.dumps(columns, ensure_ascii=False),
                    )
                    db.add(table_schema)
                    tables.append(table_schema)
                await conn.close()

            elif ds.type == "sqlserver":
                logger.debug("开始读取SQL Server表结构")
                import asyncio
                import pyodbc
                connection_string = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={ds.host},{ds.port};DATABASE={ds.database};UID={ds.username};PWD={ds.password or ''}"
                loop = asyncio.get_event_loop()
                
                def get_connection():
                    return pyodbc.connect(connection_string)
                
                conn = await loop.run_in_executor(None, get_connection)
                
                def get_tables():
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT TABLE_NAME, TABLE_COMMENT
                        FROM INFORMATION_SCHEMA.TABLES
                        WHERE TABLE_TYPE = 'BASE TABLE'
                    """)
                    return cursor.fetchall()
                
                table_rows = await loop.run_in_executor(None, get_tables)
                logger.debug(f"SQL Server数据库共有 {len(table_rows)} 张表")

                for row in table_rows:
                    table_name = row[0]
                    table_comment = row[1] if len(row) > 1 else None

                    def get_columns():
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMNPROPERTY(OBJECT_ID(TABLE_SCHEMA + '.' + TABLE_NAME), COLUMN_NAME, 'IsIdentity') AS IS_IDENTITY
                            FROM INFORMATION_SCHEMA.COLUMNS
                            WHERE TABLE_NAME = ?
                            ORDER BY ORDINAL_POSITION
                        """, (table_name,))
                        return cursor.fetchall()

                    col_rows = await loop.run_in_executor(None, get_columns)
                    columns = []
                    for col in col_rows:
                        columns.append({
                            "name": col[0],
                            "type": col[1],
                            "nullable": col[2] == 'YES',
                            "primaryKey": col[4] == 1 if len(col) > 4 else False,
                            "default": col[3],
                            "comment": "",
                        })
                    table_schema = TableSchema(
                        datasource_id=ds_id,
                        table_name=table_name,
                        table_comment=table_comment,
                        columns=json.dumps(columns, ensure_ascii=False),
                    )
                    db.add(table_schema)
                    tables.append(table_schema)
                conn.close()

            # 步骤4：提交表结构数据
            await db.commit()

            # 步骤5：刷新对象（SQLAlchemy异步模式commit后对象会过期）
            for t in tables:
                await db.refresh(t)

            logger.info(f"同步数据源表结构完成: {ds.name}, 共{len(tables)}张表")
            return tables

        except Exception as e:
            await db.rollback()
            logger.error(f"同步表结构失败: ds_id={ds_id}, error={e}")
            raise BusinessException(code=500, message=f"同步表结构失败: {str(e)}")

    @staticmethod
    async def get_schema(db: AsyncSession, ds_id: int) -> List[TableSchema]:
        """
        获取数据源的表结构列表

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: 表结构列表
        """
        stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())


# 服务实例
datasource_service = DataSourceService()
logger.info("数据源服务实例已创建")
