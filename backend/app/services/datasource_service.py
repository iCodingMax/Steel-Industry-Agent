"""
数据源服务
"""
import json
from typing import List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.datasource import DataSource, TableSchema
from app.schemas.datasource import DataSourceCreate, DataSourceUpdate, TestConnectionRequest
from app.middlewares.exception_handler import BusinessException


class DataSourceService:
    """数据源服务类"""

    @staticmethod
    async def create(db: AsyncSession, data: DataSourceCreate, user_id: Optional[int] = None) -> DataSource:
        """创建数据源"""
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
        logger.info(f"创建数据源: {ds.name} (ID: {ds.id})")
        return ds

    @staticmethod
    async def get_by_id(db: AsyncSession, ds_id: int) -> Optional[DataSource]:
        """根据ID获取数据源"""
        stmt = select(DataSource).where(DataSource.id == ds_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[DataSource]:
        """获取所有数据源"""
        stmt = select(DataSource).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db: AsyncSession, ds_id: int, data: DataSourceUpdate) -> Optional[DataSource]:
        """更新数据源"""
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(ds, key):
                setattr(ds, key, value)

        await db.commit()
        await db.refresh(ds)
        logger.info(f"更新数据源: {ds.name} (ID: {ds.id})")
        return ds

    @staticmethod
    async def delete(db: AsyncSession, ds_id: int) -> None:
        """删除数据源"""
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        await db.delete(ds)
        await db.commit()
        logger.info(f"删除数据源: {ds.name} (ID: {ds_id})")

    @staticmethod
    async def test_connection(db: AsyncSession, data: TestConnectionRequest) -> dict:
        """测试数据库连接"""
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
            elif data.type == "oracle":
                import oracledb
                oracledb.init_oracle_client()
                conn = await oracledb.create_pool_async(
                    user=data.username,
                    password=data.password or "",
                    dsn=f"{data.host}:{data.port}/{data.database}",
                    min=1,
                    max=1,
                )
                async with conn.acquire() as connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute("SELECT 1 FROM DUAL")
                await conn.close()
            else:
                raise BusinessException(code=400, message=f"不支持的数据库类型: {data.type}")

            logger.info(f"数据库连接测试成功: {data.type}://{data.host}:{data.port}/{data.database}")
            return {"success": True, "message": "连接成功"}
        except Exception as e:
            logger.error(f"数据库连接测试失败: {e}")
            return {"success": False, "message": str(e)}

    @staticmethod
    async def sync_schema(db: AsyncSession, ds_id: int) -> List[TableSchema]:
        """同步数据源表结构"""
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        try:
            # 同步前先清除该数据源的旧表结构记录，避免重复
            from sqlalchemy import delete as sa_delete
            await db.execute(sa_delete(TableSchema).where(TableSchema.datasource_id == ds_id))

            tables = []
            if ds.type == "mysql":
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
                    for (table_name,) in table_names:
                        # 获取建表SQL（用于提取表注释）
                        await cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                        create_result = await cursor.fetchone()
                        create_sql = create_result[1] if create_result else ""

                        # 提取表注释
                        table_comment = None
                        import re
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
            elif ds.type == "oracle":
                import oracledb
                oracledb.init_oracle_client()
                pool = await oracledb.create_pool_async(
                    user=ds.username,
                    password=ds.password or "",
                    dsn=f"{ds.host}:{ds.port}/{ds.database}",
                    min=1,
                    max=5,
                )
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute("""
                            SELECT table_name
                            FROM all_tables
                            WHERE owner = UPPER(:owner)
                        """, [ds.username.upper()])
                        table_rows = await cursor.fetchall()
                        for (table_name,) in table_rows:
                            await cursor.execute("""
                                SELECT comments
                                FROM all_tab_comments
                                WHERE owner = UPPER(:owner) AND table_name = :table_name
                            """, [ds.username.upper(), table_name])
                            comment_row = await cursor.fetchone()
                            table_comment = comment_row[0] if comment_row else None

                            await cursor.execute("""
                                SELECT column_name, data_type, nullable, data_default
                                FROM all_tab_columns
                                WHERE owner = UPPER(:owner) AND table_name = :table_name
                            """, [ds.username.upper(), table_name])
                            cols = await cursor.fetchall()
                            columns = []
                            for col in cols:
                                columns.append({
                                    "name": col[0],
                                    "type": col[1],
                                    "nullable": col[2] == 'Y',
                                    "default": col[3],
                                })
                            table_schema = TableSchema(
                                datasource_id=ds_id,
                                table_name=table_name,
                                table_comment=table_comment,
                                columns=json.dumps(columns, ensure_ascii=False),
                            )
                            db.add(table_schema)
                            tables.append(table_schema)
                await pool.close()

            await db.commit()
            # commit后对象会过期，需要刷新才能在to_dict时正常访问属性
            for t in tables:
                await db.refresh(t)
            logger.info(f"同步数据源表结构完成: {ds.name}, 共{len(tables)}张表")
            return tables
        except Exception as e:
            await db.rollback()
            logger.error(f"同步表结构失败: {e}")
            raise BusinessException(code=500, message=f"同步表结构失败: {str(e)}")

    @staticmethod
    async def get_schema(db: AsyncSession, ds_id: int) -> List[TableSchema]:
        """获取数据源表结构"""
        stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())


datasource_service = DataSourceService()
