"""
会话管理服务模块
管理对话会话、消息和溯源记录的完整生命周期

主要功能：
1. 会话管理：创建、查询、更新、删除会话
2. 消息管理：创建消息、获取会话消息列表、获取对话历史
3. 溯源管理：创建和查询溯源记录（用于追踪知识引用和数据来源）

数据模型关系：
- Session（会话）: 包含多个 Message（消息）和 Trace（溯源）
- Message（消息）: 属于一个 Session，包含内容、意图、引用等信息
- Trace（溯源）: 关联到 Message，记录知识片段或数据来源
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
        获取用户的会话列表

        :param db: 数据库会话
        :param user_id: 用户ID
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数，默认50）
        :return: 会话列表（按最新消息时间降序排列，无消息的会话按更新时间排序）
        """
        # 子查询：每个会话的最新消息时间
        latest_msg_subq = (
            select(
                Message.session_id.label("sid"),
                func.max(Message.created_at).label("latest_msg_time"),
            )
            .group_by(Message.session_id)
            .subquery()
        )
        # 按最新消息时间降序排列，无消息的会话按updated_at排后面
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

        :param db: 数据库会话
        :param session_id: 会话ID
        :raises BusinessException: 会话不存在时抛出
        """
        session = await SessionService.get_by_id(db, session_id)
        if not session:
            raise BusinessException(code=404, message="会话不存在")

        # 删除关联的消息和溯源记录（级联删除）
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Trace).where(Trace.session_id == session_id))
        await db.delete(session)
        await db.commit()
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
        :param intent: 意图分类（knowledge/data/mcp/skill/hybrid）
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
        # 同步更新会话的updated_at，确保会话列表按最新消息排序
        from sqlalchemy import update as sql_update
        await db.execute(
            sql_update(Session).where(Session.id == session_id).values(updated_at=func.now())
        )
        await db.commit()
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
        获取对话历史（用于LLM多轮对话上下文）

        从最近的消息开始向前回溯，截取指定条数的历史消息，
        并对每条消息内容做长度截断，避免超出LLM上下文窗口。

        :param db: 数据库会话
        :param session_id: 会话ID
        :param window_size: 返回最近的消息条数，None时从配置读取CHAT_HISTORY_LIMIT
        :return: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        """
        from app.core.config import settings

        if window_size is None:
            window_size = settings.CHAT_HISTORY_LIMIT

        if not session_id or session_id <= 0:
            return []

        # 先取最近 window_size 条消息（按id倒序取，再正序返回）
        from sqlalchemy import desc as sql_desc
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(sql_desc(Message.id))
            .limit(window_size)
        )
        result = await db.execute(stmt)
        recent_msgs = list(reversed(list(result.scalars().all())))

        history: List[dict] = []
        for msg in recent_msgs:
            content = (msg.content or "").strip()
            if not content:
                continue
            # 单条消息内容过长时截断，避免占用过多token
            if len(content) > 800:
                content = content[:800] + "..."
            history.append({"role": msg.role, "content": content})

        logger.debug(f"获取对话历史: session_id={session_id}, 数量={len(history)}")
        return history


class TraceService:
    """
    溯源服务类
    负责溯源记录的管理，追踪知识引用和数据来源
    溯源记录用于记录消息的来源信息，支持知识引用、SQL查询等场景
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