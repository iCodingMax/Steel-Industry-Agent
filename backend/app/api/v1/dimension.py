"""
维度API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db_session
from app.schemas.dimension import DimensionCreate, DimensionUpdate, DimensionResponse
from app.services.dimension_service import dimension_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User
from app.models.dimension import Dimension
from app.models.datasource import DataSource

router = APIRouter()


@router.get("", summary="获取维度列表")
async def list_dimensions(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页条数"),
    datasourceId: Optional[int] = Query(None, description="数据源ID筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取维度列表，支持分页和筛选"""
    skip = (page - 1) * pageSize
    
    # 构建查询
    query = select(Dimension)
    count_query = select(func.count(Dimension.id))
    
    # 数据源筛选
    if datasourceId:
        query = query.where(Dimension.datasource_id == datasourceId)
        count_query = count_query.where(Dimension.datasource_id == datasourceId)
    
    # 关键词搜索
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.where(Dimension.name.like(keyword_like) | Dimension.code.like(keyword_like))
        count_query = count_query.where(Dimension.name.like(keyword_like) | Dimension.code.like(keyword_like))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    query = query.order_by(Dimension.id.desc()).offset(skip).limit(pageSize)
    result = await db.execute(query)
    dimensions = list(result.scalars().all())
    
    # 转换为字典，包含数据源名称
    dimension_list = []
    for d in dimensions:
        d_dict = d.to_dict()
        # 获取数据源名称
        if d.datasource_id:
            ds_result = await db.execute(select(DataSource).where(DataSource.id == d.datasource_id))
            ds = ds_result.scalar_one_or_none()
            if ds:
                d_dict['datasourceName'] = ds.name
        dimension_list.append(d_dict)
    
    return success_response(data={
        "total": total,
        "list": dimension_list
    })


@router.get("/{dimension_id}", summary="获取维度详情")
async def get_dimension(
    dimension_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取维度"""
    dimension = await dimension_service.get_by_id(db, dimension_id)
    if not dimension:
        return success_response(data=None, message="维度不存在")
    d_dict = dimension.to_dict()
    # 获取数据源名称
    if dimension.datasource_id:
        ds_result = await db.execute(select(DataSource).where(DataSource.id == dimension.datasource_id))
        ds = ds_result.scalar_one_or_none()
        if ds:
            d_dict['datasourceName'] = ds.name
    return success_response(data=d_dict)


@router.post("", summary="创建维度")
async def create_dimension(
    data: DimensionCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新维度"""
    dimension = await dimension_service.create(db, data)
    return success_response(data=dimension.to_dict())


@router.put("/{dimension_id}", summary="更新维度")
async def update_dimension(
    dimension_id: int,
    data: DimensionUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新维度"""
    dimension = await dimension_service.update(db, dimension_id, data)
    if not dimension:
        return success_response(data=None, message="维度不存在")
    return success_response(data=dimension.to_dict())


@router.delete("/{dimension_id}", summary="删除维度")
async def delete_dimension(
    dimension_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除维度"""
    await dimension_service.delete(db, dimension_id)
    return success_response(message="删除成功")
