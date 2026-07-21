"""
数据模型模块初始化
确保所有模型被导入，以便SQLAlchemy自动建表
"""
from app.models.user import User
from app.models.datasource import DataSource, TableSchema
from app.models.metric import Metric
from app.models.dimension import Dimension
from app.models.term import Term
from app.models.llm_config import LLMConfig
from app.models.knowledge import KnowledgeBase, Document, DocumentSegment
from app.models.application import Application, AppPrompt
from app.models.session import Session, Message, Trace
from app.models.audit_log import AuditLog

__all__ = [
    "User",
    "DataSource",
    "TableSchema",
    "Metric",
    "Dimension",
    "Term",
    "LLMConfig",
    "KnowledgeBase",
    "Document",
    "DocumentSegment",
    "Application",
    "AppPrompt",
    "Session",
    "Message",
    "Trace",
    "AuditLog",
]
