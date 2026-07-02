"""
维度相关Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class DimensionCreate(BaseModel):
    """创建维度请求"""
    name: str = Field(..., description="维度名称")
    code: str = Field(..., description="维度代码")
    description: Optional[str] = Field(None, description="维度描述")
    datasourceId: int = Field(..., description="数据源ID")
    tableName: str = Field(..., description="关联表名")
    columnName: str = Field(..., description="关联列名")
    dataType: Optional[str] = Field(None, description="数据类型")
    level: int = Field(default=1, description="层级")
    parentId: Optional[int] = Field(None, description="父维度ID")


class DimensionUpdate(BaseModel):
    """更新维度请求"""
    name: Optional[str] = Field(None, description="维度名称")
    code: Optional[str] = Field(None, description="维度代码")
    description: Optional[str] = Field(None, description="维度描述")
    datasourceId: Optional[int] = Field(None, description="数据源ID")
    tableName: Optional[str] = Field(None, description="关联表名")
    columnName: Optional[str] = Field(None, description="关联列名")
    dataType: Optional[str] = Field(None, description="数据类型")
    level: Optional[int] = Field(None, description="层级")
    parentId: Optional[int] = Field(None, description="父维度ID")
    status: Optional[str] = Field(None, description="状态")


class DimensionResponse(BaseModel):
    """维度响应"""
    id: int
    name: str
    code: str
    description: Optional[str]
    datasourceId: int
    tableName: str
    columnName: str
    dataType: Optional[str]
    level: int
    parentId: Optional[int]
    hierarchyPath: Optional[str]
    status: str
    createdAt: Optional[str]
    updatedAt: Optional[str]
