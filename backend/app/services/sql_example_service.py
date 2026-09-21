"""
示例SQL库服务（NL2SQL 升级二期：Few-shot 手工示例库，参考 SQLBot）

功能模块：
    1. CRUD / 状态管理     —— 列表/新增/编辑/启用停用/删除（保存前防污染校验）
    2. dry_run             —— 试跑：validate_and_execute 只读执行一次，预览行数与首行
    3. recall_examples     —— Few-shot 注入召回（Top 2~3、阈值≥0.75、手工优先、防跨域、防漂移）

设计要点（源自方案 6.1~6.4）：
    - 防污染校验：SQLSecurityFilter 只读白名单 + sqlglot 语法校验，拦截写操作误录入
    - 向量化：保存/编辑时向量化 question（旁路：失败仅告警，embedding=None 不影响保存）
    - 召回参数：Top 2~3、相似度 ≥0.75（宁缺毋滥）、同分时 manual 优先、success_count 加权
    - 防跨域误导：示例 SQL 涉及的表必须仍在当前筛选表集合内
    - 防漂移：示例 schema_version 低于当前 Schema 版本时跳过（结构变更防护）
"""
import asyncio
from typing import List, Optional, Tuple

import sqlglot
from loguru import logger
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import SchemaEmbedding
from app.models.sql_example import SqlExample
from app.middlewares.exception_handler import BusinessException
from app.services.nl2sql_service import SQLSecurityFilter, SQLValidator


# 召回参数（方案 6.4）
RECALL_TOP_K = 3
RECALL_SIMILARITY_THRESHOLD = 0.75


class SqlExampleService:
    """示例SQL库服务（Few-shot 注入）"""

    # ---------- 向量化 ----------

    @staticmethod
    def _get_embed_model():
        """获取共享嵌入模型实例（复用知识库的 bge-m3，懒加载缓存）"""
        from app.services.vector_service import VectorIndexService
        return VectorIndexService._get_embed_model()

    @classmethod
    async def _embed_question(cls, question: str) -> Optional[List[float]]:
        """
        问题向量化（同步嵌入调用包装为线程池执行）

        :return: 向量（1024维）；失败返回 None（旁路，调用方保存原文不阻断）
        """
        try:
            embed_model = cls._get_embed_model()
            vector = await asyncio.to_thread(
                embed_model.get_text_embedding_batch, [question]
            )
            return list(vector[0])
        except Exception as e:
            logger.warning(f"示例问题向量化失败(旁路,embedding置空): {type(e).__name__}: {e}")
            return None

    @staticmethod
    async def _current_schema_version(db: AsyncSession, ds_id: int) -> int:
        """获取数据源当前 Schema 版本号（SchemaEmbedding 重建时递增）"""
        stmt = select(SchemaEmbedding.schema_version).where(
            SchemaEmbedding.datasource_id == ds_id
        )
        versions = [v for v in (await db.execute(stmt)).scalars().all() if v]
        return max(versions) if versions else 1

    # ---------- 防污染校验 ----------

    @staticmethod
    def validate_sql_readonly(sql: str) -> None:
        """
        SQL 只读白名单 + 语法校验（手工示例同样把关，防污染）

        :param sql: 待校验 SQL
        :raises BusinessException: 含危险操作或语法非法时抛出 400
        """
        is_safe, error = SQLSecurityFilter.check(sql)
        if not is_safe:
            raise BusinessException(code=400, message=f"SQL 含禁止的操作: {error}")
        is_valid, error = SQLValidator.validate(sql, "mysql")
        if not is_valid:
            raise BusinessException(code=400, message=f"SQL 语法校验失败: {error}")

    @staticmethod
    def extract_sql_tables(sql: str) -> set:
        """提取 SQL 涉及的表名集合（FROM/JOIN，防跨域示例校验用）"""
        try:
            parsed = sqlglot.parse_one(sql, dialect="mysql")
            return {t.name for t in parsed.find_all(sqlglot.exp.Table)}
        except Exception:
            return set()

    # ---------- CRUD ----------

    @staticmethod
    async def list_examples(
        db: AsyncSession,
        ds_id: Optional[int] = None,
        status: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        分页查询示例SQL列表（ds_id 为空时查询全部数据源）

        :param db: 数据库会话
        :param ds_id: 数据源ID（可选，None 表示不过滤数据源）
        :param status: 状态过滤 active/retired
        :param keyword: 关键词（匹配标准问题/SQL/备注）
        :param page: 页码（1起）
        :param page_size: 每页条数
        :return: {"total": 总数, "list": [示例字典（含 datasourceName）]}
        """
        from app.models.datasource import DataSource

        conditions = []
        if ds_id is not None:
            conditions.append(SqlExample.datasource_id == ds_id)
        if status:
            conditions.append(SqlExample.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conditions.append(
                (SqlExample.question.like(kw))
                | (SqlExample.sql.like(kw))
                | (SqlExample.description.like(kw))
            )

        base_stmt = select(SqlExample)
        if conditions:
            base_stmt = base_stmt.where(*conditions)

        total = (
            await db.execute(
                select(func.count(SqlExample.id)).where(
                    *(conditions if conditions else [SqlExample.id.is_not(None)])
                )
            )
        ).scalar() or 0

        stmt = (
            base_stmt
            .order_by(SqlExample.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = list((await db.execute(stmt)).scalars().all())

        # 批量回填数据源名称（避免 N+1：一次查出涉及的全部数据源）
        ds_ids = list({r.datasource_id for r in rows})
        ds_name_map: dict = {}
        if ds_ids:
            ds_rows = (
                await db.execute(
                    select(DataSource.id, DataSource.name).where(
                        DataSource.id.in_(ds_ids)
                    )
                )
            ).all()
            ds_name_map = {d.id: d.name for d in ds_rows}

        result_list = []
        for r in rows:
            item = r.to_dict()
            item["datasourceName"] = ds_name_map.get(r.datasource_id, f"数据源{r.datasource_id}")
            result_list.append(item)
        return {"total": total, "list": result_list}

    @staticmethod
    async def get_example(db: AsyncSession, ds_id: int, example_id: int) -> SqlExample:
        """获取单条示例，不存在或归属不符抛 404"""
        example = await db.get(SqlExample, example_id)
        if not example or example.datasource_id != ds_id:
            raise BusinessException(code=404, message="示例SQL不存在")
        return example

    @classmethod
    async def create_example(cls, db: AsyncSession, ds_id: int, data: dict, user_id: Optional[int] = None) -> SqlExample:
        """
        新增手工示例（保存前防污染校验，保存时向量化——旁路不阻断）

        :param data: {question, sql, description?, status?}
        :param user_id: 创建人ID
        :raises BusinessException: SQL 校验失败 400 / 数据源不存在 404
        """
        from app.models.datasource import DataSource
        ds_row = await db.get(DataSource, ds_id)
        if not ds_row:
            raise BusinessException(code=404, message="数据源不存在")

        question = str(data.get("question") or "").strip()
        sql = str(data.get("sql") or "").strip()
        if not question:
            raise BusinessException(code=400, message="标准问题不能为空")
        if not sql:
            raise BusinessException(code=400, message="SQL 不能为空")
        cls.validate_sql_readonly(sql)

        status = data.get("status") or "active"
        if status not in ("active", "retired"):
            raise BusinessException(code=400, message=f"非法状态: {status}")

        # 向量化（旁路：失败置 None，不阻断保存）
        embedding = await cls._embed_question(question)
        schema_version = await cls._current_schema_version(db, ds_id)

        example = SqlExample(
            datasource_id=ds_id,
            question=question,
            sql=sql,
            description=data.get("description"),
            source="manual",
            embedding=embedding,
            schema_version=schema_version,
            status=status,
            created_by=user_id,
        )
        db.add(example)
        await db.commit()
        await db.refresh(example)
        logger.info(f"新增示例SQL: ds_id={ds_id}, id={example.id}, 向量化={'成功' if embedding else '失败(旁路)'}")
        return example

    @classmethod
    async def update_example(cls, db: AsyncSession, ds_id: int, example_id: int, data: dict) -> SqlExample:
        """
        编辑示例（标准问题变更时重新向量化；SQL 变更时重新校验；可切换数据源）

        :param data: {datasourceId?, question?, sql?, description?}
        """
        from app.models.datasource import DataSource

        example = await cls.get_example(db, ds_id, example_id)
        if example.source != "manual":
            raise BusinessException(code=400, message="仅手工录入示例支持编辑")

        # 数据源切换校验：目标数据源必须存在；切换后重取新数据源 Schema 版本（防漂移基准变更）
        ds_changed = False
        if data.get("datasourceId") is not None and data["datasourceId"] != example.datasource_id:
            new_ds_id = data["datasourceId"]
            new_ds_row = await db.get(DataSource, new_ds_id)
            if not new_ds_row:
                raise BusinessException(code=404, message="目标数据源不存在")
            example.datasource_id = new_ds_id
            ds_changed = True

        question_changed = False
        if data.get("question") is not None:
            new_question = str(data["question"]).strip()
            if not new_question:
                raise BusinessException(code=400, message="标准问题不能为空")
            question_changed = new_question != example.question
            example.question = new_question
        if data.get("sql") is not None:
            new_sql = str(data["sql"]).strip()
            if not new_sql:
                raise BusinessException(code=400, message="SQL 不能为空")
            cls.validate_sql_readonly(new_sql)
            example.sql = new_sql
        if data.get("description") is not None:
            example.description = data["description"]

        # 切换数据源后重取新数据源的 Schema 版本（示例召回防漂移基准跟随新归属）
        if ds_changed:
            example.schema_version = await cls._current_schema_version(db, example.datasource_id)

        if question_changed:
            embedding = await cls._embed_question(example.question)
            if embedding is not None:
                example.embedding = embedding

        await db.commit()
        await db.refresh(example)
        logger.info(
            f"编辑示例SQL: id={example_id}, 数据源切换={'是' if ds_changed else '否'}, 问题变更={question_changed}"
        )
        return example

    @staticmethod
    async def update_status(db: AsyncSession, ds_id: int, example_id: int, status: str) -> SqlExample:
        """启用/停用示例（active/retired）"""
        if status not in ("active", "retired"):
            raise BusinessException(code=400, message=f"非法状态: {status}")
        example = await SqlExampleService.get_example(db, ds_id, example_id)
        example.status = status
        await db.commit()
        await db.refresh(example)
        logger.info(f"示例SQL状态变更: ds_id={ds_id}, id={example_id}, status={status}")
        return example

    @staticmethod
    async def delete_example(db: AsyncSession, ds_id: int, example_id: int) -> None:
        """删除示例"""
        example = await SqlExampleService.get_example(db, ds_id, example_id)
        await db.delete(example)
        await db.commit()
        logger.info(f"删除示例SQL: ds_id={ds_id}, id={example_id}")

    # ---------- 试跑 ----------

    @staticmethod
    async def dry_run(db: AsyncSession, ds_id: int, example_id: int) -> dict:
        """
        试跑：走 validate_and_execute 只读执行一次，返回行数与首行预览

        :return: {"rows": 行数, "preview": 首行数据, "columns": 字段元信息}
        :raises BusinessException: SQL 校验/执行失败 500
        """
        from app.models.datasource import DataSource
        from app.services.nl2sql_service import nl2sql_engine

        example = await SqlExampleService.get_example(db, ds_id, example_id)
        datasource = await db.get(DataSource, ds_id)
        if not datasource:
            raise BusinessException(code=404, message="数据源不存在")

        # 预校验（提前拦截写操作，给出明确错误）
        SqlExampleService.validate_sql_readonly(example.sql)

        success, error, results, column_meta, _ = await nl2sql_engine.validate_and_execute(
            db, example.sql, datasource
        )
        if not success:
            raise BusinessException(code=500, message=f"试跑失败: {error}")

        return {
            "rows": len(results) if results else 0,
            "preview": results[0] if results else None,
            "columns": column_meta,
        }

    # ---------- Few-shot 注入召回 ----------

    @classmethod
    async def recall_examples(
        cls,
        db: AsyncSession,
        ds_id: int,
        question: str,
        table_names: Optional[List[str]] = None,
        top_k: int = RECALL_TOP_K,
        similarity_threshold: float = RECALL_SIMILARITY_THRESHOLD,
    ) -> List[Tuple[str, str, float]]:
        """
        Few-shot 示例召回（注入链路，手工/自动共用）

        旁路原则：空入参、无向量数据、pgvector 缺失、检索异常一律返回空列表（零回归）。

        过滤规则：
            - status=active 且 embedding 非空
            - schema_version 不低于当前版本（防漂移：结构变更后旧示例跳过）
            - 示例 SQL 涉及的表必须仍在当前筛选表集合内（防跨域误导）

        排序规则：相似度降序为主；相似度相同时 manual 优先、success_count 加权。

        :param db: 数据库会话
        :param ds_id: 数据源ID
        :param question: 用户问题
        :param table_names: 当前筛选的表集合（空则跳过跨域过滤）
        :param top_k: 注入数量上限
        :param similarity_threshold: 相似度下限
        :return: [(question, sql, similarity)]
        """
        if not question or not question.strip():
            return []
        if ds_id is None or ds_id <= 0:
            return []
        if SqlExample.embedding is None:
            return []

        try:
            query_vec = await cls._embed_question(question.strip())
            if query_vec is None:
                return []

            current_version = await cls._current_schema_version(db, ds_id)

            try:
                from pgvector.sqlalchemy import Vector  # noqa: F401 驱动可用性探测
                sim_expr = 1.0 - SqlExample.embedding.cosine_distance(query_vec)
                stmt = (
                    select(SqlExample, sim_expr.label("similarity"))
                    .where(
                        SqlExample.datasource_id == ds_id,
                        SqlExample.status == "active",
                        SqlExample.embedding.is_not(None),
                    )
                    .order_by(sim_expr.desc())
                    .limit(max(top_k * 4, 12))  # 多取候选，跨域/漂移过滤后仍够 Top-K
                )
                rows = (await db.execute(stmt)).all()
            except ImportError:
                logger.warning("[SqlExample] pgvector未安装，Few-shot召回降级返回空")
                return []

            table_set = set(table_names) if table_names else None
            candidates: List[Tuple[str, str, float, int, int]] = []
            for example, similarity in rows:
                sim = float(similarity)
                if sim < similarity_threshold:
                    continue
                # 防漂移：示例版本落后于当前 Schema 版本时跳过
                if (example.schema_version or 1) < current_version:
                    logger.debug(
                        f"[SqlExample] 示例版本漂移跳过: id={example.id}, "
                        f"example_v={example.schema_version}, current_v={current_version}"
                    )
                    continue
                # 防跨域：示例 SQL 涉及的表必须仍在当前筛选表集合内
                if table_set is not None:
                    sql_tables = cls.extract_sql_tables(example.sql)
                    if sql_tables and not sql_tables.issubset(table_set):
                        continue
                candidates.append((
                    example.question, example.sql, sim,
                    0 if example.source == "manual" else 1,
                    example.success_count or 0,
                ))

            # 相似度降序为主；相同相似度时 manual 优先、success_count 加权排序
            candidates.sort(key=lambda x: (-x[2], x[3], -x[4]))
            results = [(q, s, sim) for q, s, sim, _src, _cnt in candidates[:top_k]]
            if results:
                logger.info(
                    f"[SqlExample] Few-shot召回完成: ds={ds_id}, 命中{len(results)}条, "
                    f"top={results[0][2]:.3f}"
                )
            return results
        except Exception as e:
            logger.warning(f"[SqlExample] Few-shot召回失败(旁路回退): {type(e).__name__}: {e}")
            return []


# 服务实例
sql_example_service = SqlExampleService()
