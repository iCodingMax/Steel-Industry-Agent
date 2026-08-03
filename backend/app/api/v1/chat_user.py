"""
对话用户 API 路由
提供对话用户管理的RESTful接口

主要接口：
1. GET /chat-users - 获取对话用户列表
2. POST /chat-users - 创建对话用户
3. GET /chat-users/{id} - 获取对话用户详情
4. PUT /chat-users/{id} - 更新对话用户
5. DELETE /chat-users/{id} - 删除对话用户
6. PATCH /chat-users/{id}/toggle-status - 切换用户状态
7. POST /chat-users/{id}/reset-password - 重置密码
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.chat_user import ChatUserCreate, ChatUserUpdate, ChatUserQuery
from app.services.chat_user_service import chat_user_service
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/chat-users", tags=["对话用户"])


class ResetPasswordRequest(BaseModel):
    """重置密码请求"""
    newPassword: str = "123456"


@router.get("", summary="获取对话用户列表")
async def list_chat_users(
    keyword: str = Query(default=None, description="关键词搜索"),
    status: str = Query(default=None, description="状态筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取对话用户列表
    
    支持按关键词搜索和状态筛选，分页返回
    """
    query = ChatUserQuery(
        keyword=keyword,
        status=status,
        page=page,
        pageSize=page_size,
    )
    
    total, users = await chat_user_service.list_users(db, query)
    
    user_list = [user.to_dict() for user in users]
    
    return success_response(data={
        "total": total,
        "items": user_list,
    })


@router.post("", summary="创建对话用户")
async def create_chat_user(
    data: ChatUserCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    创建对话用户
    
    管理员手动创建对话用户，用于对话记录隔离
    默认密码为123456
    """
    try:
        user = await chat_user_service.create_user(db, data)
        return success_response(data=user.to_dict(), message="创建成功，默认密码：123456")
    except ValueError as e:
        raise BusinessException(code=400, message=str(e))


@router.get("/{user_id}", summary="获取对话用户详情")
async def get_chat_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    获取对话用户详情
    """
    user = await chat_user_service.get_user_by_id(db, user_id)
    if not user:
        raise BusinessException(code=404, message="用户不存在")
    
    return success_response(data=user.to_dict())


@router.put("/{user_id}", summary="更新对话用户")
async def update_chat_user(
    user_id: int,
    data: ChatUserUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    更新对话用户信息
    """
    try:
        user = await chat_user_service.update_user(db, user_id, data)
        if not user:
            raise BusinessException(code=404, message="用户不存在")
        return success_response(data=user.to_dict(), message="更新成功")
    except ValueError as e:
        raise BusinessException(code=400, message=str(e))


@router.delete("/{user_id}", summary="删除对话用户")
async def delete_chat_user(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    删除对话用户
    """
    success = await chat_user_service.delete_user(db, user_id)
    if not success:
        raise BusinessException(code=404, message="用户不存在")
    
    return success_response(message="删除成功")


@router.patch("/{user_id}/toggle-status", summary="切换用户状态")
async def toggle_chat_user_status(
    user_id: int,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    切换对话用户启用/禁用状态
    """
    user = await chat_user_service.toggle_status(db, user_id)
    if not user:
        raise BusinessException(code=404, message="用户不存在")
    
    return success_response(data=user.to_dict(), message="状态切换成功")


@router.post("/{user_id}/reset-password", summary="重置对话用户密码")
async def reset_chat_user_password(
    user_id: int,
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    重置对话用户密码
    
    默认重置为123456
    """
    success = await chat_user_service.reset_password(db, user_id, data.newPassword)
    if not success:
        raise BusinessException(code=404, message="用户不存在")
    
    msg = "密码已重置为：123456" if data.newPassword == "123456" else "密码修改成功"
    return success_response(message=msg)
