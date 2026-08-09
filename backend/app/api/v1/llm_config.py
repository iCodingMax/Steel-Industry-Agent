"""
大模型配置API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

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
    model_type: str = Query(None, description="模型类型过滤: llm/embedding/rerank"),
    provider_type: str = Query(None, description="供应商类型过滤: xinference/openai等"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取所有LLM配置（同时支持模型类型和供应商类型过滤）"""
    if model_type:
        if model_type not in ['llm', 'embedding', 'rerank']:
            model_type = None
    if model_type:
        configs = await llm_config_service.get_by_model_type(db, model_type)
    elif provider_type:
        configs = await llm_config_service.get_by_provider_type(db, provider_type)
    else:
        configs = await llm_config_service.get_all(db, skip, limit)
    return success_response(data=[c.to_dict() for c in configs])


@router.get("/default", summary="获取默认LLM配置")
async def get_default_llm_config(
    model_type: str = Query('llm', description="模型类型: llm/embedding/rerank"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取指定类型的默认LLM配置"""
    logger.debug(f"收到获取默认配置请求: model_type={model_type}, type={type(model_type)}")
    # 确保model_type是有效的值
    if model_type not in ['llm', 'embedding', 'rerank']:
        model_type = 'llm'
    config = await llm_config_service.get_default_by_model_type(db, model_type)
    if not config:
        return success_response(data=None, message="未设置默认配置")
    return success_response(data=config.to_dict())


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


@router.get("/default", summary="获取默认LLM配置")
async def get_default_llm_config(
    model_type: str = Query('llm', description="模型类型: llm/embedding/rerank"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取指定类型的默认LLM配置"""
    logger.debug(f"收到获取默认配置请求: model_type={model_type}, type={type(model_type)}")
    # 确保model_type是有效的值
    if model_type not in ['llm', 'embedding', 'rerank']:
        model_type = 'llm'
    config = await llm_config_service.get_default_by_model_type(db, model_type)
    if not config:
        return success_response(data=None, message="未设置默认配置")
    return success_response(data=config.to_dict())


@router.post("/test-connection", summary="测试LLM配置连接")
async def test_llm_connection(
    data: dict,
    user: User = Depends(get_current_user),
):
    """测试LLM配置连接"""
    logger.debug(f"测试连接请求体: {data}")
    result = await llm_config_service.test_connection(data)
    return success_response(data=result)
