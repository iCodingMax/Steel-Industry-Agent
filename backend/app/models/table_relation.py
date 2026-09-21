"""
表关系元数据模型（NL2SQL 升级二期：联表查询关联键白名单）

设计约束：
- TableRelation 以 table_name/column 字符串关联，禁止引入 table_schema_id 外键
  （sync_schema 先删后插并重置序列，TableSchema.id 不稳定，见方案 4.1）
- 端点本质是无向边的两端，存储时按字典序规范化方向，保证同一条物理关系唯一存储
- probe 字段缓存 SQL 探测结论（基数/放大系数），避免重复探测
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


class TableRelation(Base):
    """
    表关系元数据（联表查询的关联键白名单）

    采集来源（source）：
        - foreign_key: 数据库外键声明（事实，默认生效，仅允许停用不允许删除）
        - auto_guess:  同名同类型字段推荐（待人工确认，不参与 JOIN 白名单）
        - manual:      人工录入（表单/画布连线/SQL 探测后保存）

    状态（status）：
        - active:   已生效（参与 NL2SQL JOIN 白名单）
        - inactive: 待确认/引用失效（不参与白名单）
        - ignored:  已忽略（不参与白名单）
    """

    __tablename__ = "table_relations"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, nullable=False, index=True, comment="数据源ID")
    left_table = Column(String(100), nullable=False, comment="左表名（规范化方向：字典序较小端）")
    left_column = Column(String(100), nullable=False, comment="左表关联字段")
    right_table = Column(String(100), nullable=False, comment="右表名（规范化方向：字典序较大端）")
    right_column = Column(String(100), nullable=False, comment="右表关联字段")
    join_type = Column(String(20), default="inner", comment="默认JOIN类型: inner/left")
    relation_desc = Column(String(255), nullable=True, comment="关系描述，如'一炉次一次打分'")
    cardinality = Column(String(20), default="1:1", comment="基数: 1:1/1:N/N:1/M:N（规范化方向左端→右端）")
    relation_group = Column(String(50), nullable=True, comment="复合关联键分组ID，同组多条字段对构成联合关联")
    source = Column(String(20), default="manual", comment="来源: foreign_key/auto_guess/manual")
    status = Column(String(20), default="active", comment="状态: active/inactive(待确认)/ignored(已忽略)")
    probe = Column(JSONB, nullable=True, comment="SQL探测结论缓存 {factor, verdict, probedAt}")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    __table_args__ = (
        # 四元组唯一约束（存储规范化后同一条物理关系只有唯一方向）
        UniqueConstraint(
            "datasource_id", "left_table", "left_column",
            "right_table", "right_column", name="uq_table_relation",
        ),
        Index("ix_table_relations_ds_status", "datasource_id", "status"),
        {"comment": "表关系元数据(NL2SQL联表查询关联键白名单)"},
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "datasourceId": self.datasource_id,
            "leftTable": self.left_table,
            "leftColumn": self.left_column,
            "rightTable": self.right_table,
            "rightColumn": self.right_column,
            "joinType": self.join_type,
            "relationDesc": self.relation_desc,
            "cardinality": self.cardinality,
            "relationGroup": self.relation_group,
            "source": self.source,
            "status": self.status,
            "probe": self.probe,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
