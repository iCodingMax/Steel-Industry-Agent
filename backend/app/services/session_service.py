"""
会话管理服务
功能：会话CRUD、消息管理、上下文管理
"""
from typing import List, Optional
from loguru import logger

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import Session, Message, Trace
from app.middlewares.exception_handler import BusinessException


class SessionService:
    """会话服务类"""

    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: int,
        title: Optional[str] = None,
    ) -> Session:
        """创建会话"""
        session = Session(
            user_id=user_id,
            title=title or "新对话",
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        logger.info(f"创建会话: ID={session.id}, 用户={user_id}")
        return session

    @staticmethod
    async def get_by_id(db: AsyncSession, session_id: int) -> Optional[Session]:
        """根据ID获取会话"""
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
        """获取用户的会话列表"""
        stmt = select(Session).where(Session.user_id == user_id).order_by(Session.updated_at.desc()).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update_title(
        db: AsyncSession,
        session_id: int,
        title: str,
    ) -> Optional[Session]:
        """更新会话标题"""
        session = await SessionService.get_by_id(db, session_id)
        if not session:
            raise BusinessException(code=404, message="会话不存在")

        session.title = title
        await db.commit()
        await db.refresh(session)
        logger.info(f"更新会话标题: ID={session_id}, 标题={title}")
        return session

    @staticmethod
    async def delete(db: AsyncSession, session_id: int) -> None:
        """删除会话"""
        session = await SessionService.get_by_id(db, session_id)
        if not session:
            raise BusinessException(code=404, message="会话不存在")

        # 删除关联的消息和溯源
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Trace).where(Trace.session_id == session_id))
        await db.delete(session)
        await db.commit()
        logger.info(f"删除会话: ID={session_id}")


class MessageService:
    """消息服务类"""

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
        query_time: Optional[int] = None,
    ) -> Message:
        """创建消息"""
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
            query_time=query_time,
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        logger.info(f"创建消息: 会话={session_id}, 角色={role}")
        return message

    @staticmethod
    async def get_by_session(
        db: AsyncSession,
        session_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """获取会话的消息列表"""
        stmt = select(Message).where(Message.session_id == session_id).order_by(Message.created_at).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_history(
        db: AsyncSession,
        session_id: int,
        window_size: int = 10,
    ) -> List[dict]:
        """获取对话历史（用于上下文）"""
        messages = await MessageService.get_by_session(db, session_id, limit=window_size)
        history = []
        for msg in messages:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })
        return history


class TraceService:
    """溯源服务类"""

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
        """创建溯源记录"""
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
        return trace

    @staticmethod
    async def get_by_message(db: AsyncSession, message_id: int) -> List[Trace]:
        """获取消息的溯源记录"""
        stmt = select(Trace).where(Trace.message_id == message_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())


# 服务实例
session_service = SessionService()
message_service = MessageService()
trace_service = TraceService()