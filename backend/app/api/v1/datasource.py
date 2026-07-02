"""
数据源API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
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

router = APIRouter()


@router.get("", summary="获取数据源列表")
async def list_datasources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取所有数据源"""
    datasources = await datasource_service.get_all(db, skip, limit)
    return success_response(data=[ds.to_dict() for ds in datasources])


@router.get("/{ds_id}", summary="获取数据源详情")
async def get_datasource(
    ds_id: int,
    db: AsyncSession = Depends(get_mysql_session),
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
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """创建新数据源"""
    ds = await datasource_service.create(db, data, user.id)
    return success_response(data=ds.to_dict())


@router.put("/{ds_id}", summary="更新数据源")
async def update_datasource(
    ds_id: int,
    data: DataSourceUpdate,
    db: AsyncSession = Depends(get_mysql_session),
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
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """删除数据源"""
    await datasource_service.delete(db, ds_id)
    return success_response(message="删除成功")


@router.post("/test-connection", summary="测试连接")
async def test_connection(
    data: TestConnectionRequest,
    db: AsyncSession = Depends(get_mysql_session),
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
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """同步数据源表结构"""
    tables = await datasource_service.sync_schema(db, ds_id)
    return success_response(data=[t.to_dict() for t in tables])


@router.get("/{ds_id}/schema", summary="获取表结构")
async def get_schema(
    ds_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取数据源表结构"""
    tables = await datasource_service.get_schema(db, ds_id)
    return success_response(data=[t.to_dict() for t in tables])
