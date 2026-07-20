"""
术语API
"""
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.term import TermCreate, TermUpdate, TermResponse
from app.services.term_service import term_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("", summary="获取术语列表")
async def list_terms(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    keyword: str = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取所有术语，或搜索术语"""
    if keyword:
        terms = await term_service.search(db, keyword)
    else:
        terms = await term_service.get_all(db, skip, limit)
    return success_response(data=[t.to_dict() for t in terms])


@router.get("/{term_id}", summary="获取术语详情")
async def get_term(
    term_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取术语"""
    term = await term_service.get_by_id(db, term_id)
    if not term:
        return success_response(data=None, message="术语不存在")
    return success_response(data=term.to_dict())


@router.post("", summary="创建术语")
async def create_term(
    data: TermCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新术语"""
    term = await term_service.create(db, data)
    return success_response(data=term.to_dict())


@router.put("/{term_id}", summary="更新术语")
async def update_term(
    term_id: int,
    data: TermUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新术语"""
    term = await term_service.update(db, term_id, data)
    if not term:
        return success_response(data=None, message="术语不存在")
    return success_response(data=term.to_dict())


@router.delete("/{term_id}", summary="删除术语")
async def delete_term(
    term_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除术语"""
    await term_service.delete(db, term_id)
    return success_response(message="删除成功")
