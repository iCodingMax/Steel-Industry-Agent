"""
用户管理API
提供系统用户的CRUD管理接口
仅管理员可访问

主要接口：
1. GET /users - 获取用户列表（分页、搜索）
2. POST /users - 创建用户
3. GET /users/{id} - 获取用户详情
4. PUT /users/{id} - 更新用户信息
5. DELETE /users/{id} - 删除用户
6. PUT /users/{id}/reset-password - 重置用户密码
7. PUT /users/{id}/toggle-status - 启用/禁用用户
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.user import UserCreate, UserUpdate, PasswordReset
from app.services.user_service import user_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("", summary="获取用户列表")
async def list_users(
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=100, description="每页条数"),
    keyword: Optional[str] = Query(None, description="搜索关键词（用户名/姓名/邮箱）"),
    status: Optional[str] = Query(None, description="状态筛选: active/disabled"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """获取用户列表，支持分页、搜索和状态筛选"""
    users, total = await user_service.list_users(
        db=db,
        page=page,
        page_size=pageSize,
        keyword=keyword,
        status=status,
    )
    
    user_list = [u.to_dict() for u in users]
    return success_response(data={
        "total": total,
        "list": user_list,
    })


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """根据ID获取用户详情"""
    user = await user_service.get_by_id(db, user_id)
    if not user:
        return success_response(data=None, message="用户不存在")
    return success_response(data=user.to_dict())


@router.post("", summary="创建用户")
async def create_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """创建新用户"""
    user = await user_service.create(db, data)
    return success_response(data=user.to_dict())


@router.put("/{user_id}", summary="更新用户信息")
async def update_user(
    user_id: int,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """更新用户基本信息"""
    user = await user_service.update(db, user_id, data)
    if not user:
        return success_response(data=None, message="用户不存在")
    return success_response(data=user.to_dict())


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """删除用户（不能删除自己和admin账号）"""
    await user_service.delete(db, user_id, current_user.id)
    return success_response(message="删除成功")


@router.put("/{user_id}/reset-password", summary="重置用户密码")
async def reset_user_password(
    user_id: int,
    data: PasswordReset,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """重置指定用户的密码"""
    await user_service.reset_password(db, user_id, data.password)
    return success_response(message="密码重置成功")


@router.put("/{user_id}/toggle-status", summary="启用/禁用用户")
async def toggle_user_status(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """切换用户状态（启用/禁用）"""
    user = await user_service.toggle_status(db, user_id)
    if not user:
        return success_response(data=None, message="用户不存在")
    return success_response(data=user.to_dict())
