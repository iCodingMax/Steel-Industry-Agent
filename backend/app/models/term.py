"""
术语模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.base_model import Base


class Term(Base):
    """业务术语定义表"""

    __tablename__ = "terms"

    id = Column(Integer, primary_key=True, index=True, comment="术语ID")
    term = Column(String(100), nullable=False, comment="术语名称")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="术语代码")
    definition = Column(Text, nullable=True, comment="术语定义")
    category = Column(String(50), nullable=True, comment="分类")
    synonyms = Column(Text, nullable=True, comment="同义词(JSON数组)")
    datasource_id = Column(Integer, nullable=True, index=True, comment="关联数据源ID")
    related_terms = Column(Text, nullable=True, comment="相关术语(JSON数组)")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        import json
        return {
            "id": self.id,
            "term": self.term,
            "code": self.code,
            "definition": self.definition,
            "category": self.category,
            "synonyms": json.loads(self.synonyms) if self.synonyms else [],
            "datasourceId": self.datasource_id,
            "relatedTerms": json.loads(self.related_terms) if self.related_terms else [],
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
