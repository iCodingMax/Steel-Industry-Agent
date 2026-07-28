"""
数据源模型模块
定义数据源配置和表结构缓存的数据模型

数据关系：
- DataSource（数据源）: 包含多个 TableSchema（表结构）
- TableSchema（表结构）: 关联到 DataSource，缓存表和字段信息

支持的数据库类型：
- MySQL
- PostgreSQL
- SQL Server

注意：
- 密码字段存储加密后的密码
- TableSchema 使用 JSONB 缓存列信息，避免频繁查询业务数据库
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


class DataSource(Base):
    """
    数据源配置表
    存储业务数据库连接配置
    支持多种数据库类型和连接池配置
    """

    __tablename__ = "datasources"

    id = Column(Integer, primary_key=True, index=True, comment="数据源ID")
    name = Column(String(100), nullable=False, comment="数据源名称")
    type = Column(String(20), nullable=False, comment="数据库类型: mysql/postgresql/sqlserver")
    host = Column(String(255), nullable=False, comment="主机地址")
    port = Column(Integer, nullable=False, comment="端口")
    database = Column(String(100), nullable=False, comment="数据库名")
    username = Column(String(100), nullable=False, comment="用户名")
    password = Column(String(255), nullable=True, comment="密码(加密存储)")
    charset = Column(String(20), default="utf8mb4", comment="字符集")
    pool_size = Column(Integer, default=5, comment="连接池大小")
    max_overflow = Column(Integer, default=10, comment="最大溢出连接数")
    description = Column(Text, nullable=True, comment="描述")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(Integer, nullable=True, comment="创建人ID")

    def to_dict(self, include_password: bool = False) -> dict:
        """转换为字典"""
        data = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "username": self.username,
            "charset": self.charset,
            "poolSize": self.pool_size,
            "maxOverflow": self.max_overflow,
            "description": self.description,
            "status": self.status,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_password and self.password:
            data["password"] = self.password
        return data


class TableSchema(Base):
    """
    数据源表结构缓存表
    缓存业务数据库的表结构信息，避免频繁查询INFORMATION_SCHEMA
    列信息以JSONB格式存储，包含字段名、类型、注释等元数据
    """

    __tablename__ = "table_schemas"

    id = Column(Integer, primary_key=True, index=True)
    datasource_id = Column(Integer, nullable=False, index=True, comment="数据源ID")
    table_name = Column(String(100), nullable=False, comment="表名")
    table_comment = Column(Text, nullable=True, comment="表注释")
    columns = Column(JSONB, nullable=True, comment="列信息(JSON)")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "datasourceId": self.datasource_id,
            "tableName": self.table_name,
            "tableComment": self.table_comment,
            "columns": self.columns if self.columns else [],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
