"""
智能体长期记忆模型模块
定义 MasterAgent 长期记忆（三层记忆之长期记忆层）的数据模型

数据关系：
- AgentMemory（长期记忆）: 关联 Application，可选关联 User/Session

设计说明：
- 存储用户偏好/设备档案/诊断结论，供 planner 节点检索注入上下文
- 使用 pgvector VECTOR(1024)（bge-m3 嵌入维度）+ HNSW 余弦相似度索引
- 表位于系统库 steel_agent（与 applications 同库，保留外键级联）
- 治理机制：人工清理接口 + expires_at 时效控制（防记忆污染）
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Index
from sqlalchemy.sql import func

from app.core.base_model import Base

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


class AgentMemory(Base):
    """
    智能体长期记忆表
    存储跨会话沉淀的记忆条目，支持向量相似度检索
    """

    __tablename__ = "agent_memories"

    id = Column(Integer, primary_key=True, index=True, comment="记忆ID")
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, comment="所属应用ID(应用级记忆隔离)")
    user_id = Column(Integer, nullable=True, comment="关联用户ID(为空表示应用级公共记忆)")
    memory_type = Column(String(30), nullable=False, comment="记忆类型: preference(用户偏好)/fact(设备档案)/diagnosis_conclusion(诊断结论)")
    content = Column(Text, nullable=False, comment="记忆文本内容")
    # pgvector 向量列（bge-m3，1024维）；驱动未安装时降级为 NULL 列由 SQL 脚本兜底建列
    embedding = Column(Vector(1024), nullable=True, comment="记忆内容向量(bge-m3,1024维)") if Vector else Column(Text, nullable=True, comment="记忆内容向量(降级占位列)")
    session_id = Column(Integer, nullable=True, comment="来源会话ID(溯源用,指向sessions.id)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    expires_at = Column(DateTime, nullable=True, comment="过期时间(为空表示永久有效)")

    __table_args__ = (
        Index("idx_agent_memories_app_user", "application_id", "user_id"),
        Index("idx_agent_memories_type", "memory_type"),
        Index("idx_agent_memories_expires", "expires_at"),
        {
            "comment": "智能体长期记忆表(用户偏好/设备档案/诊断结论,pgvector向量检索)",
        },
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "applicationId": self.application_id,
            "userId": self.user_id,
            "memoryType": self.memory_type,
            "content": self.content,
            "sessionId": self.session_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "expiresAt": self.expires_at.isoformat() if self.expires_at else None,
        }
