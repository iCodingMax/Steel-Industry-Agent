"""
术语相关Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class TermCreate(BaseModel):
    """创建术语请求"""
    term: str = Field(..., description="术语名称")
    code: str = Field(..., description="术语代码")
    definition: Optional[str] = Field(None, description="术语定义")
    category: Optional[str] = Field(None, description="分类")
    synonyms: Optional[List[str]] = Field(default_factory=list, description="同义词")
    datasourceId: Optional[int] = Field(None, description="关联数据源ID")
    relatedTerms: Optional[List[str]] = Field(default_factory=list, description="相关术语")


class TermUpdate(BaseModel):
    """更新术语请求"""
    term: Optional[str] = Field(None, description="术语名称")
    code: Optional[str] = Field(None, description="术语代码")
    definition: Optional[str] = Field(None, description="术语定义")
    category: Optional[str] = Field(None, description="分类")
    synonyms: Optional[List[str]] = Field(None, description="同义词")
    datasourceId: Optional[int] = Field(None, description="关联数据源ID")
    relatedTerms: Optional[List[str]] = Field(None, description="相关术语")
    status: Optional[str] = Field(None, description="状态")


class TermResponse(BaseModel):
    """术语响应"""
    id: int
    term: str
    code: str
    definition: Optional[str]
    category: Optional[str]
    synonyms: List[str]
    datasourceId: Optional[int]
    relatedTerms: List[str]
    status: str
    createdAt: Optional[str]
    updatedAt: Optional[str]
