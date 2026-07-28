"""
数据源API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db_session
from app.schemas.datasource import (
    DataSourceCreate,
    DataSourceUpdate,
    DataSourceResponse,
    TestConnectionRequest,
    TableSchemaResponse,
)
from app.services.datasource_service import datasource_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User
from app.models.datasource import DataSource

router = APIRouter()


@router.get("", summary="获取数据源列表")
async def list_datasources(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取数据源列表，支持分页和搜索"""
    skip = (page - 1) * pageSize
    
    query = select(DataSource)
    count_query = select(func.count(DataSource.id))
    
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.where(DataSource.name.like(keyword_like) | DataSource.type.like(keyword_like))
        count_query = count_query.where(DataSource.name.like(keyword_like) | DataSource.type.like(keyword_like))
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    query = query.order_by(DataSource.id.desc()).offset(skip).limit(pageSize)
    result = await db.execute(query)
    datasources = list(result.scalars().all())
    
    return success_response(data={
        "total": total,
        "list": [ds.to_dict() for ds in datasources]
    })


@router.get("/{ds_id}", summary="获取数据源详情")
async def get_datasource(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取数据源"""
    ds = await datasource_service.get_by_id(db, ds_id)
    if not ds:
        return success_response(data=None, message="数据源不存在")
    return success_response(data=ds.to_dict(include_password=True))


@router.post("", summary="创建数据源")
async def create_datasource(
    data: DataSourceCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新数据源"""
    ds = await datasource_service.create(db, data, user.id)
    return success_response(data=ds.to_dict())


@router.put("/{ds_id}", summary="更新数据源")
async def update_datasource(
    ds_id: int,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新数据源"""
    ds = await datasource_service.update(db, ds_id, data)
    if not ds:
        return success_response(data=None, message="数据源不存在")
    return success_response(data=ds.to_dict())


@router.delete("/{ds_id}", summary="删除数据源")
async def delete_datasource(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除数据源"""
    await datasource_service.delete(db, ds_id)
    return success_response(message="删除成功")


@router.post("/test-connection", summary="测试连接")
async def test_connection(
    data: TestConnectionRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """测试数据库连接"""
    result = await datasource_service.test_connection(db, data)
    if result["success"]:
        return success_response(data=result)
    return success_response(data=result, message="连接失败")


@router.post("/{ds_id}/sync-schema", summary="同步表结构")
async def sync_schema(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """同步数据源表结构"""
    tables = await datasource_service.sync_schema(db, ds_id)
    return success_response(data=[t.to_dict() for t in tables])


@router.get("/{ds_id}/schema", summary="获取表结构")
async def get_schema(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取数据源表结构"""
    tables = await datasource_service.get_schema(db, ds_id)
    return success_response(data=[t.to_dict() for t in tables])
