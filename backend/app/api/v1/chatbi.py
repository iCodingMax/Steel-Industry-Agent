"""
ChatBI智能问数API
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.database import get_mysql_session
from app.services.chatbi_service import chatbi_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


class ChatBIQuery(BaseModel):
    """智能问数请求"""
    question: str = Field(..., description="用户问题", min_length=1)
    datasourceId: Optional[int] = Field(None, description="数据源ID（可选）")


class ChatBIResponse(BaseModel):
    """智能问数响应"""
    explanation: str
    data: Optional[List[dict]]
    sqlTraces: List[dict]
    queryTime: float
    columnMeta: Optional[List[dict]] = None
    chartType: Optional[str] = None


@router.post("/query", summary="智能问数")
async def query_data(
    data: ChatBIQuery,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """智能问数查询"""
    explanation, results, sql_traces, query_time, _, column_meta, chart_type = await chatbi_service.query(
        db,
        data.question,
        data.datasourceId,
    )

    response = ChatBIResponse(
        explanation=explanation,
        data=results,
        sqlTraces=sql_traces,
        queryTime=query_time,
        columnMeta=column_meta,
        chartType=chart_type,
    )
    return success_response(data=response)