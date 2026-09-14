"""
智能体记忆管理API
功能：长期记忆（agent_memories）查询、删除、过期清理治理入口

设计说明：
- 记忆由 MasterAgent 在问答收尾时自动沉淀（LLM抽取），本API提供人工治理能力
- 查询/删除均需登录认证；application_id 为必填过滤条件（应用级记忆隔离）
- purge-expired 可由运维定时任务或管理端手动触发（TTL清理）
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db_session
from app.models.user import User
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user
from app.services.agent_memory_service import (
    agent_memory_service,
    MemoryServiceError,
    VALID_MEMORY_TYPES,
)

router = APIRouter()


@router.get("", summary="查询记忆列表")
async def list_memories(
    applicationId: int = Query(..., description="应用ID（必填，应用级记忆隔离）"),
    userId: Optional[int] = Query(None, description="用户ID筛选（缺省查全部用户+公共记忆）"),
    memoryType: Optional[str] = Query(None, description="记忆类型筛选"),
    includeExpired: bool = Query(False, description="是否包含已过期记忆（默认过滤）"),
    limit: int = Query(100, ge=1, le=500, description="分页大小"),
    offset: int = Query(0, ge=0, description="分页偏移"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """
    分页查询指定应用的长期记忆列表

    支持按用户ID、记忆类型筛选；默认过滤已过期记忆
    """
    # 记忆类型合法性校验（防止无效枚举透传到SQL）
    if memoryType and memoryType not in VALID_MEMORY_TYPES:
        raise BusinessException(
            code=400,
            message=f"无效的记忆类型: {memoryType}，可选值: {', '.join(VALID_MEMORY_TYPES)}",
        )

    try:
        rows = await agent_memory_service.list_memories(
            db,
            application_id=applicationId,
            user_id=userId,
            memory_type=memoryType,
            include_expired=includeExpired,
            limit=limit,
            offset=offset,
        )
        return success_response(data={"items": rows, "limit": limit, "offset": offset})
    except MemoryServiceError as e:
        logger.error(f"[记忆管理API] 查询失败: {e}")
        raise BusinessException(code=500, message=f"记忆查询失败: {e}")


@router.delete("/{memory_id}", summary="删除单条记忆")
async def delete_memory(
    memory_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """
    人工删除单条记忆（治理入口，用于清除错误/污染记忆）
    """
    try:
        deleted = await agent_memory_service.delete_memory(db, memory_id)
        if not deleted:
            raise BusinessException(code=404, message=f"记忆不存在或已删除: id={memory_id}")
        return success_response(message="删除成功")
    except BusinessException:
        raise
    except MemoryServiceError as e:
        logger.error(f"[记忆管理API] 删除失败: {e}")
        raise BusinessException(code=500, message=f"记忆删除失败: {e}")


@router.post("/purge-expired", summary="清理过期记忆")
async def purge_expired(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """
    清理全部已过期记忆（expires_at <= 当前时间的记录）

    可由管理端手动触发，也可供定时任务调用
    """
    try:
        deleted = await agent_memory_service.purge_expired(db)
        logger.info(f"[记忆管理API] 过期记忆清理完成: 操作人={user.id}, 删除{deleted}条")
        return success_response(data={"deleted": deleted}, message="过期记忆清理完成")
    except MemoryServiceError as e:
        logger.error(f"[记忆管理API] 过期清理失败: {e}")
        raise BusinessException(code=500, message=f"过期记忆清理失败: {e}")
