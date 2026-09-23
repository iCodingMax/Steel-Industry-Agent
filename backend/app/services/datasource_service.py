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
from sqlalchemy import select, delete as sa_delete, text, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.datasource import DataSource, TableSchema, SchemaEmbedding
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
    def _normalize_columns(columns_data) -> str:
        """
        将列信息标准化为可比较的JSON字符串
        用于对比表结构是否发生变化

        :param columns_data: 列信息（JSONB、字符串或列表）
        :return: 标准化后的JSON字符串
        """
        if isinstance(columns_data, str):
            try:
                columns_data = json.loads(columns_data)
            except (json.JSONDecodeError, TypeError):
                columns_data = []
        if not isinstance(columns_data, list):
            columns_data = []
        return json.dumps(columns_data, sort_keys=True, ensure_ascii=False)

    @staticmethod
    def _columns_to_list(columns_data) -> list:
        """
        columns 数据统一转 list（兼容 JSONB list / 历史 JSON 字符串 / 异常数据）

        :param columns_data: 列信息（JSONB、字符串或列表）
        :return: 列信息列表（异常时返回空列表）
        """
        if isinstance(columns_data, str):
            try:
                columns_data = json.loads(columns_data)
            except (json.JSONDecodeError, TypeError):
                return []
        return columns_data if isinstance(columns_data, list) else []

    @staticmethod
    def _apply_remark_backfill(columns: list, remark_map: dict, comment_map: dict) -> tuple:
        """
        字段备注回填（V2.1 双列设计：comment=原字段备注只读，remark=字段备注可编辑）

        回填规则：
            - remark_edited=True（人工编辑过）：保留人工 remark；
              若本次同步的原注释与上次不同，计入 remark_conflicts 供前端提示
            - 未编辑过：remark 跟随本次同步的 comment 刷新，remark_edited=False

        :param columns: 本次同步采集的列信息列表（将原地补充 remark/remark_edited 键）
        :param remark_map: 快照 {col_name: (remark, edited)}（来自同步前的旧数据）
        :param comment_map: 快照 {col_name: 旧comment}（用于冲突统计）
        :return: (回填后的 columns, remark_conflicts 数)
        """
        conflicts = 0
        for col in columns:
            if not isinstance(col, dict) or not col.get("name"):
                continue
            name = col["name"]
            old = remark_map.get(name)
            if old is not None and old[1]:
                # 人工编辑过：保留 remark；原注释已变化时计数提示
                if comment_map.get(name, "") != str(col.get("comment") or ""):
                    conflicts += 1
                col["remark"] = old[0]
                col["remark_edited"] = True
            else:
                # 未编辑过：跟随本次同步的原注释
                col["remark"] = str(col.get("comment") or "")
                col["remark_edited"] = False
        return columns, conflicts

    @staticmethod
    async def sync_schema(db: AsyncSession, ds_id: int) -> dict:
        """
        同步数据源表结构
        从业务数据库读取所有表结构信息，同步到系统数据库的table_schemas表

        同步流程：
        1. 获取数据源配置
        2. 获取已存在的表结构，用于后续对比变更
        3. 清除该数据源的旧表结构记录（避免重复）
        4. 重置PostgreSQL序列（避免主键冲突）
        5. 根据数据库类型读取表和字段信息
        6. 将表结构数据写入系统数据库
        7. 对比新旧表结构，返回变更统计信息

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: 包含表结构列表和变更统计的字典
        :raises BusinessException: 数据源不存在或同步失败时抛出
        """
        ds = await DataSourceService.get_by_id(db, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")

        logger.info(f"开始同步数据源表结构: ID={ds_id}, name={ds.name}, type={ds.type}")

        try:
            # 步骤1：获取已存在的表结构，用于后续对比变更
            existing_stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
            existing_result = await db.execute(existing_stmt)
            existing_tables = {}
            # 字段备注快照（V2.1 双列：先删后插前保存人工编辑的 remark，防丢失）
            existing_remarks = {}   # {table_name: {col_name: (remark, edited)}}
            existing_comments = {}  # {table_name: {col_name: 旧comment}}（冲突统计用）
            for t in existing_result.scalars().all():
                existing_tables[t.table_name] = DataSourceService._normalize_columns(t.columns)
                remark_map = {}
                comment_map = {}
                for c in DataSourceService._columns_to_list(t.columns):
                    if isinstance(c, dict) and c.get("name"):
                        remark_map[c["name"]] = (
                            str(c.get("remark") or ""), bool(c.get("remark_edited"))
                        )
                        comment_map[c["name"]] = str(c.get("comment") or "")
                existing_remarks[t.table_name] = remark_map
                existing_comments[t.table_name] = comment_map
            logger.debug(f"已存在 {len(existing_tables)} 张表的表结构记录")

            # 收集新表结构信息，用于对比变更
            new_tables_info = {}
            remark_conflicts = 0  # 原注释变化但人工备注被保留的字段数（V2.1）

            # 步骤2：清除该数据源的旧表结构记录
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

                        # 字段备注回填（V2.1：人工编辑的 remark 保留，未编辑跟随原注释）
                        columns, col_conflicts = DataSourceService._apply_remark_backfill(
                            columns,
                            existing_remarks.get(table_name, {}),
                            existing_comments.get(table_name, {}),
                        )
                        remark_conflicts += col_conflicts

                        # 记录新表结构信息，用于对比变更
                        new_tables_info[table_name] = columns

                        # 创建表结构记录
                        table_schema = TableSchema(
                            datasource_id=ds_id,
                            table_name=table_name,
                            table_comment=table_comment or "",
                            columns=columns,
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
                    # 字段备注回填（V2.1：人工编辑的 remark 保留，未编辑跟随原注释）
                    columns, col_conflicts = DataSourceService._apply_remark_backfill(
                        columns,
                        existing_remarks.get(table_name, {}),
                        existing_comments.get(table_name, {}),
                    )
                    remark_conflicts += col_conflicts
                    # 记录新表结构信息，用于对比变更
                    new_tables_info[table_name] = columns

                    table_schema = TableSchema(
                        datasource_id=ds_id,
                        table_name=table_name,
                        table_comment=table_comment,
                        columns=columns,
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
                    # 字段备注回填（V2.1：人工编辑的 remark 保留，未编辑跟随原注释）
                    columns, col_conflicts = DataSourceService._apply_remark_backfill(
                        columns,
                        existing_remarks.get(table_name, {}),
                        existing_comments.get(table_name, {}),
                    )
                    remark_conflicts += col_conflicts
                    # 记录新表结构信息，用于对比变更
                    new_tables_info[table_name] = columns

                    table_schema = TableSchema(
                        datasource_id=ds_id,
                        table_name=table_name,
                        table_comment=table_comment,
                        columns=columns,
                    )
                    db.add(table_schema)
                    tables.append(table_schema)
                conn.close()

            # 步骤4：提交表结构数据
            await db.commit()

            # 步骤5：刷新对象（SQLAlchemy异步模式commit后对象会过期）
            for t in tables:
                await db.refresh(t)

            # 步骤6：对比新旧表结构，计算变更数量
            new_names = set(new_tables_info.keys())
            existing_names = set(existing_tables.keys())
            added_count = len(new_names - existing_names)
            removed_count = len(existing_names - new_names)
            updated_count = 0
            for name in (existing_names & new_names):
                new_cols = DataSourceService._normalize_columns(new_tables_info[name])
                if existing_tables[name] != new_cols:
                    updated_count += 1

            # 组装返回结果（在向量钩子前组装，避免钩子失败回滚影响对象状态）
            result = {
                "tables": [t.to_dict() for t in tables],
                "total": len(tables),
                "added": added_count,
                "removed": removed_count,
                "updated": updated_count,
                "remarkConflicts": remark_conflicts,
            }

            # 步骤7：重建该数据源的 Schema 向量索引（一期升级）
            # 旁路原则：重建失败仅告警，不影响同步主流程（向量召回会自动回退关键词逻辑）
            # 门控条件：仅当结构真正变更（新增/移除/更新表）或索引为空时才重建。
            # 若无条件重建，schema_version 每次同步都会 +1（如开发模式 --reload 每次重启
            # 都会触发 seed → sync_schema），导致所有示例SQL 被"版本漂移"防护误伤跳过，
            # Few-shot 召回被清空
            embedding_count = 0
            try:
                from app.models.term import Term
                from app.services.schema_embedding_service import SchemaEmbeddingService
                schema_changed = (
                    added_count > 0 or removed_count > 0 or updated_count > 0
                )
                has_index = (
                    await db.execute(
                        select(func.count()).select_from(SchemaEmbedding).where(
                            SchemaEmbedding.datasource_id == ds_id
                        )
                    )
                ).scalar() or 0
                if schema_changed or not has_index:
                    terms_result = await db.execute(select(Term))
                    terms = list(terms_result.scalars().all())
                    embedding_count = await SchemaEmbeddingService.rebuild_datasource(
                        db, ds_id, terms=terms
                    )
                    await db.commit()
                else:
                    logger.debug(
                        f"Schema无变更且向量索引已存在，跳过索引重建: ds_id={ds_id}"
                    )
            except Exception as embed_err:
                await db.rollback()
                logger.warning(
                    f"Schema向量索引重建失败(旁路忽略): ds_id={ds_id}, "
                    f"{type(embed_err).__name__}: {embed_err}"
                )

            logger.info(
                f"同步数据源表结构完成: {ds.name}, 共{len(tables)}张表 "
                f"(新增{added_count}, 移除{removed_count}, 更新{updated_count}, "
                f"向量化{embedding_count})"
            )
            result["schemaEmbeddings"] = embedding_count

            # 步骤8：表关系钩子（V2.1 二期：失效校验 + 三通道采集）
            # 旁路原则：失败仅告警，不影响同步主流程
            try:
                from app.services.table_relation_service import table_relation_service
                relation_stats = await table_relation_service.on_sync_schema(db, ds_id)
                result["relations"] = relation_stats
                logger.info(f"表关系钩子完成: ds_id={ds_id}, {relation_stats}")
            except Exception as rel_err:
                logger.warning(
                    f"表关系钩子失败(旁路忽略): ds_id={ds_id}, "
                    f"{type(rel_err).__name__}: {rel_err}"
                )

            return result

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

    @staticmethod
    async def update_column_remarks(
        db: AsyncSession,
        ds_id: int,
        table_name: str,
        remarks: List[dict],
    ) -> dict:
        """
        批量保存表字段备注（V2.1 双列：remark 可编辑，保存即置 remark_edited=True）

        保存成功后重建该表的 SchemaEmbedding（旁路：失败仅告警，不影响保存结果），
        保证向量召回与 LLM Prompt 同步使用最新字段备注。

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param table_name: 表名
        :param remarks: 字段备注列表 [{"name": 字段名, "remark": 字段备注, "reset": 是否重置为原字段备注}]
        :return: {"updated": 实际更新字段数, "embedded": 向量重建是否成功}
        :raises BusinessException: 表结构不存在时抛出
        """
        stmt = select(TableSchema).where(
            TableSchema.datasource_id == ds_id,
            TableSchema.table_name == table_name,
        )
        schema = (await db.execute(stmt)).scalar_one_or_none()
        if not schema:
            raise BusinessException(code=404, message="表结构不存在")

        # 入参归一化：{字段名: (备注文本, 是否重置)}
        remark_payload = {
            str(r.get("name")): (str(r.get("remark") or ""), bool(r.get("reset")))
            for r in remarks
            if isinstance(r, dict) and r.get("name")
        }

        columns = DataSourceService._columns_to_list(schema.columns)
        updated = 0
        for col in columns:
            if isinstance(col, dict) and col.get("name") in remark_payload:
                remark, reset = remark_payload[col["name"]]
                if reset:
                    # 重置为原字段备注：remark=comment 且 remark_edited=False（后续同步跟随 comment 刷新）
                    col["remark"] = str(col.get("comment") or "")
                    col["remark_edited"] = False
                else:
                    col["remark"] = remark
                    col["remark_edited"] = True
                updated += 1

        # 重新赋值触发 JSONB 变更检测
        schema.columns = columns
        await db.commit()
        logger.info(f"字段备注保存: ds_id={ds_id}, table={table_name}, 更新{updated}个字段")

        # 单表向量重建（旁路）
        embedded = True
        try:
            from app.models.term import Term
            from app.services.schema_embedding_service import SchemaEmbeddingService
            terms_result = await db.execute(select(Term))
            terms = list(terms_result.scalars().all())
            await SchemaEmbeddingService.rebuild_table(
                db, ds_id, table_name, terms=terms
            )
            await db.commit()
        except Exception as embed_err:
            await db.rollback()
            embedded = False
            logger.warning(
                f"字段备注保存后向量重建失败(旁路忽略): ds_id={ds_id}, "
                f"table={table_name}, {type(embed_err).__name__}: {embed_err}"
            )

        return {"updated": updated, "embedded": embedded}


# 服务实例
datasource_service = DataSourceService()
logger.info("数据源服务实例已创建")
