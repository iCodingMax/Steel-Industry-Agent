"""
指标相关Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class MetricCreate(BaseModel):
    """创建指标请求"""
    name: str = Field(..., description="指标名称")
    code: str = Field(..., description="指标代码")
    description: Optional[str] = Field(None, description="指标描述")
    datasourceId: int = Field(..., description="数据源ID")
    sqlExpression: str = Field(..., description="SQL表达式")
    resultType: str = Field(default="number", description="结果类型: number/percent/string")
    unit: Optional[str] = Field(None, description="单位")
    groupName: Optional[str] = Field(None, description="分组名称")
    tags: Optional[List[str]] = Field(default_factory=list, description="标签")


class MetricUpdate(BaseModel):
    """更新指标请求"""
    name: Optional[str] = Field(None, description="指标名称")
    code: Optional[str] = Field(None, description="指标代码")
    description: Optional[str] = Field(None, description="指标描述")
    datasourceId: Optional[int] = Field(None, description="数据源ID")
    sqlExpression: Optional[str] = Field(None, description="SQL表达式")
    resultType: Optional[str] = Field(None, description="结果类型")
    unit: Optional[str] = Field(None, description="单位")
    groupName: Optional[str] = Field(None, description="分组名称")
    tags: Optional[List[str]] = Field(None, description="标签")
    status: Optional[str] = Field(None, description="状态")


class MetricResponse(BaseModel):
    """指标响应"""
    id: int
    name: str
    code: str
    description: Optional[str]
    datasourceId: int
    sqlExpression: str
    resultType: str
    unit: Optional[str]
    groupName: Optional[str]
    tags: List[str]
    status: str
    createdAt: Optional[str]
    updatedAt: Optional[str]
