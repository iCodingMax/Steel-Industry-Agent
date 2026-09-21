"""
表关系相关Schema（NL2SQL 升级二期）
"""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class RelationCreate(BaseModel):
    """新建表关系请求（人工录入）"""
    leftTable: str = Field(..., description="左表名", min_length=1, max_length=100)
    leftColumn: str = Field(..., description="左表关联字段", min_length=1, max_length=100)
    rightTable: str = Field(..., description="右表名", min_length=1, max_length=100)
    rightColumn: str = Field(..., description="右表关联字段", min_length=1, max_length=100)
    joinType: Optional[Literal["inner", "left"]] = Field("inner", description="JOIN类型")
    relationDesc: Optional[str] = Field(None, description="关系描述", max_length=255)
    cardinality: Optional[Literal["1:1", "1:N", "N:1", "M:N"]] = Field("1:1", description="基数")
    relationGroup: Optional[str] = Field(None, description="复合关联键分组ID", max_length=50)


class RelationUpdate(BaseModel):
    """编辑表关系请求（基数/描述/JOIN类型/状态/关联键分组）"""
    joinType: Optional[Literal["inner", "left"]] = Field(None, description="JOIN类型")
    relationDesc: Optional[str] = Field(None, description="关系描述", max_length=255)
    cardinality: Optional[Literal["1:1", "1:N", "N:1", "M:N"]] = Field(None, description="基数")
    status: Optional[Literal["active", "inactive", "ignored"]] = Field(None, description="状态")
    relationGroup: Optional[str] = Field(None, description="复合关联键分组ID", max_length=50)


class BatchActionRequest(BaseModel):
    """批量确认/忽略请求"""
    ids: List[int] = Field(..., description="关系ID列表", min_length=1)


class BatchConfirmRequest(BatchActionRequest):
    """批量确认请求（可统一补充基数）"""
    cardinality: Optional[Literal["1:1", "1:N", "N:1", "M:N"]] = Field(None, description="统一基数")


class ProbeRequest(BaseModel):
    """SQL 探测请求（服务端拼装SQL，不接受前端传SQL）"""
    leftTable: str = Field(..., description="左表名", min_length=1, max_length=100)
    leftColumn: str = Field(..., description="左表关联字段", min_length=1, max_length=100)
    rightTable: str = Field(..., description="右表名", min_length=1, max_length=100)
    rightColumn: str = Field(..., description="右表关联字段", min_length=1, max_length=100)
