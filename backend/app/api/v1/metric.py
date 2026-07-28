"""
指标API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db_session
from app.schemas.metric import MetricCreate, MetricUpdate, MetricResponse
from app.services.metric_service import metric_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User
from app.models.metric import Metric
from app.models.datasource import DataSource

router = APIRouter()


@router.get("", summary="获取指标列表")
async def list_metrics(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页条数"),
    datasourceId: Optional[int] = Query(None, description="数据源ID筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取指标列表，支持分页和筛选"""
    skip = (page - 1) * pageSize
    
    # 构建查询
    query = select(Metric)
    count_query = select(func.count(Metric.id))
    
    # 数据源筛选
    if datasourceId:
        query = query.where(Metric.datasource_id == datasourceId)
        count_query = count_query.where(Metric.datasource_id == datasourceId)
    
    # 关键词搜索
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.where(Metric.name.like(keyword_like) | Metric.code.like(keyword_like))
        count_query = count_query.where(Metric.name.like(keyword_like) | Metric.code.like(keyword_like))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    query = query.order_by(Metric.id.desc()).offset(skip).limit(pageSize)
    result = await db.execute(query)
    metrics = list(result.scalars().all())
    
    # 转换为字典，包含数据源名称
    metric_list = []
    for m in metrics:
        m_dict = m.to_dict()
        # 获取数据源名称
        if m.datasource_id:
            ds_result = await db.execute(select(DataSource).where(DataSource.id == m.datasource_id))
            ds = ds_result.scalar_one_or_none()
            if ds:
                m_dict['datasourceName'] = ds.name
        metric_list.append(m_dict)
    
    return success_response(data={
        "total": total,
        "list": metric_list
    })


@router.get("/{metric_id}", summary="获取指标详情")
async def get_metric(
    metric_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取指标"""
    metric = await metric_service.get_by_id(db, metric_id)
    if not metric:
        return success_response(data=None, message="指标不存在")
    metric_dict = metric.to_dict()
    # 获取数据源名称
    if metric.datasource_id:
        ds_result = await db.execute(select(DataSource).where(DataSource.id == metric.datasource_id))
        ds = ds_result.scalar_one_or_none()
        if ds:
            metric_dict['datasourceName'] = ds.name
    return success_response(data=metric_dict)


@router.post("", summary="创建指标")
async def create_metric(
    data: MetricCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新指标"""
    metric = await metric_service.create(db, data)
    return success_response(data=metric.to_dict())


@router.put("/{metric_id}", summary="更新指标")
async def update_metric(
    metric_id: int,
    data: MetricUpdate,
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除指标"""
    await metric_service.delete(db, metric_id)
    return success_response(message="删除成功")
