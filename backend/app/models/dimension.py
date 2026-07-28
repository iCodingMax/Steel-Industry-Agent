"""
维度模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func

from app.core.base_model import Base


class Dimension(Base):
    """业务维度定义表"""

    __tablename__ = "dimensions"

    id = Column(Integer, primary_key=True, index=True, comment="维度ID")
    name = Column(String(100), nullable=False, comment="维度名称")
    code = Column(String(50), unique=True, nullable=False, index=True, comment="维度代码")
    description = Column(Text, nullable=True, comment="维度描述")
    datasource_id = Column(Integer, nullable=True, index=True, comment="数据源ID，未绑定则不参与智能问数")
    table_name = Column(String(100), nullable=False, comment="关联表名")
    column_name = Column(String(100), nullable=False, comment="关联列名")
    data_type = Column(String(20), nullable=True, comment="数据类型: string/number/date")
    level = Column(Integer, default=1, comment="层级(1=一级,2=二级...)")
    parent_id = Column(Integer, nullable=True, comment="父维度ID")
    hierarchy_path = Column(String(500), nullable=True, comment="层级路径")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "description": self.description,
            "datasourceId": self.datasource_id,
            "tableName": self.table_name,
            "columnName": self.column_name,
            "dataType": self.data_type,
            "level": self.level,
            "parentId": self.parent_id,
            "hierarchyPath": self.hierarchy_path,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
