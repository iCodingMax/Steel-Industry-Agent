"""
表关系元数据服务（NL2SQL 升级二期：联表查询关联键白名单）

功能模块：
    1. normalize_pair        —— 四元组端点规范化（无向边唯一存储方向）
    2. CRUD / 批量操作       —— 列表/新建/编辑/删除/批量确认/批量忽略
    3. collect_relations     —— 关系采集三通道（外键 / 同名同类型推荐 / 人工录入走CRUD）
    4. probe_relation        —— SQL 探测（基数实测 + 放大系数，结论缓存到 relation 行）
    5. get_relation_graph    —— nodes + edges 聚合（画布/总览一次取全量，内存缓存）
    6. on_sync_schema        —— 同步表结构钩子：失效校验 + 三通道采集

设计要点（源自方案 4.1/4.2/4.4.5）：
    - 全程以 table_name/column 字符串关联，禁止 table_schema_id 外键
    - 四道防线防重复：存储规范化 / 唯一约束 / 无序组合采集 / 校验无序比对
    - auto_guess 候选一律 inactive（待人工确认），不参与 JOIN 白名单
    - 探测 SQL 服务端拼装（不接受前端SQL），只读 + 30s 超时 + LIMIT 100001 防大表全扫
    - 钩子/探测失败一律旁路（仅告警），不影响同步主流程与 NL2SQL 主链路
"""
import asyncio
import itertools
import time
import uuid
from typing import Dict, List, Optional, Set, Tuple

from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import DataSource, TableSchema
from app.models.table_relation import TableRelation
from app.middlewares.exception_handler import BusinessException
from app.services.datasource_service import DataSourceService


# 同名推荐黑名单（无业务含义字段，关联必为误报）
AUTO_GUESS_BLACKLIST = {
    "ID", "IS_DELETED", "CREATED_AT", "UPDATED_AT", "CREATE_TIME", "UPDATE_TIME",
    "CREATED_BY", "UPDATED_BY", "CREATE_BY", "UPDATE_BY", "REMARK", "VERSION",
    "ROW_VERSION", "TENANT_ID",
}

# 同名推荐单次采集候选上限（防大库组合爆炸）
AUTO_GUESS_MAX_CANDIDATES = 200

# 探测 SQL 子查询行数上限（防大表全扫）
PROBE_ROW_LIMIT = 100001

# 探测超时（秒）
PROBE_TIMEOUT_SECONDS = 30


def normalize_pair(
    left_table: str, left_column: str, right_table: str, right_column: str
) -> Tuple[str, str, str, str]:
    """
    关系四元组端点规范化（无向边 → 唯一存储方向）

    规范：left_table 字典序 > right_table 时交换四元组；
    同表自关联（left_table == right_table）时按 (table, column) 元组字典序交换。

    :param left_table: 左表名
    :param left_column: 左表字段
    :param right_table: 右表名
    :param right_column: 右表字段
    :return: 规范化后的 (left_table, left_column, right_table, right_column)
    """
    lt, lc, rt, rc = left_table.strip(), left_column.strip(), right_table.strip(), right_column.strip()
    if (lt, lc) > (rt, rc):
        lt, lc, rt, rc = rt, rc, lt, lc
    return lt, lc, rt, rc


class TableRelationService:
    """表关系元数据服务"""

    # relation-graph 内存缓存 {datasource_id: (写入时间, graph)}
    _graph_cache: Dict[int, Tuple[float, dict]] = {}
    # 缓存有效期（秒），超时自动失效兜底
    _graph_cache_ttl = 300

    # ---------- 基础查询 ----------

    @staticmethod
    async def _get_datasource(db: AsyncSession, ds_id: int) -> DataSource:
        """获取数据源，不存在抛 404"""
        ds = await db.get(DataSource, ds_id)
        if not ds:
            raise BusinessException(code=404, message="数据源不存在")
        return ds

    @staticmethod
    async def get_relation(db: AsyncSession, ds_id: int, rel_id: int) -> TableRelation:
        """获取单条关系，不存在或归属不符抛 404"""
        rel = await db.get(TableRelation, rel_id)
        if not rel or rel.datasource_id != ds_id:
            raise BusinessException(code=404, message="表关系不存在")
        return rel

    @staticmethod
    async def list_relations(
        db: AsyncSession,
        ds_id: int,
        status: Optional[str] = None,
        source: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        分页查询表关系列表

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param status: 状态过滤 active/inactive/ignored
        :param source: 来源过滤 foreign_key/auto_guess/manual
        :param keyword: 关键词（匹配表名/字段名/关系描述）
        :param page: 页码（1起）
        :param page_size: 每页条数
        :return: {"total": 总数, "list": [关系字典]}
        """
        conditions = [TableRelation.datasource_id == ds_id]
        if status:
            conditions.append(TableRelation.status == status)
        if source:
            conditions.append(TableRelation.source == source)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conditions.append(
                (TableRelation.left_table.like(kw))
                | (TableRelation.right_table.like(kw))
                | (TableRelation.left_column.like(kw))
                | (TableRelation.right_column.like(kw))
                | (TableRelation.relation_desc.like(kw))
            )

        total = (
            await db.execute(select(func.count(TableRelation.id)).where(*conditions))
        ).scalar() or 0

        stmt = (
            select(TableRelation)
            .where(*conditions)
            .order_by(TableRelation.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return {"total": total, "list": [r.to_dict() for r in rows]}

    # ---------- CRUD / 批量操作 ----------

    @staticmethod
    async def create_relation(db: AsyncSession, ds_id: int, data: dict) -> TableRelation:
        """
        新建关系（人工录入：表单/画布连线/探测后保存）

        存储前规范化端点方向；四元组已存在时直接返回已有记录（幂等）。

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param data: {leftTable, leftColumn, rightTable, rightColumn, cardinality?,
                      joinType?, relationDesc?, relationGroup?}
        :return: 关系记录
        """
        await TableRelationService._get_datasource(db, ds_id)

        lt, lc, rt, rc = normalize_pair(
            data["leftTable"], data["leftColumn"], data["rightTable"], data["rightColumn"]
        )

        # 幂等：同四元组已存在则直接返回
        existing = await TableRelationService._find_by_quad(db, ds_id, lt, lc, rt, rc)
        if existing:
            return existing

        rel = TableRelation(
            datasource_id=ds_id,
            left_table=lt,
            left_column=lc,
            right_table=rt,
            right_column=rc,
            join_type=data.get("joinType") or "inner",
            relation_desc=data.get("relationDesc"),
            cardinality=data.get("cardinality") or "1:1",
            relation_group=data.get("relationGroup"),
            source="manual",
            status="active",
        )
        db.add(rel)
        await db.commit()
        await db.refresh(rel)
        TableRelationService._invalidate_graph_cache(ds_id)
        logger.info(f"新建表关系: ds_id={ds_id}, {lt}.{lc} = {rt}.{rc}")
        return rel

    @staticmethod
    async def _find_by_quad(
        db: AsyncSession, ds_id: int, lt: str, lc: str, rt: str, rc: str
    ) -> Optional[TableRelation]:
        """按规范化四元组查找关系（去重防线：规范化比对）"""
        stmt = select(TableRelation).where(
            TableRelation.datasource_id == ds_id,
            TableRelation.left_table == lt,
            TableRelation.left_column == lc,
            TableRelation.right_table == rt,
            TableRelation.right_column == rc,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def update_relation(db: AsyncSession, ds_id: int, rel_id: int, data: dict) -> TableRelation:
        """
        编辑关系（仅允许修改 基数/描述/JOIN类型/状态/关联键分组）

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param rel_id: 关系ID
        :param data: {cardinality?, joinType?, relationDesc?, status?, relationGroup?}
        :return: 更新后的关系记录
        """
        rel = await TableRelationService.get_relation(db, ds_id, rel_id)
        if data.get("status") and data["status"] not in ("active", "inactive", "ignored"):
            raise BusinessException(code=400, message=f"非法状态值: {data['status']}")
        if data.get("cardinality") and data["cardinality"] not in ("1:1", "1:N", "N:1", "M:N"):
            raise BusinessException(code=400, message=f"非法基数: {data['cardinality']}")
        if data.get("joinType") and data["joinType"] not in ("inner", "left"):
            raise BusinessException(code=400, message=f"非法JOIN类型: {data['joinType']}")

        for key in ("cardinality", "joinType", "relationDesc", "status", "relationGroup"):
            if key in data and data[key] is not None:
                setattr(rel, {
                    "joinType": "join_type",
                    "relationDesc": "relation_desc",
                    "relationGroup": "relation_group",
                }.get(key, key), data[key])

        await db.commit()
        await db.refresh(rel)
        TableRelationService._invalidate_graph_cache(ds_id)
        return rel

    @staticmethod
    async def delete_relation(db: AsyncSession, ds_id: int, rel_id: int) -> None:
        """
        删除关系（仅 manual/auto_guess；外键关系为数据库声明的事实，只允许停用）

        :raises BusinessException: 外键来源关系返回 400
        """
        rel = await TableRelationService.get_relation(db, ds_id, rel_id)
        if rel.source == "foreign_key":
            raise BusinessException(code=400, message="外键关系为数据库声明的事实，只允许停用（置为 ignored）")
        await db.delete(rel)
        await db.commit()
        TableRelationService._invalidate_graph_cache(ds_id)
        logger.info(f"删除表关系: ds_id={ds_id}, id={rel_id}")

    @staticmethod
    async def batch_confirm(db: AsyncSession, ds_id: int, ids: List[int], cardinality: Optional[str] = None) -> int:
        """
        批量确认候选关系（inactive → active）

        :param ids: 关系ID列表
        :param cardinality: 可选统一基数（确认时补充业务知识）
        :return: 实际确认条数
        """
        if cardinality and cardinality not in ("1:1", "1:N", "N:1", "M:N"):
            raise BusinessException(code=400, message=f"非法基数: {cardinality}")
        updated = 0
        for rel in await TableRelationService._get_by_ids(db, ds_id, ids):
            rel.status = "active"
            if cardinality:
                rel.cardinality = cardinality
            updated += 1
        await db.commit()
        TableRelationService._invalidate_graph_cache(ds_id)
        logger.info(f"批量确认表关系: ds_id={ds_id}, 确认{updated}条")
        return updated

    @staticmethod
    async def batch_ignore(db: AsyncSession, ds_id: int, ids: List[int]) -> int:
        """批量忽略关系（→ ignored，不参与白名单）"""
        updated = 0
        for rel in await TableRelationService._get_by_ids(db, ds_id, ids):
            rel.status = "ignored"
            updated += 1
        await db.commit()
        TableRelationService._invalidate_graph_cache(ds_id)
        logger.info(f"批量忽略表关系: ds_id={ds_id}, 忽略{updated}条")
        return updated

    @staticmethod
    async def _get_by_ids(db: AsyncSession, ds_id: int, ids: List[int]) -> List[TableRelation]:
        """按ID列表查询归属该数据源的关系"""
        if not ids:
            return []
        stmt = select(TableRelation).where(
            TableRelation.datasource_id == ds_id,
            TableRelation.id.in_(ids),
        )
        return list((await db.execute(stmt)).scalars().all())

    # ---------- NL2SQL 白名单 ----------

    @staticmethod
    async def get_active_relations(db: AsyncSession, ds_id: int) -> Set[Tuple[str, str, str, str]]:
        """
        获取全部 active 关系的规范化四元组集合（_validate_joins 白名单）

        :return: {(left_table, left_column, right_table, right_column)}
        """
        stmt = select(TableRelation).where(
            TableRelation.datasource_id == ds_id,
            TableRelation.status == "active",
        )
        rows = list((await db.execute(stmt)).scalars().all())
        return {
            normalize_pair(r.left_table, r.left_column, r.right_table, r.right_column)
            for r in rows
        }

    # ---------- 关系采集三通道 ----------

    @staticmethod
    async def _collect_foreign_keys(ds: DataSource) -> List[dict]:
        """
        通道一：数据库外键采集

        MySQL: INFORMATION_SCHEMA.KEY_COLUMN_USAGE (REFERENCED_TABLE_NAME IS NOT NULL)
        PostgreSQL: pg_constraint contype='f'
        SQL Server: 暂不支持（返回空并告警）

        :param ds: 数据源配置
        :return: [{leftTable, leftColumn, rightTable, rightColumn}]
        """
        pairs: List[dict] = []
        try:
            if ds.type == "mysql":
                import aiomysql
                conn = await asyncio.wait_for(
                    aiomysql.connect(
                        host=ds.host, port=ds.port, user=ds.username,
                        password=ds.password or "", db=ds.database,
                        charset=ds.charset or "utf8mb4",
                    ),
                    timeout=PROBE_TIMEOUT_SECONDS,
                )
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME
                        FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                        WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL
                        """,
                        (ds.database,),
                    )
                    rows = await cursor.fetchall()
                conn.close()
                for table_name, column_name, ref_table, ref_column in rows:
                    pairs.append({
                        "leftTable": table_name, "leftColumn": column_name,
                        "rightTable": ref_table, "rightColumn": ref_column,
                    })
            elif ds.type == "postgresql":
                import asyncpg
                conn = await asyncio.wait_for(
                    asyncpg.connect(
                        host=ds.host, port=ds.port, user=ds.username,
                        password=ds.password or "", database=ds.database,
                    ),
                    timeout=PROBE_TIMEOUT_SECONDS,
                )
                rows = await conn.fetch(
                    """
                    SELECT src_table.relname AS table_name,
                           src_col.attname AS column_name,
                           dst_table.relname AS referenced_table_name,
                           dst_col.attname AS referenced_column_name
                    FROM pg_constraint con
                    JOIN pg_class src_table ON con.conrelid = src_table.oid
                    JOIN pg_class dst_table ON con.confrelid = dst_table.oid
                    CROSS JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS sk(attnum, ord)
                    JOIN LATERAL unnest(con.confkey) WITH ORDINALITY AS dk(attnum, ord)
                      ON sk.ord = dk.ord
                    JOIN pg_attribute src_col
                      ON src_col.attrelid = con.conrelid AND src_col.attnum = sk.attnum
                    JOIN pg_attribute dst_col
                      ON dst_col.attrelid = con.confrelid AND dst_col.attnum = dk.attnum
                    WHERE con.contype = 'f'
                    """
                )
                await conn.close()
                for row in rows:
                    pairs.append({
                        "leftTable": row["table_name"], "leftColumn": row["column_name"],
                        "rightTable": row["referenced_table_name"], "rightColumn": row["referenced_column_name"],
                    })
            else:
                logger.warning(f"外键采集暂不支持该数据库类型: type={ds.type}, ds_id={ds.id}")
        except Exception as e:
            # 旁路：采集失败仅告警
            logger.warning(f"外键采集失败(旁路忽略): ds_id={ds.id}, {type(e).__name__}: {e}")
        return pairs

    @staticmethod
    def _collect_same_name_candidates(
        schemas: List[TableSchema], existing_quads: Set[Tuple[str, str, str, str]]
    ) -> List[dict]:
        """
        通道二：同名同类型字段推荐（两两表无序组合，黑名单排除）

        :param schemas: 该数据源全部表结构（TableSchema ORM）
        :param existing_quads: 已存在关系的规范化四元组集合（避免重复推荐）
        :return: 候选关系列表（数量上限 AUTO_GUESS_MAX_CANDIDATES）
        """
        # 预解析列信息 {table: {col_name: type}}
        table_columns: Dict[str, Dict[str, str]] = {}
        for schema in schemas:
            cols = DataSourceService._columns_to_list(schema.columns)
            table_columns[schema.table_name] = {
                str(c.get("name")): str(c.get("type") or "")
                for c in cols if isinstance(c, dict) and c.get("name")
            }

        candidates: List[dict] = []
        for t1, t2 in itertools.combinations(sorted(table_columns.keys()), 2):
            cols1, cols2 = table_columns[t1], table_columns[t2]
            for col in sorted(set(cols1.keys()) & set(cols2.keys())):
                if col.upper() in AUTO_GUESS_BLACKLIST:
                    continue
                # 同名且同类型才推荐（类型宽松比对：小写去空格）
                if cols1[col].strip().lower() != cols2[col].strip().lower():
                    continue
                lt, lc, rt, rc = normalize_pair(t1, col, t2, col)
                if (lt, lc, rt, rc) in existing_quads:
                    continue
                candidates.append({
                    "leftTable": lt, "leftColumn": lc, "rightTable": rt, "rightColumn": rc,
                })
                if len(candidates) >= AUTO_GUESS_MAX_CANDIDATES:
                    logger.warning(
                        f"同名推荐候选达到上限{AUTO_GUESS_MAX_CANDIDATES}，截断剩余组合"
                    )
                    return candidates
        return candidates

    @classmethod
    async def collect_relations(cls, db: AsyncSession, ds_id: int) -> dict:
        """
        执行三通道采集（外键 + 同名推荐；人工录入走 create_relation）

        入库规则：
            - 外键: source=foreign_key, status=active（数据库声明的事实）
            - 同名推荐: source=auto_guess, status=inactive（待人工确认）
            - 已存在四元组（任意来源/状态）跳过，不覆盖人工标注

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: {"foreignKeys": 外键新增数, "autoGuess": 推荐新增数, "skipped": 已存在跳过数}
        """
        ds = await cls._get_datasource(db, ds_id)

        # 现存四元组（规范化）
        stmt = select(TableRelation).where(TableRelation.datasource_id == ds_id)
        existing_rows = list((await db.execute(stmt)).scalars().all())
        existing_quads: Set[Tuple[str, str, str, str]] = {
            normalize_pair(r.left_table, r.left_column, r.right_table, r.right_column)
            for r in existing_rows
        }

        fk_added, guess_added, skipped = 0, 0, 0

        # 通道一：外键
        fk_pairs = await cls._collect_foreign_keys(ds)
        for p in fk_pairs:
            lt, lc, rt, rc = normalize_pair(p["leftTable"], p["leftColumn"], p["rightTable"], p["rightColumn"])
            if (lt, lc, rt, rc) in existing_quads:
                skipped += 1
                continue
            db.add(TableRelation(
                datasource_id=ds_id, left_table=lt, left_column=lc,
                right_table=rt, right_column=rc,
                source="foreign_key", status="active", cardinality="1:1",
                relation_desc="数据库外键声明",
            ))
            existing_quads.add((lt, lc, rt, rc))
            fk_added += 1

        # 通道二：同名同类型推荐
        schema_stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
        schemas = list((await db.execute(schema_stmt)).scalars().all())
        guess_pairs = cls._collect_same_name_candidates(schemas, existing_quads)
        for p in guess_pairs:
            lt, lc, rt, rc = normalize_pair(p["leftTable"], p["leftColumn"], p["rightTable"], p["rightColumn"])
            if (lt, lc, rt, rc) in existing_quads:
                skipped += 1
                continue
            db.add(TableRelation(
                datasource_id=ds_id, left_table=lt, left_column=lc,
                right_table=rt, right_column=rc,
                source="auto_guess", status="inactive", cardinality="1:N",
            ))
            existing_quads.add((lt, lc, rt, rc))
            guess_added += 1

        if fk_added or guess_added:
            await db.commit()
        cls._invalidate_graph_cache(ds_id)
        logger.info(
            f"表关系采集完成: ds_id={ds_id}, 外键新增{fk_added}, 推荐新增{guess_added}, 跳过{skipped}"
        )
        return {"foreignKeys": fk_added, "autoGuess": guess_added, "skipped": skipped}

    # ---------- 同步钩子 ----------

    @classmethod
    async def on_sync_schema(cls, db: AsyncSession, ds_id: int) -> dict:
        """
        sync_schema 钩子：失效校验 + 三通道采集（均旁路，失败仅告警）

        失效校验：关系引用的表/字段在新 Schema 中不存在时置 inactive（方案 8.2 风险6）。

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :return: {"invalidated": 置失效条数, ...collect_relations 返回}
        """
        stats: dict = {"invalidated": 0}

        # 1. 失效校验（引用的表/字段已不存在 → inactive）
        schema_stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
        schemas = list((await db.execute(schema_stmt)).scalars().all())
        valid_tables: Dict[str, Set[str]] = {
            s.table_name: {
                str(c.get("name"))
                for c in DataSourceService._columns_to_list(s.columns)
                if isinstance(c, dict) and c.get("name")
            }
            for s in schemas
        }

        rel_stmt = select(TableRelation).where(
            TableRelation.datasource_id == ds_id,
            TableRelation.status == "active",
        )
        active_rows = list((await db.execute(rel_stmt)).scalars().all())
        changed = False
        for rel in active_rows:
            left_ok = rel.left_table in valid_tables and rel.left_column in valid_tables[rel.left_table]
            right_ok = rel.right_table in valid_tables and rel.right_column in valid_tables[rel.right_table]
            if not (left_ok and right_ok):
                rel.status = "inactive"
                stats["invalidated"] += 1
                changed = True
                logger.warning(
                    f"表关系引用失效置inactive: ds_id={ds_id}, id={rel.id}, "
                    f"{rel.left_table}.{rel.left_column} = {rel.right_table}.{rel.right_column}"
                )
        if changed:
            await db.commit()

        # 2. 三通道采集
        try:
            collect_stats = await cls.collect_relations(db, ds_id)
            stats.update(collect_stats)
        except Exception as e:
            await db.rollback()
            logger.warning(f"表关系采集失败(旁路忽略): ds_id={ds_id}, {type(e).__name__}: {e}")

        cls._invalidate_graph_cache(ds_id)
        return stats

    # ---------- SQL 探测 ----------

    @staticmethod
    async def _run_probe_sql(ds: DataSource, sql: str) -> Tuple[int, int, int]:
        """
        在业务库执行探测 SQL（只读 + 30s 超时）

        :param ds: 数据源配置
        :param sql: 服务端拼装的探测 SQL
        :return: (joined_rows, left_distinct, right_distinct)
        :raises BusinessException: 连接/执行失败时抛出
        """
        try:
            if ds.type == "mysql":
                import aiomysql
                conn = await asyncio.wait_for(
                    aiomysql.connect(
                        host=ds.host, port=ds.port, user=ds.username,
                        password=ds.password or "", db=ds.database,
                        charset=ds.charset or "utf8mb4",
                    ),
                    timeout=PROBE_TIMEOUT_SECONDS,
                )
                try:
                    async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
                        async with conn.cursor() as cursor:
                            await cursor.execute(sql)
                            row = await cursor.fetchone()
                finally:
                    conn.close()
                return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
            elif ds.type == "postgresql":
                import asyncpg
                conn = await asyncio.wait_for(
                    asyncpg.connect(
                        host=ds.host, port=ds.port, user=ds.username,
                        password=ds.password or "", database=ds.database,
                    ),
                    timeout=PROBE_TIMEOUT_SECONDS,
                )
                try:
                    async with asyncio.timeout(PROBE_TIMEOUT_SECONDS):
                        row = await conn.fetchrow(sql)
                finally:
                    await conn.close()
                return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0)
            else:
                raise BusinessException(code=400, message=f"探测暂不支持数据库类型: {ds.type}")
        except BusinessException:
            raise
        except Exception as e:
            raise BusinessException(code=500, message=f"探测执行失败: {str(e)}") from e

    @staticmethod
    def _build_probe_sql(
        ds: DataSource, lt: str, lc: str, rt: str, rc: str
    ) -> str:
        """
        服务端拼装探测 SQL（不接受前端传入SQL）

        结构：COUNT(*) + 左右字段 DISTINCT 计数，子查询 LIMIT 100001 防大表全扫。

        :param ds: 数据源配置（决定方言引号风格）
        :return: 探测 SQL
        """
        if ds.type == "mysql":
            q = "`{}`"
            inner = (
                f"SELECT {q.format(lt)}.{q.format(lc)} AS lc, {q.format(rt)}.{q.format(rc)} AS rc "
                f"FROM {q.format(lt)} "
                f"JOIN {q.format(rt)} ON {q.format(lt)}.{q.format(lc)} = {q.format(rt)}.{q.format(rc)} "
                f"LIMIT {PROBE_ROW_LIMIT}"
            )
            return (
                f"SELECT COUNT(*) AS joined_rows, "
                f"COUNT(DISTINCT probe.lc) AS left_distinct, "
                f"COUNT(DISTINCT probe.rc) AS right_distinct "
                f"FROM ({inner}) probe"
            )
        q = '"{}"'
        inner = (
            f"SELECT {q.format(lt)}.{q.format(lc)} AS lc, {q.format(rt)}.{q.format(rc)} AS rc "
            f"FROM {q.format(lt)} "
            f"JOIN {q.format(rt)} ON {q.format(lt)}.{q.format(lc)} = {q.format(rt)}.{q.format(rc)} "
            f"LIMIT {PROBE_ROW_LIMIT}"
        )
        return (
            f"SELECT COUNT(*) AS joined_rows, "
            f"COUNT(DISTINCT probe.lc) AS left_distinct, "
            f"COUNT(DISTINCT probe.rc) AS right_distinct "
            f"FROM ({inner}) probe"
        )

    @staticmethod
    def _judge_cardinality(
        joined_rows: int, left_distinct: int, right_distinct: int
    ) -> Tuple[Optional[float], str]:
        """
        探测结论判定（规范化方向：左端→右端基数）

        :param joined_rows: JOIN 后行数
        :param left_distinct: 左字段去重数
        :param right_distinct: 右字段去重数
        :return: (放大系数 factor, 基数判定 verdict)
        """
        if left_distinct == 0 or right_distinct == 0:
            return None, "无匹配数据"
        f_left = joined_rows / left_distinct    # 左端一键平均匹配右表行数
        f_right = joined_rows / right_distinct  # 右端一键平均匹配左表行数
        factor = round(max(f_left, f_right), 2)

        if f_left <= 1.05 and f_right <= 1.05:
            verdict = "1:1"
        elif f_left <= 1.05 and f_right > 1.05:
            verdict = "1:N"
        elif f_left > 1.05 and f_right <= 1.05:
            verdict = "N:1"
        else:
            verdict = "M:N"
        return factor, verdict

    @classmethod
    async def probe_relation(cls, db: AsyncSession, ds_id: int, data: dict) -> dict:
        """
        SQL 探测：基数实测 + 放大系数（录入时暴露关联放大风险）

        流程：
            1. 校验表/字段存在于 Schema 缓存（引用不存在直接 400）
            2. 服务端拼装探测 SQL（子查询 LIMIT 防全扫）
            3. 业务库执行（只读 + 30s 超时）
            4. 判定基数结论，缓存到已存在 relation 行的 probe 字段

        :param data: {leftTable, leftColumn, rightTable, rightColumn}
        :return: {joinedRows, leftDistinct, rightDistinct, factor, verdict, truncated}
        """
        ds = await cls._get_datasource(db, ds_id)

        lt, lc, rt, rc = normalize_pair(
            data["leftTable"], data["leftColumn"], data["rightTable"], data["rightColumn"]
        )

        # 1. 引用校验（基于 Schema 缓存，不发业务库请求）
        schema_stmt = select(TableSchema).where(
            TableSchema.datasource_id == ds_id,
            TableSchema.table_name.in_([lt, rt]),
        )
        schemas = {s.table_name: s for s in (await db.execute(schema_stmt)).scalars().all()}
        if lt not in schemas or rt not in schemas:
            raise BusinessException(code=400, message=f"引用表不在Schema中: {lt if lt not in schemas else rt}")
        for table, column in ((lt, lc), (rt, rc)):
            col_names = {
                str(c.get("name"))
                for c in DataSourceService._columns_to_list(schemas[table].columns)
                if isinstance(c, dict) and c.get("name")
            }
            if column not in col_names:
                raise BusinessException(code=400, message=f"字段 {table}.{column} 不在Schema中")

        # 2-3. 执行探测
        sql = cls._build_probe_sql(ds, lt, lc, rt, rc)
        logger.info(f"执行表关系探测: ds_id={ds_id}, {lt}.{lc} = {rt}.{rc}")
        joined_rows, left_distinct, right_distinct = await cls._run_probe_sql(ds, sql)
        factor, verdict = cls._judge_cardinality(joined_rows, left_distinct, right_distinct)
        truncated = joined_rows >= PROBE_ROW_LIMIT

        probe_result = {
            "factor": factor,
            "verdict": verdict,
            "truncated": truncated,
            "probedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 4. 结论缓存到已存在 relation 行（旁路）
        try:
            rel = await cls._find_by_quad(db, ds_id, lt, lc, rt, rc)
            if rel:
                rel.probe = probe_result
                await db.commit()
        except Exception as e:
            await db.rollback()
            logger.warning(f"探测结论缓存失败(旁路忽略): ds_id={ds_id}, {type(e).__name__}: {e}")

        return {
            "leftTable": lt, "leftColumn": lc, "rightTable": rt, "rightColumn": rc,
            "joinedRows": joined_rows,
            "leftDistinct": left_distinct,
            "rightDistinct": right_distinct,
            "factor": factor,
            "verdict": verdict,
            "truncated": truncated,
        }

    # ---------- relation-graph 聚合 ----------

    @classmethod
    def _invalidate_graph_cache(cls, ds_id: int) -> None:
        """失效指定数据源的 graph 缓存（同步/关系变更时调用）"""
        cls._graph_cache.pop(ds_id, None)

    @classmethod
    async def get_relation_graph(cls, db: AsyncSession, ds_id: int) -> dict:
        """
        relation-graph 聚合接口（画布/总览一次取全量）

        nodes 来自 table_schemas 缓存（含字段列表 + 主键标记 + port_id），
        edges 来自 table_relations（关联探测结论缓存），stats 为状态统计。
        内存缓存：datasource_id 维度，同步/关系变更时失效（方案 4.4.6）。

        :return: {"nodes": [...], "edges": [...], "stats": {active, inactive, ignored}}
        """
        cached = cls._graph_cache.get(ds_id)
        if cached and (time.time() - cached[0]) < cls._graph_cache_ttl:
            return cached[1]

        await cls._get_datasource(db, ds_id)

        # 1. nodes（来自 table_schemas）
        schema_stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
        schemas = list((await db.execute(schema_stmt)).scalars().all())
        nodes = []
        for s in schemas:
            cols = DataSourceService._columns_to_list(s.columns)
            columns = [
                {
                    "name": str(c.get("name")),
                    "type": str(c.get("type") or ""),
                    "comment": str(c.get("remark") or c.get("comment") or ""),
                    "is_pk": bool(c.get("primaryKey")),
                    "port_id": f"col_{c.get('name')}",
                }
                for c in cols if isinstance(c, dict) and c.get("name")
            ]
            nodes.append({
                "id": s.table_name,
                "label": (s.table_comment or "").strip() or s.table_name,
                "columns": columns,
            })

        # 2. edges（来自 table_relations）
        rel_stmt = select(TableRelation).where(TableRelation.datasource_id == ds_id)
        relations = list((await db.execute(rel_stmt)).scalars().all())
        edges = [
            {
                "id": r.id,
                "source": r.left_table,
                "source_port": f"col_{r.left_column}",
                "target": r.right_table,
                "target_port": f"col_{r.right_column}",
                "source_type": r.source,
                "status": r.status,
                "cardinality": r.cardinality,
                "desc": r.relation_desc,
                "relation_group": r.relation_group,
                "probe": r.probe,
            }
            for r in relations
        ]

        # 3. stats
        stats = {"active": 0, "inactive": 0, "ignored": 0}
        for r in relations:
            if r.status in stats:
                stats[r.status] += 1

        graph = {"nodes": nodes, "edges": edges, "stats": stats}
        cls._graph_cache[ds_id] = (time.time(), graph)
        return graph

    @staticmethod
    def new_relation_group_id() -> str:
        """生成复合关联键分组ID（rg_ 前缀 + 短UUID）"""
        return f"rg_{uuid.uuid4().hex[:12]}"


# 服务实例
table_relation_service = TableRelationService()
