"""
认证API
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_mysql_session
from app.schemas.auth import LoginRequest, LoginResponse, ChangePasswordRequest, UserInfoResponse
from app.services.auth_service import auth_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.post("/login", summary="用户登录")
async def login(
    req: LoginRequest,
    db: AsyncSession = Depends(get_mysql_session),
):
    """用户登录"""
    result = await auth_service.login(db, req)
    return success_response(data={
        "token": result["token"],
        "expiresIn": result["expiresIn"],
    })


@router.get("/me", summary="获取当前用户信息")
async def get_current_user_info(
    user: User = Depends(get_current_user),
):
    """获取当前登录用户信息"""
    return success_response(data=user.to_dict())


@router.post("/change-password", summary="修改密码")
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_mysql_session),
):
    """修改当前用户密码"""
    await auth_service.change_password(db, user.id, req)
    return success_response(message="密码修改成功")


@router.post("/logout", summary="退出登录")
async def logout(
    user: User = Depends(get_current_user),
):
    """退出登录（前端清除token即可）"""
    return success_response(message="退出成功")
