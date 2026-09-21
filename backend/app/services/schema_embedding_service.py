"""
Schema 向量化索引服务（NL2SQL 升级一期：Schema Linking 向量召回）

功能模块：
    1. _build_embed_text  —— TableSchema 转自然语言描述（信息密度决定召回质量）
    2. rebuild_datasource —— 数据源"同步表结构"后全量重建该数据源的向量索引
    3. recall             —— 用户问题向量化后按余弦相似度召回 Top-K 候选表

设计要点（参照 agent_memory_service 成熟模式）：
    1. 嵌入复用 VectorIndexService._get_embed_model()（bge-m3, 1024维）
    2. 嵌入调用为同步阻塞，统一 asyncio.to_thread 包装防止事件循环卡死
    3. 向量检索使用 pgvector 原生查询（schema_embeddings 与系统库同库）
    4. 以 table_name 字符串关联（sync_schema 先删后插导致 TableSchema.id 不稳定）
    5. recall 全旁路化：任何失败仅告警并返回空列表，调用方回退原有关键词逻辑（零回归）
"""
import asyncio
import json
from typing import Any, List, Optional, Tuple

from loguru import logger
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import SchemaEmbedding, TableSchema
from app.models.term import Term


# ===================== 自定义业务异常 =====================


class SchemaEmbeddingError(Exception):
    """Schema 向量化服务统一业务异常基类"""
    pass


class SchemaEmbeddingBuildError(SchemaEmbeddingError):
    """向量索引构建失败异常（嵌入模型缺失/向量化失败/入库失败）"""
    pass


# ===================== 服务实现 =====================


class SchemaEmbeddingService:
    """
    表结构向量化索引服务

    职责：
        1. rebuild_datasource()  —— 数据源表结构同步后重建向量索引
        2. recall()              —— 用户问题向量召回候选表（generate_sql 接入）
    """

    # 召回候选表数量上限（交由 SchemaLinkingEngine LLM 精选 ≤3 张）
    RECALL_TOP_K = 8
    # 召回相似度下限（余弦相似度，宽松阈值——召回结果仍会经 LLM 精选）
    RECALL_SIMILARITY_THRESHOLD = 0.30
    # 单表参与向量化的最大列数（异常大表截断，防 embed_text 爆炸）
    MAX_COLUMNS_PER_TABLE = 100
    # embed_text 最大字符数
    MAX_EMBED_TEXT_CHARS = 8000
    # 注入 embed_text 的术语别名数量上限
    MAX_TERM_ALIASES = 20

    # ---------- 嵌入辅助 ----------

    @staticmethod
    def _get_embed_model():
        """
        获取共享嵌入模型实例（复用知识库的 bge-m3，懒加载缓存）

        :return: OpenAIEmbedding 实例
        :raises SchemaEmbeddingBuildError: 嵌入模型初始化失败时抛出
        """
        try:
            from app.services.vector_service import VectorIndexService
            return VectorIndexService._get_embed_model()
        except Exception as e:
            raise SchemaEmbeddingBuildError(
                f"嵌入模型初始化失败: {type(e).__name__}: {e}"
            ) from e

    @classmethod
    async def _embed_texts(cls, texts: List[str]) -> List[List[float]]:
        """
        批量文本向量化（同步嵌入调用包装为线程池执行）

        :param texts: 待向量化文本列表
        :return: 向量列表（与输入顺序一致，1024维）
        :raises SchemaEmbeddingBuildError: 向量化失败时抛出
        """
        if not texts:
            return []
        try:
            embed_model = cls._get_embed_model()
            # LlamaIndex get_text_embedding_batch 为同步阻塞调用
            vectors = await asyncio.to_thread(
                embed_model.get_text_embedding_batch, texts
            )
            return [list(v) for v in vectors]
        except SchemaEmbeddingBuildError:
            raise
        except Exception as e:
            raise SchemaEmbeddingBuildError(
                f"文本向量化失败: {type(e).__name__}: {e}"
            ) from e

    # ---------- embed_text 构造 ----------

    @staticmethod
    def _extract_term_aliases(terms: Optional[List[Term]]) -> List[str]:
        """
        从术语列表提取别名集合（term 本名 + synonyms JSON 数组展开）

        :param terms: 术语列表（Term ORM 对象）
        :return: 去重后的别名列表（term 本名在前）
        """
        aliases: List[str] = []
        seen = set()
        for t in terms or []:
            name = (t.term or "").strip()
            if name and name not in seen:
                aliases.append(name)
                seen.add(name)
            try:
                synonyms = json.loads(t.synonyms) if t.synonyms else []
            except (json.JSONDecodeError, TypeError):
                synonyms = []
            for syn in synonyms if isinstance(synonyms, list) else []:
                syn_str = str(syn).strip()
                if syn_str and syn_str not in seen:
                    aliases.append(syn_str)
                    seen.add(syn_str)
        return aliases

    @classmethod
    def _build_embed_text(cls, schema: TableSchema, term_aliases: List[str]) -> str:
        """
        表结构转自然语言描述用于向量化

        信息密度设计：表注释（业务语义主锚点）+ 列名 + 字段备注
        （remark 优先、comment 兜底）+ 术语别名（语义桥接，如"铁水"→炉况）。

        示例输出：
            高炉炉况打分结果表(hgbf1_condition_result)。字段：炉次号HEAT_NO、
            生产日期PRODUCE_DATE、炉况评分SCORE。业务别名：炉况、打分、高炉状态。

        :param schema: 表结构 ORM 对象（columns 为 JSONB list 或 JSON 字符串）
        :param term_aliases: 术语别名列表
        :return: 向量化原文
        """
        # 1. 解析 columns（兼容 JSONB list 与历史 JSON 字符串）
        columns_data = schema.columns
        if isinstance(columns_data, str):
            try:
                columns_data = json.loads(columns_data)
            except (json.JSONDecodeError, TypeError):
                columns_data = []
        if not isinstance(columns_data, list):
            columns_data = []

        # 2. 表头：表注释(表名)。—— 表注释为语义主锚点
        table_comment = (schema.table_comment or "").strip()
        header = (
            f"{table_comment}({schema.table_name})。"
            if table_comment
            else f"{schema.table_name}。"
        )

        # 3. 字段段：字段备注名（remark 优先、comment 兜底，为空时仅列名）
        col_parts = []
        for col in columns_data[: cls.MAX_COLUMNS_PER_TABLE]:
            if not isinstance(col, dict):
                continue
            name = str(col.get("name") or "").strip()
            if not name:
                continue
            remark = str(col.get("remark") or col.get("comment") or "").strip()
            col_parts.append(f"{remark}{name}" if remark else name)
        body = f"字段：{'、'.join(col_parts)}。" if col_parts else ""

        # 4. 别名段：术语别名注入（语义桥接）
        aliases = term_aliases[: cls.MAX_TERM_ALIASES]
        alias_seg = f"业务别名：{'、'.join(aliases)}。" if aliases else ""

        text = header + body + alias_seg
        return text[: cls.MAX_EMBED_TEXT_CHARS]

    # ---------- 重建 ----------

    @classmethod
    async def rebuild_datasource(
        cls,
        db: AsyncSession,
        ds_id: int,
        terms: Optional[List[Term]] = None,
    ) -> int:
        """
        重建指定数据源的 Schema 向量索引（先删后插，幂等）

        调用时机：数据源"同步表结构"完成后（sync_schema 钩子）、字段备注编辑后（单表重建）。
        事务边界：仅 flush 不 commit，由调用方统一提交（与 sync_schema 事务策略一致）。

        :param db: 数据库异步会话
        :param ds_id: 数据源ID
        :param terms: 术语列表（别名注入 embed_text 提升语义桥接召回）
        :return: 实际写入的向量记录数
        :raises SchemaEmbeddingBuildError: 查询/向量化/入库失败时抛出（调用方旁路处理）
        """
        try:
            # 1. 读取该数据源全部表结构
            stmt = select(TableSchema).where(TableSchema.datasource_id == ds_id)
            schemas = list((await db.execute(stmt)).scalars().all())
            if not schemas:
                logger.info(f"[SchemaEmbedding] 数据源无表结构，跳过重建: ds_id={ds_id}")
                return 0

            # 2. 构造 embed_text（术语别名注入）
            term_aliases = cls._extract_term_aliases(terms)
            embed_texts = [cls._build_embed_text(s, term_aliases) for s in schemas]

            # 3. 批量向量化
            vectors = await cls._embed_texts(embed_texts)

            # 4. 版本号递增（旧向量随重建删除，版本号用于二期示例漂移判断）
            ver_stmt = select(SchemaEmbedding.schema_version).where(
                SchemaEmbedding.datasource_id == ds_id
            )
            versions = [v for v in (await db.execute(ver_stmt)).scalars().all() if v]
            next_version = (max(versions) + 1) if versions else 1

            # 5. 先删后插（以 table_name 关联，非外键）
            await db.execute(
                sql_delete(SchemaEmbedding).where(SchemaEmbedding.datasource_id == ds_id)
            )
            for schema, text, vec in zip(schemas, embed_texts, vectors):
                db.add(
                    SchemaEmbedding(
                        datasource_id=ds_id,
                        table_name=schema.table_name,
                        embed_text=text,
                        embedding=vec,
                        schema_version=next_version,
                    )
                )
            await db.flush()

            logger.info(
                f"[SchemaEmbedding] 索引重建完成: ds_id={ds_id}, "
                f"表数={len(schemas)}, 版本={next_version}"
            )
            return len(schemas)
        except SchemaEmbeddingBuildError:
            raise
        except Exception as e:
            raise SchemaEmbeddingBuildError(
                f"向量索引重建失败: ds_id={ds_id}, {type(e).__name__}: {e}"
            ) from e

    @classmethod
    async def rebuild_table(
        cls,
        db: AsyncSession,
        ds_id: int,
        table_name: str,
        terms: Optional[List[Term]] = None,
    ) -> bool:
        """
        重建单张表的向量索引（字段备注编辑后调用，轻量增量）

        :param db: 数据库异步会话
        :param ds_id: 数据源ID
        :param table_name: 表名
        :param terms: 术语列表
        :return: 是否重建成功（表不存在返回 False）
        :raises SchemaEmbeddingBuildError: 查询/向量化/入库失败时抛出（调用方旁路处理）
        """
        try:
            stmt = select(TableSchema).where(
                TableSchema.datasource_id == ds_id,
                TableSchema.table_name == table_name,
            )
            schema = (await db.execute(stmt)).scalar_one_or_none()
            if schema is None:
                logger.warning(
                    f"[SchemaEmbedding] 单表重建跳过(表不存在): ds_id={ds_id}, table={table_name}"
                )
                return False

            text = cls._build_embed_text(schema, cls._extract_term_aliases(terms))
            vector = (await cls._embed_texts([text]))[0]

            # 版本号沿用该数据源当前最大版本
            ver_stmt = select(SchemaEmbedding.schema_version).where(
                SchemaEmbedding.datasource_id == ds_id
            )
            versions = [v for v in (await db.execute(ver_stmt)).scalars().all() if v]
            current_version = max(versions) if versions else 1

            await db.execute(
                sql_delete(SchemaEmbedding).where(
                    SchemaEmbedding.datasource_id == ds_id,
                    SchemaEmbedding.table_name == table_name,
                )
            )
            db.add(
                SchemaEmbedding(
                    datasource_id=ds_id,
                    table_name=table_name,
                    embed_text=text,
                    embedding=vector,
                    schema_version=current_version,
                )
            )
            await db.flush()
            logger.info(f"[SchemaEmbedding] 单表重建完成: ds_id={ds_id}, table={table_name}")
            return True
        except SchemaEmbeddingBuildError:
            raise
        except Exception as e:
            raise SchemaEmbeddingBuildError(
                f"单表向量重建失败: ds_id={ds_id}, table={table_name}, "
                f"{type(e).__name__}: {e}"
            ) from e

    # ---------- 召回 ----------

    @classmethod
    async def recall(
        cls,
        db: AsyncSession,
        question: str,
        datasource_id: int,
        top_k: int = RECALL_TOP_K,
        similarity_threshold: float = RECALL_SIMILARITY_THRESHOLD,
    ) -> List[Tuple[str, float]]:
        """
        用户问题向量召回候选表（generate_sql 关键词通道未命中时的兜底补全）

        旁路原则：空入参、无索引数据、pgvector 驱动缺失、检索异常一律返回空列表，
        调用方回退原有逻辑（全量表或关键词筛选结果），保证零回归风险。

        :param db: 数据库异步会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :param top_k: 返回候选表数量上限
        :param similarity_threshold: 余弦相似度下限
        :return: [(table_name, similarity)] 按相似度降序；失败/无数据返回 []
        """
        # 1. 入参前置校验（旁路：直接回退）
        if not question or not question.strip():
            return []
        if datasource_id is None or datasource_id <= 0:
            return []
        if SchemaEmbedding.embedding is None:
            return []

        try:
            # 2. 问题向量化
            query_vec = (await cls._embed_texts([question.strip()]))[0]

            # 3. pgvector 余弦相似度检索（<=> 余弦距离，相似度 = 1 - 距离）
            try:
                from pgvector.sqlalchemy import Vector  # noqa: F401 驱动可用性探测
                sim_expr = 1.0 - SchemaEmbedding.embedding.cosine_distance(query_vec)
                stmt = (
                    select(
                        SchemaEmbedding.table_name,
                        sim_expr.label("similarity"),
                    )
                    .where(
                        SchemaEmbedding.datasource_id == datasource_id,
                        SchemaEmbedding.embedding.is_not(None),
                    )
                    .order_by(sim_expr.desc())
                    .limit(max(1, top_k))
                )
                rows = (await db.execute(stmt)).all()
            except ImportError:
                # pgvector 驱动未安装：按方案降级到原有逻辑（返回空，调用方回退）
                logger.warning("[SchemaEmbedding] pgvector未安装，召回降级返回空")
                return []

            # 4. 阈值过滤
            results = [
                (r[0], float(r[1]))
                for r in rows
                if float(r[1]) >= similarity_threshold
            ]
            if results:
                logger.info(
                    f"[SchemaEmbedding] 召回完成: ds={datasource_id}, "
                    f"命中{len(results)}表, top={results[0][1]:.3f}, "
                    f"tables={[r[0] for r in results]}"
                )
            return results
        except SchemaEmbeddingBuildError as e:
            # 嵌入模型缺失/向量化失败：旁路回退原逻辑
            logger.warning(f"[SchemaEmbedding] 召回失败(向量化,旁路回退): {e}")
            return []
        except Exception as e:
            logger.warning(f"[SchemaEmbedding] 召回失败(旁路回退): {type(e).__name__}: {e}")
            return []


# ===================== 服务实例（供其他模块调用） =====================

schema_embedding_service = SchemaEmbeddingService()
