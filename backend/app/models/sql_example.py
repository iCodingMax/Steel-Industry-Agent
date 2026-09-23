"""
NL2SQL Few-shot 示例库模型（NL2SQL 升级二期：手工示例SQL库，参考 SQLBot）

设计要点：
- 手工录入（manual，二期）与自动沉淀（auto，后续排期）共用同一张表，以 source 区分
- question 为向量召回键，保存/编辑时向量化（pgvector 降级占位列模式复刻 agent_memory）
- schema_version 记录沉淀时的 Schema 版本，结构变更后防漂移（召回时跳过旧版本示例）
- status=retired 表示停用/下架，不参与注入
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.base_model import Base

# pgvector 向量类型（驱动缺失时降级为占位列，参照 SchemaEmbedding/agent_memory 模式）
try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover
    Vector = None


class SqlExample(Base):
    """NL2SQL Few-shot 示例库（手工录入 + 执行沉淀共用，以 source 区分）"""

    __tablename__ = "sql_examples"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, nullable=False, index=True, comment="数据源ID")
    question = Column(Text, nullable=False, comment="标准问题（向量召回键）")
    sql = Column(Text, nullable=False, comment="标准答案SQL（手工录入/执行成功沉淀）")
    description = Column(String(500), nullable=True, comment="备注说明（适用场景、口径约定等）")
    source = Column(String(20), default="manual", comment="来源: manual(手工录入,二期)/auto(自动沉淀,后续)")
    # 问题向量化（召回键）；驱动未安装时降级为占位列，召回侧过滤 embedding IS NOT NULL
    embedding = (
        Column(Vector(1024), nullable=True, comment="问题向量化(bge-m3,1024维)")
        if Vector
        else Column(Text, nullable=True, comment="问题向量化(降级占位列)")
    )
    schema_version = Column(Integer, default=1, comment="沉淀时的Schema版本（结构变更后召回时跳过旧版本）")
    status = Column(String(20), default="active", comment="状态: active/retired(停用或下架)")
    success_count = Column(Integer, default=0, comment="同题复用成功次数（auto来源）")
    feedback = Column(String(20), nullable=True, comment="用户反馈: like/dislike（auto来源，后续排期）")
    created_by = Column(Integer, nullable=True, comment="创建人ID（manual来源）")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        """转换为字典（向量字段不返回）"""
        return {
            "id": self.id,
            "datasourceId": self.datasource_id,
            "question": self.question,
            "sql": self.sql,
            "description": self.description,
            "source": self.source,
            "schemaVersion": self.schema_version,
            "status": self.status,
            "successCount": self.success_count,
            # 晋升建议（治理2）：auto 来源同题复用成功≥5次，提示可人工审核转为指标
            "suggestPromotion": self.source == "auto" and (self.success_count or 0) >= 5,
            "feedback": self.feedback,
            "createdBy": self.created_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
