"""
维度API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.dimension import DimensionCreate, DimensionUpdate, DimensionResponse
from app.services.dimension_service import dimension_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("", summary="获取维度列表")
async def list_dimensions(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取所有维度"""
    dimensions = await dimension_service.get_all(db, skip, limit)
    return success_response(data=[d.to_dict() for d in dimensions])


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
    return success_response(data=dimension.to_dict())


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
