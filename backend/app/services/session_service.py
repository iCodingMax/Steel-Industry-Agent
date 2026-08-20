"""
会话管理服务模块（Session Service Layer）
管理对话会话、消息和溯源记录的完整生命周期

=============================================================================
架构定位（面试重点）：
  本模块属于「业务服务层」，负责对话数据的 CRUD 操作。
  分为三个服务类，各司其职：
    - SessionService  —— 会话管理（创建/查询/更新/删除会话）
    - MessageService  —— 消息管理（创建消息/获取历史/持久化AI回复）
    - TraceService    —— 溯源管理（记录知识引用和SQL来源，支撑可解释AI）

  数据模型关系（一对多级联）：
    Session（会话） 1 ──── N Message（消息） 1 ──── N Trace（溯源）
    │                        │                        │
    │  user_id（所属用户）    │  role（user/assistant） │  trace_type
    │  title（会话标题）      │  content（消息内容）    │  source_name
    │  chat_user_id（嵌入隔离）│  intent（意图分类）    │  score（匹配分数）
    │                        │  references（知识引用） │
    │                        │  data_result（查询结果）│
    │                        │  thinking_steps（思考） │

  设计模式：静态方法 + 依赖注入
    所有方法都是 @staticmethod，通过 db: AsyncSession 参数注入数据库会话。
    好处：无状态、线程安全、易于单元测试（可传入 mock session）。
=============================================================================

面试考点：
  Q: 为什么用静态方法而不是实例方法？
  A: 服务类本身不需要维护状态（所有状态在数据库中），静态方法更轻量、更易测试。
     底部创建的 session_service 等实例只是为了让路由层通过依赖注入引用更自然。
  Q: 为什么 get_by_user 要用子查询排序？
  A: 因为会话列表要按「最新消息时间」排序（最近活跃的会话排前面），
     但有些会话可能还没有消息，需要用 updated_at 兜底。这需要 LEFT JOIN 子查询。
"""
from typing import List, Optional
from loguru import logger

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, Message, Trace
from app.middlewares.exception_handler import BusinessException


class SessionService:
    """
    会话服务类
    负责对话会话的生命周期管理
    支持用户创建新会话、查询会话列表、更新会话标题、删除会话等操作
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        title: Optional[str] = None,
        chat_user_id: Optional[int] = None,
    ) -> Session:
        """
        创建新会话

        :param db: 数据库会话
        :param user_id: 系统用户ID（满足外键约束）
        :param title: 会话标题（可选，默认为"新对话"）
        :param chat_user_id: 对话用户ID（可选，嵌入模式用于数据隔离）
        :return: 创建的会话对象
        """
        logger.debug(f"创建会话: user_id={user_id}, chat_user_id={chat_user_id}, title={title}")
        session = Session(
            user_id=user_id,
            chat_user_id=chat_user_id,
            title=title or "新对话",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info(f"创建会话成功: ID={session.id}, 系统用户={user_id}, 对话用户={chat_user_id}")
        return session

    @staticmethod
    async def get_by_id(db: AsyncSession, session_id: int) -> Optional[Session]:
        """
        根据ID获取会话

        :param db: 数据库会话
        :param session_id: 会话ID
        :return: 会话对象（不存在返回None）
        """
        stmt = select(Session).where(Session.id == session_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_user(
        db: AsyncSession,
        user_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Session]:
        """
        获取用户的会话列表（按最新消息时间降序排列）

        排序策略（面试考点 —— 复杂排序逻辑）：
          用户希望最近活跃的会话排在前面。但「活跃」的定义是：
            - 有消息的会话：按最新消息的 created_at 排序
            - 无消息的会话：按会话的 updated_at 排序（兜底）

          实现方式：
            1. 子查询：对 Message 表按 session_id 分组，取每个会话的最新消息时间
            2. LEFT JOIN：将 Session 表与子查询左连接（无消息的会话也保留）
            3. COALESCE：latest_msg_time 为 NULL 时用 updated_at 兜底
            4. ORDER BY ... DESC：按兜底后的时间降序排列

        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数，默认50）
        :return: 会话列表（最近活跃的会话排在最前面）
        """
        # 子查询：对 Message 表按 session_id 分组，获取每个会话的最新消息创建时间
        latest_msg_subq = (
            select(
                Message.session_id.label("sid"),
                func.max(Message.created_at).label("latest_msg_time"),
            )
            .group_by(Message.session_id)
            .subquery()
        )
        # LEFT JOIN + COALESCE 排序：
        # - 有消息的会话用 latest_msg_time 排序
        # - 无消息的会话 latest_msg_time 为 NULL，COALESCE 用 updated_at 兜底
        stmt = (
            select(Session)
            .outerjoin(latest_msg_subq, Session.id == latest_msg_subq.c.sid)
            .where(Session.user_id == user_id)
            .order_by(
                func.coalesce(latest_msg_subq.c.latest_msg_time, Session.updated_at).desc()
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        sessions = list(result.scalars().all())
        logger.debug(f"获取用户会话列表: user_id={user_id}, 数量={len(sessions)}")
        return sessions

    @staticmethod
    async def update_title(
        db: AsyncSession,
        session_id: int,
        title: str,
    ) -> Optional[Session]:
        """
        更新会话标题

        :param db: 数据库会话
        :param session_id: 会话ID
        :param title: 新标题
        :return: 更新后的会话对象
        :raises BusinessException: 会话不存在时抛出
        """
        session = await SessionService.get_by_id(db, session_id)
        if not session:
            raise BusinessException(code=404, message="会话不存在")

        session.title = title
        await db.commit()
        await db.refresh(session)
        logger.info(f"更新会话标题成功: ID={session_id}, 标题={title}")
        return session

    @staticmethod
    async def delete(db: AsyncSession, session_id: int) -> None:
        """
        删除会话（级联删除关联的消息和溯源记录）

        级联删除策略（面试考点 —— 数据一致性）：
          因为 Message 和 Trace 表通过 session_id 外键关联到 Session 表，
          删除会话时必须先删除子表数据（Message 和 Trace），再删除主表（Session）。
          否则会触发 PostgreSQL 的外键约束错误。

          删除顺序：
            1. DELETE FROM messages WHERE session_id = ?  （删除所有消息）
            2. DELETE FROM traces WHERE session_id = ?     （删除所有溯源）
            3. DELETE FROM sessions WHERE id = ?           （最后删会话本身）
          三个操作在同一个事务中，保证原子性（要么全删，要么全不删）。

        :param db: 数据库会话
        :param session_id: 会话ID
        :raises BusinessException: 会话不存在时抛出（404）
        """
        session = await SessionService.get_by_id(db, session_id)
        if not session:
            raise BusinessException(code=404, message="会话不存在")

        # 级联删除：先删子表（Message、Trace），再删主表（Session）
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Trace).where(Trace.session_id == session_id))
        await db.delete(session)
        await db.commit()  # 统一提交，保证原子性
        logger.info(f"删除会话成功: ID={session_id}")


class MessageService:
    """
    消息服务类
    负责对话消息的管理，包括消息创建、查询和历史获取
    消息是对话的基本单元，记录用户输入和助手回复
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        session_id: int,
        role: str,
        content: str,
        intent: Optional[str] = None,
        references: Optional[List[dict]] = None,
        sql_traces: Optional[List[dict]] = None,
        data_result: Optional[List[dict]] = None,
        column_meta: Optional[List[dict]] = None,
        chart_type: Optional[str] = None,
        thinking_steps: Optional[List[dict]] = None,
        tool_calls: Optional[List[dict]] = None,
        tool_results: Optional[List[dict]] = None,
        query_time: Optional[int] = None,
    ) -> Message:
        """
        创建消息

        :param db: 数据库会话
        :param session_id: 会话ID
        :param role: 角色（user/assistant）
        :param content: 消息内容
        :param intent: 意图分类（knowledge/data/mcp/skill/hybrid/chat）
        :param references: 知识引用列表（RAG检索结果）
        :param sql_traces: SQL查询追踪列表（NL2SQL生成的SQL）
        :param data_result: 数据查询结果（JSON格式）
        :param column_meta: 字段元数据（字段名、注释等）
        :param chart_type: 推荐图表类型（line/bar/pie/table）
        :param thinking_steps: 思考过程步骤列表
        :param tool_calls: 工具调用信息列表
        :param tool_results: 工具调用结果列表
        :param query_time: 查询耗时（毫秒）
        :return: 创建的消息对象
        """
        logger.debug(f"创建消息: session_id={session_id}, role={role}, intent={intent}")
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            intent=intent,
            references=references,
            sql_traces=sql_traces,
            data_result=data_result,
            column_meta=column_meta,
            chart_type=chart_type,
            thinking_steps=thinking_steps,
            tool_calls=tool_calls,
            tool_results=tool_results,
            query_time=query_time,
        )
        db.add(message)
        # 同步更新会话的 updated_at 时间戳
        # 原因：get_by_user 方法用 COALESCE(latest_msg_time, updated_at) 排序，
        # 对于没有消息的新会话，updated_at 是唯一的排序依据。
        # 每次新增消息时更新 updated_at，确保会话列表排序正确。
        from sqlalchemy import update as sql_update
        await db.execute(
            sql_update(Session).where(Session.id == session_id).values(updated_at=func.now())
        )
        await db.commit()  # 统一提交（消息创建 + 会话时间戳更新），保证原子性
        await db.refresh(message)
        logger.info(f"创建消息成功: 会话={session_id}, 角色={role}, ID={message.id}")
        return message

    @staticmethod
    async def get_by_session(
        db: AsyncSession,
        session_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """
        获取会话的消息列表

        :param db: 数据库会话
        :param session_id: 会话ID
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数，默认100）
        :return: 消息列表（按创建时间升序排列）
        """
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at).offset(skip).limit(limit)
        result = await db.execute(stmt)
        messages = list(result.scalars().all())
        logger.debug(f"获取会话消息列表: session_id={session_id}, 数量={len(messages)}")
        return messages

    @staticmethod
    async def get_history(
        db: AsyncSession,
        session_id: int,
        window_size: int = None,
    ) -> List[dict]:
        """
        获取对话历史（用于LLM多轮对话上下文窗口管理）

        对话历史窗口策略（面试考点 —— 多轮对话上下文管理）：
          LLM 有上下文窗口限制（如 qwen3-32b 的上下文长度约 32K tokens），
          不能把所有历史消息都塞进去。需要用「滑动窗口」截取最近 N 条消息。

          window_size 来源（优先级从高到低）：
            1. 调用方显式传入的 window_size 参数
            2. 环境变量 CHAT_HISTORY_LIMIT（默认 10 条）
          建议值：6-10 条（太少丢失上下文，太多占用 token 预算）

        截断策略：
          - 单条消息超过 800 字符时截断（避免一条超长消息吃掉所有 token 预算）
          - 空内容消息跳过（如流式输出失败的空消息）
          - 按 id 倒序取最近 N 条，再 reversed 正序返回（保证时间顺序正确）

        :param db: 数据库会话
        :param session_id: 会话ID
        :param window_size: 返回最近的消息条数，None时从配置读取 CHAT_HISTORY_LIMIT
        :return: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        """
        from app.core.config import settings

        # window_size 优先级：参数传入 > 环境变量配置
        if window_size is None:
            window_size = settings.CHAT_HISTORY_LIMIT  # 默认 10 条

        if not session_id or session_id <= 0:
            return []

        # 按 id 倒序取最近 window_size 条消息（id 是自增的，倒序 = 最新）
        from sqlalchemy import desc as sql_desc
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(sql_desc(Message.id))
            .limit(window_size)
        )
        result = await db.execute(stmt)
        # reversed 把倒序结果转回正序（时间从早到晚），保证对话逻辑正确
        recent_msgs = list(reversed(list(result.scalars().all())))

        history: List[dict] = []
        for msg in recent_msgs:
            content = (msg.content or "").strip()
            if not content:
                continue  # 跳过空消息（如流式输出中断的空回复）
            # 区分角色截断策略（P1改造修复：Skill引导词被截断问题）
            # - user 消息：截断到 1500 字符（用户输入通常较短，JSON数据也够用）
            # - assistant 消息：不截断（Skill引导词如"请发送数据"通常在末尾，截断会丢失关键特征词）
            #   token 预算由 _build_messages 的 max_history_chars=30000 兜底，从最旧开始丢弃
            if msg.role == "assistant":
                # assistant 消息不截断，保留完整的 Skill 引导词和诊断结果
                pass
            elif len(content) > 1500:
                content = content[:1500] + "..."
            history.append({"role": msg.role, "content": content})

        # 详细日志：输出每条历史消息的角色和内容前50字符
        # 这是排查「LLM 忘记历史」问题的关键日志，可以看到历史是否正确加载
        history_preview = "; ".join([f"[{h['role']}] {h['content'][:50]}" for h in history])
        logger.info(f"获取对话历史: session_id={session_id}, window_size={window_size}, 数量={len(history)}, 历史=[{history_preview}]")
        return history


class TraceService:
    """
    溯源服务类（Traceability Service —— 可解释AI的数据基础）

    负责溯源记录的管理，追踪知识引用和数据来源。
    溯源记录是「可解释AI」(Explainable AI) 的数据基础：
      当 AI 回答一个问题后，用户可能想知道"你依据什么回答的？"
      Trace 记录了 AI 回答所引用的知识片段、执行的 SQL 等来源信息。

    溯源类型（trace_type）：
      - knowledge: 知识引用（RAG 检索命中的文档片段 + 相似度分数）
      - sql:       SQL 查询溯源（NL2SQL 生成的 SQL 语句 + 执行结果摘要）
      - data:      数据来源（查询的数据表、字段等元信息）

    典型流程：
      用户提问 → RAG检索 → 命中3个知识片段 → AI生成回答
                                          ↓
                                    为每个片段创建 Trace 记录
                                    (source_name=文档名, content=片段内容, score=相似度)
    """

    @staticmethod
    async def create(
        db: AsyncSession,
        session_id: int,
        message_id: int,
        trace_type: str,
        source_id: Optional[int] = None,
        source_name: Optional[str] = None,
        content: Optional[str] = None,
        score: Optional[int] = None,
    ) -> Trace:
        """
        创建溯源记录

        :param db: 数据库会话
        :param session_id: 会话ID
        :param message_id: 消息ID
        :param trace_type: 溯源类型（knowledge/sql/data）
        :param source_id: 来源ID（如知识文档ID、数据表ID）
        :param source_name: 来源名称（如文档标题、表名）
        :param content: 溯源内容片段（如知识片段摘要）
        :param score: 匹配分数（如RAG检索相似度分数）
        :return: 创建的溯源记录对象
        """
        logger.debug(f"创建溯源记录: message_id={message_id}, type={trace_type}, score={score}")
        trace = Trace(
            session_id=session_id,
            message_id=message_id,
            trace_type=trace_type,
            source_id=source_id,
            source_name=source_name,
            content=content,
            score=score,
        )
        db.add(trace)
        await db.commit()
        await db.refresh(trace)
        logger.debug(f"创建溯源记录成功: ID={trace.id}")
        return trace

    @staticmethod
    async def get_by_message(db: AsyncSession, message_id: int) -> List[Trace]:
        """
        获取消息的溯源记录列表

        :param db: 数据库会话
        :param message_id: 消息ID
        :return: 溯源记录列表
        """
        stmt = select(Trace).where(Trace.message_id == message_id)
        result = await db.execute(stmt)
        traces = list(result.scalars().all())
        logger.debug(f"获取消息溯源记录: message_id={message_id}, 数量={len(traces)}")
        return traces


# 服务实例
session_service = SessionService()
message_service = MessageService()
trace_service = TraceService()
logger.info("会话服务实例已创建")