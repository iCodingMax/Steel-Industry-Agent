"""
术语API
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_db_session
from app.schemas.term import TermCreate, TermUpdate, TermResponse
from app.services.term_service import term_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User
from app.models.term import Term
from app.models.datasource import DataSource

router = APIRouter()


@router.get("", summary="获取术语列表")
async def list_terms(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页条数"),
    datasourceId: Optional[int] = Query(None, description="数据源ID筛选"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取术语列表，支持分页和筛选"""
    skip = (page - 1) * pageSize
    
    # 构建查询
    query = select(Term)
    count_query = select(func.count(Term.id))
    
    # 数据源筛选
    if datasourceId:
        query = query.where(Term.datasource_id == datasourceId)
        count_query = count_query.where(Term.datasource_id == datasourceId)
    
    # 关键词搜索
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.where(or_(
            Term.term.like(keyword_like),
            Term.code.like(keyword_like),
            Term.definition.like(keyword_like)
        ))
        count_query = count_query.where(or_(
            Term.term.like(keyword_like),
            Term.code.like(keyword_like),
            Term.definition.like(keyword_like)
        ))
    
    # 获取总数
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    # 分页查询
    query = query.order_by(Term.id.desc()).offset(skip).limit(pageSize)
    result = await db.execute(query)
    terms = list(result.scalars().all())
    
    # 转换为字典，包含数据源名称
    term_list = []
    for t in terms:
        t_dict = t.to_dict()
        # 获取数据源名称
        if t.datasource_id:
            ds_result = await db.execute(select(DataSource).where(DataSource.id == t.datasource_id))
            ds = ds_result.scalar_one_or_none()
            if ds:
                t_dict['datasourceName'] = ds.name
        term_list.append(t_dict)
    
    return success_response(data={
        "total": total,
        "list": term_list
    })


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
    t_dict = term.to_dict()
    # 获取数据源名称
    if term.datasource_id:
        ds_result = await db.execute(select(DataSource).where(DataSource.id == term.datasource_id))
        ds = ds_result.scalar_one_or_none()
        if ds:
            t_dict['datasourceName'] = ds.name
    return success_response(data=t_dict)


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
