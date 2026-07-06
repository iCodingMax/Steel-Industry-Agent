"""
会话与消息模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.sql import func

from app.core.base_model import Base


class Session(Base):
    """会话表"""

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True, comment="会话ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    title = Column(String(200), nullable=True, comment="会话标题")
    intent_type = Column(String(20), nullable=True, comment="会话意图类型: knowledge/data/hybrid")
    status = Column(String(20), default="active", comment="状态: active/archived")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "title": self.title,
            "intentType": self.intent_type,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class Message(Base):
    """消息表"""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, comment="消息ID")
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True, comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    intent = Column(String(20), nullable=True, comment="消息意图: knowledge/data/hybrid")
    references = Column(JSON, nullable=True, comment="引用信息(JSON)")
    sql_traces = Column(JSON, nullable=True, comment="SQL溯源(JSON)")
    data_result = Column(JSON, nullable=True, comment="查询结果数据(JSON)")
    column_meta = Column(JSON, nullable=True, comment="字段元信息(JSON)")
    chart_type = Column(String(20), nullable=True, comment="推荐图表类型")
    thinking_steps = Column(JSON, nullable=True, comment="思考过程步骤(JSON)")
    query_time = Column(Integer, nullable=True, comment="查询耗时(毫秒)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "role": self.role,
            "content": self.content,
            "intent": self.intent,
            "references": self.references,
            "sqlTraces": self.sql_traces,
            "dataResult": self.data_result,
            "columnMeta": self.column_meta,
            "chartType": self.chart_type,
            "thinkingSteps": self.thinking_steps,
            "queryTime": self.query_time,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }


class Trace(Base):
    """全链路溯源表"""

    __tablename__ = "traces"

    id = Column(Integer, primary_key=True, index=True, comment="溯源ID")
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True, comment="会话ID")
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=False, index=True, comment="消息ID")
    trace_type = Column(String(20), nullable=False, comment="溯源类型: knowledge/data/sql")
    source_id = Column(Integer, nullable=True, comment="来源ID(文档ID/数据源ID)")
    source_name = Column(String(200), nullable=True, comment="来源名称")
    content = Column(Text, nullable=True, comment="溯源内容")
    score = Column(Integer, nullable=True, comment="匹配分数")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "messageId": self.message_id,
            "traceType": self.trace_type,
            "sourceId": self.source_id,
            "sourceName": self.source_name,
            "content": self.content,
            "score": self.score,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }