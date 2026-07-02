"""
数据源相关Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class DataSourceCreate(BaseModel):
    """创建数据源请求"""
    name: str = Field(..., description="数据源名称")
    type: str = Field(..., description="数据库类型: mysql/postgresql/clickhouse/oracle")
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口")
    database: str = Field(..., description="数据库名")
    username: str = Field(..., description="用户名")
    password: Optional[str] = Field(None, description="密码")
    charset: str = Field(default="utf8mb4", description="字符集")
    poolSize: int = Field(default=5, description="连接池大小")
    maxOverflow: int = Field(default=10, description="最大溢出连接数")
    description: Optional[str] = Field(None, description="描述")


class DataSourceUpdate(BaseModel):
    """更新数据源请求"""
    name: Optional[str] = Field(None, description="数据源名称")
    type: Optional[str] = Field(None, description="数据库类型")
    host: Optional[str] = Field(None, description="主机地址")
    port: Optional[int] = Field(None, description="端口")
    database: Optional[str] = Field(None, description="数据库名")
    username: Optional[str] = Field(None, description="用户名")
    password: Optional[str] = Field(None, description="密码")
    charset: Optional[str] = Field(None, description="字符集")
    poolSize: Optional[int] = Field(None, description="连接池大小")
    maxOverflow: Optional[int] = Field(None, description="最大溢出连接数")
    description: Optional[str] = Field(None, description="描述")
    status: Optional[str] = Field(None, description="状态")


class DataSourceResponse(BaseModel):
    """数据源响应"""
    id: int
    name: str
    type: str
    host: str
    port: int
    database: str
    username: str
    charset: str
    poolSize: int
    maxOverflow: int
    description: Optional[str]
    status: str
    createdAt: Optional[str]
    updatedAt: Optional[str]


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    type: str = Field(..., description="数据库类型")
    host: str = Field(..., description="主机地址")
    port: int = Field(..., description="端口")
    database: str = Field(..., description="数据库名")
    username: str = Field(..., description="用户名")
    password: Optional[str] = Field(None, description="密码")
    charset: Optional[str] = Field("utf8mb4", description="字符集")


class TableSchemaResponse(BaseModel):
    """表结构响应"""
    id: int
    datasourceId: int
    tableName: str
    tableComment: Optional[str]
    columns: List[dict]
    createdAt: Optional[str]


class ColumnInfo(BaseModel):
    """列信息"""
    name: str
    type: str
    comment: Optional[str]
    nullable: bool
    primaryKey: bool
    default: Optional[str]
