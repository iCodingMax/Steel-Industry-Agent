"""
智能体记忆服务（M3 阶段核心：三层记忆之中期压缩 + 长期记忆）

功能模块：
    1. ContextCompressService —— 会话上下文滚动压缩
       会话历史超出滑动窗口（CHAT_HISTORY_LIMIT=10）时，被丢弃的早期
       历史由 LLM 摘要压缩后写入 sessions.summarized_context，随会话
       滚动更新，实现"无限轮次不爆上下文"。

    2. AgentMemoryService —— 长期记忆读写与治理
       - 写入：MasterAgent 每轮运行后由 LLM 抽取值得沉淀的记忆条目
         （用户偏好/设备档案/诊断结论），bge-m3 向量化入库
       - 召回：用户提问前按 application+user 向量检索（pgvector HNSW
         余弦相似度），命中条目注入系统提示词
       - 治理：expires_at 时效过滤（防记忆污染）、人工查询/删除

设计要点：
    1. 嵌入复用 VectorIndexService._get_embed_model()（bge-m3, 1024维）
    2. 嵌入调用为同步阻塞，统一 asyncio.to_thread 包装防止事件循环卡死
    3. 向量检索使用 pgvector 原生 SQL（AgentMemory 表与业务库同库，
       走 SQLAlchemy Core 直查，不依赖 LlamaIndex 索引抽象）
    4. 记忆召回/沉淀全部旁路化：任何失败仅告警不中断主问答链路
"""
import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy import delete as sql_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session
from app.services.llm_service import llm_service


# ===================== 自定义业务异常 =====================


class MemoryServiceError(Exception):
    """记忆服务统一业务异常基类"""
    pass


class MemoryWriteError(MemoryServiceError):
    """记忆写入/向量化失败异常"""
    pass


class MemoryRecallError(MemoryServiceError):
    """记忆召回失败异常"""
    pass


# ===================== 长期记忆数据结构 =====================


# 记忆类型常量（与 agent_memories.memory_type 字段对齐）
MEMORY_TYPE_PREFERENCE = "preference"                    # 用户偏好
MEMORY_TYPE_FACT = "fact"                                # 设备档案
MEMORY_TYPE_DIAGNOSIS = "diagnosis_conclusion"           # 诊断结论

VALID_MEMORY_TYPES = (MEMORY_TYPE_PREFERENCE, MEMORY_TYPE_FACT, MEMORY_TYPE_DIAGNOSIS)


class RecalledMemory:
    """
    召回的单条记忆（轻量载体，避免直接暴露 ORM 对象）
    """

    __slots__ = ("memory_id", "memory_type", "content", "similarity", "created_at")

    def __init__(self, memory_id: int, memory_type: str, content: str,
                 similarity: float, created_at: Optional[datetime] = None):
        self.memory_id = memory_id
        self.memory_type = memory_type
        self.content = content
        self.similarity = similarity
        self.created_at = created_at

    def __repr__(self) -> str:
        return (f"RecalledMemory(id={self.memory_id}, type={self.memory_type}, "
                f"sim={self.similarity:.3f})")


# ===================== 中期记忆：会话上下文压缩 =====================


class ContextCompressService:
    """
    会话上下文滚动压缩服务（中期记忆层）

    策略：
        - get_history 滑动窗口只保留最近 CHAT_HISTORY_LIMIT(10) 条
        - 本服务把"窗口外的全部历史 + 已有摘要"交给 LLM 滚动压缩，
          结果写入 sessions.summarized_context
        - MasterAgent 组装消息时：系统提示词注入摘要 + 窗口内历史，
          兼顾长程记忆与近期细节

    触发条件：
        窗口外历史条数 >= COMPRESS_MIN_DROPPED（避免频繁压缩浪费 LLM 调用）
    """

    # 窗口外最少历史条数（达到才触发压缩）
    COMPRESS_MIN_DROPPED = 4
    # 摘要最大字符数（超限截断，防止无限膨胀）
    MAX_SUMMARY_CHARS = 2000

    # 压缩提示词（输入完整对话 + 旧摘要，输出滚动更新后的新摘要）
    _COMPRESS_PROMPT = (
        "你是对话记录压缩助手。请将以下【旧摘要】与【待压缩对话】合并，"
        "生成一份滚动更新的对话摘要，用于后续对话的背景上下文。\n"
        "要求：\n"
        "1. 保留用户身份/偏好、设备名称/编号、关键数据结论、未完成事项\n"
        "2. 丢弃寒暄、重复内容、与任务无关的细节\n"
        "3. 用简洁的条目式中文输出，不超过500字\n"
        "4. 直接输出摘要内容，不要任何解释或前后缀\n\n"
        "【旧摘要】\n{old_summary}\n\n"
        "【待压缩对话】\n{dropped_text}\n\n"
        "【滚动更新后的摘要】"
    )

    @staticmethod
    def _format_history_text(history: List[Dict[str, str]]) -> str:
        """
        格式化历史列表为多行文本（角色: 内容）

        :param history: 对话历史 [{"role": "user/assistant", "content": "..."}]
        :return: 格式化文本
        """
        return "\n".join(
            f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')}"
            for m in history
        )

    @classmethod
    async def compress_if_needed(
        cls,
        db: AsyncSession,
        session_id: int,
        window_history: List[Dict[str, str]],
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        判断并执行会话上下文压缩（旁路：失败仅告警返回 None）

        :param db: 数据库异步会话
        :param session_id: 会话ID
        :param window_history: 滑动窗口内的历史（get_history 返回值，不参与压缩）
        :param llm_config: 应用级LLM配置（透传给压缩调用）
        :return: 压缩后的摘要文本；未触发压缩或压缩失败返回 None
        """
        try:
            if not session_id or session_id <= 0:
                return None

            # 1. 加载会话与全量历史（窗口外部分）
            session_obj = (await db.execute(
                select(Session).where(Session.id == session_id)
            )).scalar_one_or_none()
            if session_obj is None:
                logger.warning(f"[ContextCompress] 会话不存在: session_id={session_id}")
                return None

            from app.models.session import Message
            all_msgs_stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.id.asc())
            )
            all_msgs = list((await db.execute(all_msgs_stmt)).scalars().all())

            window_size = len(window_history)
            dropped_count = len(all_msgs) - window_size
            if dropped_count < cls.COMPRESS_MIN_DROPPED:
                return None  # 窗口外历史不足，无需压缩

            # 2. 取窗口外的早期历史（全量 - 窗口尾部）
            dropped_msgs = all_msgs[:-window_size] if window_size > 0 else all_msgs
            dropped_history = [
                {"role": m.role, "content": (m.content or "").strip()}
                for m in dropped_msgs
                if (m.content or "").strip()
            ]
            if not dropped_history:
                return None

            # 3. LLM 滚动压缩（旧摘要 + 窗口外历史 → 新摘要）
            old_summary = (session_obj.summarized_context or "").strip() or "（无）"
            prompt = cls._COMPRESS_PROMPT.format(
                old_summary=old_summary,
                dropped_text=cls._format_history_text(dropped_history),
            )
            new_summary = (await llm_service.chat(prompt, config=llm_config)).strip()
            if not new_summary:
                logger.warning(f"[ContextCompress] 压缩结果为空: session_id={session_id}")
                return None
            if len(new_summary) > cls.MAX_SUMMARY_CHARS:
                new_summary = new_summary[:cls.MAX_SUMMARY_CHARS]

            # 4. 写回会话（flush 不提交，事务由调用方统一控制）
            session_obj.summarized_context = new_summary
            await db.flush()

            logger.info(
                f"[ContextCompress] 压缩完成: session_id={session_id}, "
                f"窗口外{dropped_count}条 → 摘要{len(new_summary)}字符"
            )
            return new_summary
        except Exception as e:
            # 旁路原则：压缩失败不影响主问答，仅告警
            logger.warning(f"[ContextCompress] 压缩失败(旁路忽略): {type(e).__name__}: {e}")
            return None

    @staticmethod
    async def get_summarized_context(db: AsyncSession, session_id: int) -> str:
        """
        读取会话的滚动摘要（不存在返回空串）

        :param db: 数据库异步会话
        :param session_id: 会话ID
        :return: 摘要文本（无则为空字符串）
        """
        if not session_id or session_id <= 0:
            return ""
        session_obj = (await db.execute(
            select(Session).where(Session.id == session_id)
        )).scalar_one_or_none()
        return (session_obj.summarized_context or "") if session_obj else ""


# ===================== 长期记忆：写入/召回/治理 =====================


class AgentMemoryService:
    """
    智能体长期记忆服务（跨会话记忆沉淀与召回）

    职责：
        1. extract_and_save()  —— LLM 抽取本轮对话值得沉淀的记忆并入库
        2. recall()            —— 按应用+用户向量召回相关记忆
        3. 治理接口            —— 查询/删除/过期清理（供管理API调用）
    """

    # 单次召回最大条数（防止提示词被记忆占满）
    RECALL_TOP_K = 5
    # 召回相似度下限（余弦相似度 < 阈值的记忆不注入）
    RECALL_SIMILARITY_THRESHOLD = 0.35
    # 单条记忆内容最大长度
    MAX_CONTENT_CHARS = 500
    # 单次抽取的记忆条数上限（防LLM过度抽取）
    MAX_EXTRACT_ITEMS = 5

    # 记忆抽取提示词
    _EXTRACT_PROMPT = (
        "分析以下对话，抽取值得长期记住的信息（用户偏好、设备档案、"
        "诊断结论等）。\n"
        "判断标准：只抽取跨会话仍然有价值的信息，如：\n"
        "- 用户偏好（负责的产线/设备、常用汇总口径、汇报格式偏好）\n"
        "- 设备档案（设备编号、位置、已知的故障或参数特性）\n"
        "- 诊断结论（问题根因、已验证的处理方法、维修记录）\n"
        "不要抽取：临时性问题、寒暄、一次性查询结果、没有结论的讨论。\n\n"
        "输出严格的 JSON 数组（无值得记住的信息时输出 []），"
        "每项格式：\n"
        '{{"memory_type": "preference/fact/diagnosis_conclusion", "content": "记忆内容(50字内)"}}\n\n'
        "【对话内容】\n{dialog_text}\n\n"
        "【记忆抽取结果(JSON数组)】"
    )

    # ---------- 嵌入辅助 ----------

    @staticmethod
    def _get_embed_model():
        """
        获取共享嵌入模型实例（复用知识库的 bge-m3，懒加载缓存）

        :return: OpenAIEmbedding 实例
        :raises MemoryWriteError: 嵌入模型初始化失败时抛出
        """
        try:
            from app.services.vector_service import VectorIndexService
            return VectorIndexService._get_embed_model()
        except Exception as e:
            raise MemoryWriteError(f"嵌入模型初始化失败: {type(e).__name__}: {e}") from e

    @classmethod
    async def _embed_texts(cls, texts: List[str]) -> List[List[float]]:
        """
        批量文本向量化（同步嵌入调用包装为线程池执行）

        :param texts: 待向量化文本列表
        :return: 向量列表（与输入顺序一致，1024维）
        :raises MemoryWriteError: 向量化失败时抛出
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
        except MemoryWriteError:
            raise
        except Exception as e:
            raise MemoryWriteError(f"文本向量化失败: {type(e).__name__}: {e}") from e

    # ---------- 记忆召回 ----------

    @classmethod
    async def recall(
        cls,
        db: AsyncSession,
        application_id: int,
        query_text: str,
        user_id: Optional[int] = None,
        top_k: int = None,
        similarity_threshold: float = None,
    ) -> List[RecalledMemory]:
        """
        向量召回长期记忆（planner 前注入上下文的检索入口）

        检索规则：
            - 应用隔离：application_id 精确匹配
            - 用户隔离：user_id 匹配 或 公共记忆（user_id IS NULL）
            - 时效过滤：expires_at 为空或晚于当前时间
            - 相似度：余弦相似度降序取 top_k

        :param db: 数据库异步会话
        :param application_id: 应用ID（隔离键）
        :param query_text: 检索文本（通常为用户问题）
        :param user_id: 用户ID（None 表示仅召回应用级公共记忆）
        :param top_k: 返回条数上限（默认 RECALL_TOP_K）
        :param similarity_threshold: 相似度下限（默认 RECALL_SIMILARITY_THRESHOLD）
        :return: 命中记忆列表（按相似度降序）
        :raises MemoryRecallError: 向量化或检索失败时抛出
        """
        if not query_text or not query_text.strip():
            return []
        if application_id is None or application_id <= 0:
            return []

        top_k = top_k or cls.RECALL_TOP_K
        threshold = (cls.RECALL_SIMILARITY_THRESHOLD
                     if similarity_threshold is None else similarity_threshold)

        try:
            # 1. 问题向量化
            query_vec = (await cls._embed_texts([query_text.strip()]))[0]

            # 2. pgvector 余弦相似度检索（原生 SQL，含隔离/时效过滤）
            from app.models.agent_memory import AgentMemory
            try:
                from pgvector.sqlalchemy import Vector  # noqa: F401 驱动可用性探测
                # <=> 为余弦距离，相似度 = 1 - 距离
                sim_expr = 1.0 - AgentMemory.embedding.cosine_distance(query_vec)
                stmt = (
                    select(
                        AgentMemory.id,
                        AgentMemory.memory_type,
                        AgentMemory.content,
                        AgentMemory.created_at,
                        sim_expr.label("similarity"),
                    )
                    .where(
                        AgentMemory.application_id == application_id,
                        (AgentMemory.user_id == user_id)
                        | (AgentMemory.user_id.is_(None)),
                        AgentMemory.embedding.is_not(None),
                        (AgentMemory.expires_at.is_(None))
                        | (AgentMemory.expires_at > datetime.now()),
                    )
                    .order_by(sim_expr.desc())
                    .limit(top_k)
                )
                rows = (await db.execute(stmt)).all()
            except ImportError:
                # pgvector 驱动未安装：降级关键词匹配（LIKE）保证功能可用
                logger.warning("[AgentMemory] pgvector未安装，降级关键词召回")
                kw = f"%{query_text.strip()[:50]}%"
                stmt = (
                    select(
                        AgentMemory.id,
                        AgentMemory.memory_type,
                        AgentMemory.content,
                        AgentMemory.created_at,
                    )
                    .where(
                        AgentMemory.application_id == application_id,
                        (AgentMemory.user_id == user_id)
                        | (AgentMemory.user_id.is_(None)),
                        (AgentMemory.expires_at.is_(None))
                        | (AgentMemory.expires_at > datetime.now()),
                        AgentMemory.content.like(kw),
                    )
                    .order_by(AgentMemory.created_at.desc())
                    .limit(top_k)
                )
                rows = [
                    (r.id, r.memory_type, r.content, r.created_at, 0.5)
                    for r in (await db.execute(stmt)).all()
                ]

            # 3. 相似度阈值过滤 + 转换载体
            results = [
                RecalledMemory(r[0], r[1], r[2], float(r[4]), r[3])
                for r in rows
                if float(r[4]) >= threshold
            ]
            if results:
                logger.info(
                    f"[AgentMemory] 召回完成: app={application_id}, user={user_id}, "
                    f"命中{len(results)}条, top相似度={results[0].similarity:.3f}"
                )
            return results
        except MemoryWriteError as e:
            raise MemoryRecallError(f"召回失败(向量化异常): {e}") from e
        except Exception as e:
            raise MemoryRecallError(f"召回失败: {type(e).__name__}: {e}") from e

    # ---------- 记忆写入 ----------

    @classmethod
    async def save_memory(
        cls,
        db: AsyncSession,
        application_id: int,
        memory_type: str,
        content: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        expires_at: Optional[datetime] = None,
    ) -> int:
        """
        写入单条长期记忆（向量化后入库）

        :param db: 数据库异步会话
        :param application_id: 应用ID（隔离键）
        :param memory_type: 记忆类型（VALID_MEMORY_TYPES 之一）
        :param content: 记忆文本内容
        :param user_id: 用户ID（None 表示应用级公共记忆）
        :param session_id: 来源会话ID（溯源用）
        :param expires_at: 过期时间（None 表示永久有效）
        :return: 新记忆条目ID
        :raises MemoryWriteError: 参数非法、向量化或入库失败时抛出
        """
        # 1. 入参校验
        if application_id is None or application_id <= 0:
            raise MemoryWriteError("应用ID必须为正整数")
        if memory_type not in VALID_MEMORY_TYPES:
            raise MemoryWriteError(
                f"非法记忆类型 {memory_type!r}，可选: {VALID_MEMORY_TYPES}"
            )
        content = (content or "").strip()
        if not content:
            raise MemoryWriteError("记忆内容不能为空")
        if len(content) > cls.MAX_CONTENT_CHARS:
            content = content[:cls.MAX_CONTENT_CHARS]

        # 2. 内容去重（同应用+用户+类型+内容已存在则跳过，幂等写入）
        from app.models.agent_memory import AgentMemory
        dup_stmt = select(AgentMemory.id).where(
            AgentMemory.application_id == application_id,
            AgentMemory.user_id == user_id if user_id is not None
            else AgentMemory.user_id.is_(None),
            AgentMemory.memory_type == memory_type,
            AgentMemory.content == content,
        )
        dup_id = (await db.execute(dup_stmt)).scalar_one_or_none()
        if dup_id is not None:
            logger.info(f"[AgentMemory] 重复记忆跳过: 已存在id={dup_id}")
            return dup_id

        # 3. 向量化 + 入库
        try:
            vector = (await cls._embed_texts([content]))[0]
            memory_obj = AgentMemory(
                application_id=application_id,
                user_id=user_id,
                memory_type=memory_type,
                content=content,
                embedding=vector,
                session_id=session_id,
                expires_at=expires_at,
            )
            db.add(memory_obj)
            await db.flush()
            logger.info(
                f"[AgentMemory] 记忆写入: id={memory_obj.id}, app={application_id}, "
                f"user={user_id}, type={memory_type}, content={content[:30]}..."
            )
            return memory_obj.id
        except MemoryWriteError:
            raise
        except Exception as e:
            raise MemoryWriteError(f"记忆入库失败: {type(e).__name__}: {e}") from e

    @classmethod
    async def extract_and_save(
        cls,
        db: AsyncSession,
        application_id: int,
        question: str,
        answer: str,
        user_id: Optional[int] = None,
        session_id: Optional[int] = None,
        llm_config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        LLM 抽取本轮对话中值得沉淀的记忆并入库（MasterAgent 收尾调用）

        旁路原则：抽取/写入任一环节失败仅告警返回空列表，不影响主问答。

        :param db: 数据库异步会话
        :param application_id: 应用ID
        :param question: 本轮用户问题
        :param answer: 本轮智能体最终回答
        :param user_id: 用户ID（None 表示应用级公共记忆）
        :param session_id: 来源会话ID（溯源）
        :param llm_config: 应用级LLM配置（透传给抽取调用）
        :return: 实际写入的记忆列表 [{"memory_type": ..., "content": ...}]
        """
        try:
            if not question or not answer:
                return []

            # 1. LLM 抽取（严格 JSON 数组输出）
            dialog_text = (
                f"用户: {question[:1000]}\n助手: {answer[:2000]}"
            )
            prompt = cls._EXTRACT_PROMPT.format(dialog_text=dialog_text)
            raw = (await llm_service.chat(prompt, config=llm_config)).strip()

            # 2. 解析 JSON（容错：剥离markdown代码块包裹）
            if raw.startswith("```"):
                raw = raw.strip("`").lstrip("json").strip()
            items = json.loads(raw) if raw else []
            if not isinstance(items, list):
                logger.warning(f"[AgentMemory] 抽取结果非数组，忽略: {raw[:100]}")
                return []

            # 3. 逐条校验并入库（单条失败跳过不影响其余）
            saved = []
            for item in items[:cls.MAX_EXTRACT_ITEMS]:
                if not isinstance(item, dict):
                    continue
                m_type = str(item.get("memory_type") or "").strip()
                m_content = str(item.get("content") or "").strip()
                if m_type not in VALID_MEMORY_TYPES or not m_content:
                    continue
                try:
                    await cls.save_memory(
                        db=db,
                        application_id=application_id,
                        memory_type=m_type,
                        content=m_content,
                        user_id=user_id,
                        session_id=session_id,
                    )
                    saved.append({"memory_type": m_type, "content": m_content})
                except MemoryWriteError as e:
                    logger.warning(f"[AgentMemory] 单条记忆写入失败(跳过): {e}")
            if saved:
                logger.info(f"[AgentMemory] 本轮沉淀记忆{len(saved)}条: app={application_id}")
            return saved
        except json.JSONDecodeError as e:
            logger.warning(f"[AgentMemory] 抽取结果JSON解析失败(旁路忽略): {e}")
            return []
        except Exception as e:
            # 旁路原则：抽取失败不影响主问答
            logger.warning(f"[AgentMemory] 记忆抽取失败(旁路忽略): {type(e).__name__}: {e}")
            return []

    # ---------- 记忆治理（管理API调用） ----------

    @staticmethod
    async def list_memories(
        db: AsyncSession,
        application_id: int,
        user_id: Optional[int] = None,
        memory_type: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        查询记忆列表（管理端分页查询）

        :param db: 数据库异步会话
        :param application_id: 应用ID
        :param user_id: 用户ID筛选（None 查全部用户+公共记忆）
        :param memory_type: 记忆类型筛选
        :param include_expired: 是否包含已过期记忆（默认过滤）
        :param limit: 分页大小（1~500）
        :param offset: 分页偏移
        :return: 记忆字典列表（AgentMemory.to_dict 格式）
        """
        from app.models.agent_memory import AgentMemory

        limit = max(1, min(500, limit))
        conditions = [AgentMemory.application_id == application_id]
        if user_id is not None:
            conditions.append(AgentMemory.user_id == user_id)
        if memory_type:
            conditions.append(AgentMemory.memory_type == memory_type)
        if not include_expired:
            conditions.append(
                (AgentMemory.expires_at.is_(None))
                | (AgentMemory.expires_at > datetime.now())
            )

        stmt = (
            select(AgentMemory)
            .where(*conditions)
            .order_by(AgentMemory.id.desc())
            .limit(limit)
            .offset(max(0, offset))
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [r.to_dict() for r in rows]

    @staticmethod
    async def delete_memory(db: AsyncSession, memory_id: int) -> bool:
        """
        删除单条记忆（人工治理入口）

        :param db: 数据库异步会话
        :param memory_id: 记忆ID
        :return: 是否实际删除（不存在返回 False）
        """
        from app.models.agent_memory import AgentMemory

        result = await db.execute(
            sql_delete(AgentMemory).where(AgentMemory.id == memory_id)
        )
        deleted = (result.rowcount or 0) > 0
        if deleted:
            logger.info(f"[AgentMemory] 记忆删除: id={memory_id}")
        return deleted

    @staticmethod
    async def purge_expired(db: AsyncSession) -> int:
        """
        清理全部已过期记忆（TTL 定时任务/手动触发入口）

        :param db: 数据库异步会话
        :return: 实际删除条数
        """
        from app.models.agent_memory import AgentMemory

        result = await db.execute(
            sql_delete(AgentMemory).where(
                AgentMemory.expires_at.is_not(None),
                AgentMemory.expires_at <= datetime.now(),
            )
        )
        deleted = (result.rowcount or 0)
        if deleted:
            logger.info(f"[AgentMemory] 过期记忆清理: 删除{deleted}条")
        return deleted


# ===================== 服务实例（供其他模块调用） =====================

context_compress_service = ContextCompressService()
agent_memory_service = AgentMemoryService()
