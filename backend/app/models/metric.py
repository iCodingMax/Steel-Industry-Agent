"""
指标模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.base_model import Base

# pgvector 向量类型（驱动缺失时降级为占位列，参照 SqlExample/agent_memory 模式）
try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


class Metric(Base):
    """业务指标定义表"""

    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True, comment="指标ID")
    name = Column(String(100), nullable=False, comment="指标名称")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="指标代码")
    description = Column(Text, nullable=True, comment="指标描述")
    datasource_id = Column(Integer, nullable=True, index=True, comment="数据源ID，未绑定则不参与智能问数")
    sql_expression = Column(Text, nullable=False, comment="SQL表达式")
    result_type = Column(String(20), default="number", comment="结果类型: number/percent/string")
    unit = Column(String(20), nullable=True, comment="单位")
    group_name = Column(String(50), nullable=True, comment="分组名称")
    tags = Column(String(255), nullable=True, comment="标签(JSON数组)")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    # 指标召回键向量化（方案8：名称+描述+标签拼接向量，Top-K 召回候选供 LLM 精选）
    # 驱动未安装时降级为占位列，召回侧过滤 embedding IS NOT NULL，回退 LLM 全量匹配
    embedding = (
        Column(Vector(1024), nullable=True, comment="指标召回键向量(bge-m3,1024维)")
        if Vector
        else Column(Text, nullable=True, comment="指标召回键向量(降级占位列)")
    )
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        import json
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "datasourceId": self.datasource_id,
            "sqlExpression": self.sql_expression,
            "resultType": self.result_type,
            "unit": self.unit,
            "groupName": self.group_name,
            "tags": json.loads(self.tags) if self.tags else [],
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
