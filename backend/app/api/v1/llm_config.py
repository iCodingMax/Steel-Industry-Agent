"""
大模型配置API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate, LLMConfigResponse
from app.services.llm_config_service import llm_config_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("", summary="获取LLM配置列表")
async def list_llm_configs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    config_type: str = Query(None, description="配置类型"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取所有LLM配置"""
    if config_type:
        configs = await llm_config_service.get_by_type(db, config_type)
    else:
        configs = await llm_config_service.get_all(db, skip, limit)
    return success_response(data=[c.to_dict() for c in configs])


@router.get("/{config_id}", summary="获取LLM配置详情")
async def get_llm_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取配置"""
    config = await llm_config_service.get_by_id(db, config_id)
    if not config:
        return success_response(data=None, message="配置不存在")
    return success_response(data=config.to_dict(include_secret=True))


@router.post("", summary="创建LLM配置")
async def create_llm_config(
    data: LLMConfigCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新LLM配置"""
    config = await llm_config_service.create(db, data)
    return success_response(data=config.to_dict())


@router.put("/{config_id}", summary="更新LLM配置")
async def update_llm_config(
    config_id: int,
    data: LLMConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新LLM配置"""
    config = await llm_config_service.update(db, config_id, data)
    if not config:
        return success_response(data=None, message="配置不存在")
    return success_response(data=config.to_dict())


@router.delete("/{config_id}", summary="删除LLM配置")
async def delete_llm_config(
    config_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除LLM配置"""
    await llm_config_service.delete(db, config_id)
    return success_response(message="删除成功")


@router.post("/test-connection", summary="测试LLM配置连接")
async def test_llm_connection(
    data: dict,
    user: User = Depends(get_current_user),
):
    """测试LLM配置连接"""
    result = await llm_config_service.test_connection(data)
    return success_response(data=result)
