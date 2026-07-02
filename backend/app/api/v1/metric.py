"""
指标API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.schemas.metric import MetricCreate, MetricUpdate, MetricResponse
from app.services.metric_service import metric_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("", summary="获取指标列表")
async def list_metrics(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取所有指标"""
    metrics = await metric_service.get_all(db, skip, limit)
    return success_response(data=[m.to_dict() for m in metrics])


@router.get("/{metric_id}", summary="获取指标详情")
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取指标"""
    metric = await metric_service.get_by_id(db, metric_id)
    if not metric:
        return success_response(data=None, message="指标不存在")
    return success_response(data=metric.to_dict())


@router.post("", summary="创建指标")
async def create_metric(
    data: MetricCreate,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """创建新指标"""
    metric = await metric_service.create(db, data)
    return success_response(data=metric.to_dict())


@router.put("/{metric_id}", summary="更新指标")
async def update_metric(
    metric_id: int,
    data: MetricUpdate,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """更新指标"""
    metric = await metric_service.update(db, metric_id, data)
    if not metric:
        return success_response(data=None, message="指标不存在")
    return success_response(data=metric.to_dict())


@router.delete("/{metric_id}", summary="删除指标")
async def delete_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """删除指标"""
    await metric_service.delete(db, metric_id)
    return success_response(message="删除成功")
