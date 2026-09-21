"""
示例SQL库API（NL2SQL 升级二期：Few-shot 手工示例库，参考 SQLBot）

路由前缀由 api_router 统一挂载为 /datasources，本路由内路径为 /{ds_id}/sql-examples...
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.sql_example import (
    SqlExampleCreate,
    SqlExampleUpdate,
    SqlExampleStatusUpdate,
)
from app.services.sql_example_service import sql_example_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/sql-examples", summary="获取全部示例SQL列表（跨数据源）")
async def list_all_sql_examples(
    status: Optional[str] = Query(None, description="状态过滤: active/retired"),
    keyword: Optional[str] = Query(None, description="关键词（问题/SQL/备注）"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """分页查询全部数据源的示例SQL列表，支持状态/关键词过滤"""
    result = await sql_example_service.list_examples(
        db, None, status=status, keyword=keyword, page=page, page_size=pageSize
    )
    return success_response(data=result)


@router.get("/{ds_id}/sql-examples", summary="获取示例SQL列表")
async def list_sql_examples(
    ds_id: int,
    status: Optional[str] = Query(None, description="状态过滤: active/retired"),
    keyword: Optional[str] = Query(None, description="关键词（问题/SQL/备注）"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """分页查询示例SQL列表，支持状态/关键词过滤"""
    result = await sql_example_service.list_examples(
        db, ds_id, status=status, keyword=keyword, page=page, page_size=pageSize
    )
    return success_response(data=result)


@router.post("/{ds_id}/sql-examples", summary="新增示例SQL")
async def create_sql_example(
    ds_id: int,
    data: SqlExampleCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """新增手工示例（保存前防污染校验：只读白名单+语法校验；保存后向量化）"""
    example = await sql_example_service.create_example(
        db, ds_id, data.model_dump(), user_id=user.id
    )
    return success_response(data=example.to_dict(), message="示例SQL创建成功")


@router.put("/{ds_id}/sql-examples/{example_id}", summary="编辑示例SQL")
async def update_sql_example(
    ds_id: int,
    example_id: int,
    data: SqlExampleUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """编辑示例（仅 manual 来源；问题变更时重新向量化，SQL 变更时重新校验）"""
    example = await sql_example_service.update_example(
        db, ds_id, example_id, data.model_dump(exclude_unset=True)
    )
    return success_response(data=example.to_dict(), message="示例SQL更新成功")


@router.put("/{ds_id}/sql-examples/{example_id}/status", summary="启用/停用示例SQL")
async def update_sql_example_status(
    ds_id: int,
    example_id: int,
    data: SqlExampleStatusUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """切换示例启用状态（active/retired）"""
    example = await sql_example_service.update_status(db, ds_id, example_id, data.status)
    return success_response(data=example.to_dict(), message="状态更新成功")


@router.delete("/{ds_id}/sql-examples/{example_id}", summary="删除示例SQL")
async def delete_sql_example(
    ds_id: int,
    example_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除示例SQL"""
    await sql_example_service.delete_example(db, ds_id, example_id)
    return success_response(message="示例SQL删除成功")


@router.post("/{ds_id}/sql-examples/{example_id}/dry-run", summary="试跑示例SQL")
async def dry_run_sql_example(
    ds_id: int,
    example_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """只读执行一次示例SQL，返回行数与首行预览（录入者确认结果符合预期后启用）"""
    result = await sql_example_service.dry_run(db, ds_id, example_id)
    return success_response(data=result)
