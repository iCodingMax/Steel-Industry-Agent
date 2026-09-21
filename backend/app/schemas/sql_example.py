"""
示例SQL库相关Schema（NL2SQL 升级二期：Few-shot 手工示例库）
"""
from typing import Optional, Literal
from pydantic import BaseModel, Field


class SqlExampleCreate(BaseModel):
    """新增示例SQL请求"""
    question: str = Field(..., description="标准问题（向量召回键）", min_length=1)
    sql: str = Field(..., description="标准答案SQL", min_length=1)
    description: Optional[str] = Field(None, description="备注说明（适用场景、口径约定等）", max_length=500)
    status: Optional[Literal["active", "retired"]] = Field("active", description="启用状态")


class SqlExampleUpdate(BaseModel):
    """编辑示例SQL请求（仅 manual 来源）"""
    datasourceId: Optional[int] = Field(None, description="目标数据源ID（切换归属，切换后重取Schema版本）")
    question: Optional[str] = Field(None, description="标准问题（变更时重新向量化）", min_length=1)
    sql: Optional[str] = Field(None, description="标准答案SQL（变更时重新校验）", min_length=1)
    description: Optional[str] = Field(None, description="备注说明", max_length=500)


class SqlExampleStatusUpdate(BaseModel):
    """启用/停用示例SQL请求"""
    status: Literal["active", "retired"] = Field(..., description="目标状态")
