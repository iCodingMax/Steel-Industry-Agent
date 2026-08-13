"""
会话与消息模型模块
定义对话会话、消息和全链路溯源的数据模型

数据关系：
- Session（会话）: 包含多个 Message（消息）和 Trace（溯源）
- Message（消息）: 属于一个 Session，记录用户输入和助手回复
- Trace（溯源）: 关联到 Message，记录知识引用和数据来源

注意：
- 使用 PostgreSQL JSONB 类型存储结构化数据（references、sql_traces、thinking_steps等）
- created_at/updated_at 使用 SQLAlchemy func.now() 自动生成
- 时间统一返回北京时间（UTC+8），确保前端显示一致
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base

# 北京时间时区
CST = timezone(timedelta(hours=8))


def _to_cst_iso(dt: datetime | None) -> str | None:
    """
    将时间转换为北京时间ISO格式字符串

    :param dt: 原始时间（通常是UTC）
    :return: 北京时间ISO格式字符串，如 '2024-01-15T14:30:00+08:00'
    """
    if dt is None:
        return None
    # 如果是naive datetime（无时区信息），假设为UTC时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # 转换为北京时间
    return dt.astimezone(CST).isoformat()


class Session(Base):
    """
    会话表
    存储用户与系统的对话会话信息
    每个会话包含多条消息，支持意图分类和状态管理

    用户关联说明：
    - user_id: 关联系统用户表(users)，满足外键约束，embed场景使用默认系统用户
    - chat_user_id: 关联对话用户表(chat_users)，可为空，用于embed场景的对话用户数据隔离
    """

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True, comment="会话ID")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="系统用户ID")
    chat_user_id = Column(Integer, ForeignKey("chat_users.id"), nullable=True, index=True, comment="对话用户ID(嵌入模式使用，可为空)")
    title = Column(String(200), nullable=True, comment="会话标题")
    intent_type = Column(String(20), nullable=True, comment="会话意图类型: knowledge/data/hybrid")
    llm_config_id = Column(Integer, nullable=True, comment="LLM配置ID")
    status = Column(String(20), default="active", comment="状态: active/archived")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典，时间统一转换为北京时间"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "chatUserId": self.chat_user_id,
            "title": self.title,
            "intentType": self.intent_type,
            "llmConfigId": self.llm_config_id,
            "status": self.status,
            "createdAt": _to_cst_iso(self.created_at),
            "updatedAt": _to_cst_iso(self.updated_at),
        }


class Message(Base):
    """
    消息表
    存储对话中的每条消息，包括用户输入和助手回复
    消息包含丰富的元数据，支持知识引用、SQL溯源、图表推荐、工具调用等功能
    """

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, comment="消息ID")
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True, comment="会话ID")
    role = Column(String(20), nullable=False, comment="角色: user/assistant")
    content = Column(Text, nullable=False, comment="消息内容")
    intent = Column(String(20), nullable=True, comment="消息意图: knowledge/data/mcp/skill/hybrid/chat")
    references = Column(JSONB, nullable=True, comment="引用信息(JSON)")
    sql_traces = Column(JSONB, nullable=True, comment="SQL溯源(JSON)")
    data_result = Column(JSONB, nullable=True, comment="查询结果数据(JSON)")
    column_meta = Column(JSONB, nullable=True, comment="字段元信息(JSON)")
    chart_type = Column(String(20), nullable=True, comment="推荐图表类型")
    thinking_steps = Column(JSONB, nullable=True, comment="思考过程步骤(JSON)")
    tool_calls = Column(JSONB, nullable=True, comment="工具调用信息(JSON)")
    tool_results = Column(JSONB, nullable=True, comment="工具调用结果(JSON)")
    query_time = Column(Integer, nullable=True, comment="查询耗时(毫秒)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        """转换为字典，时间统一转换为北京时间"""
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
            "toolCalls": self.tool_calls,
            "toolResults": self.tool_results,
            "queryTime": self.query_time,
            "createdAt": _to_cst_iso(self.created_at),
        }


class Trace(Base):
    """
    全链路溯源表
    记录消息的来源信息，支持知识引用、数据来源和SQL追踪
    用于实现回答的可解释性和数据溯源
    """

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
        """转换为字典，时间统一转换为北京时间"""
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "messageId": self.message_id,
            "traceType": self.trace_type,
            "sourceId": self.source_id,
            "sourceName": self.source_name,
            "content": self.content,
            "score": self.score,
            "createdAt": _to_cst_iso(self.created_at),
        }