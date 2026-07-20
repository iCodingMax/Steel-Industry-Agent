"""
JWT认证依赖
"""
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db_session
from app.utils.security import decode_token
from app.services.auth_service import auth_service
from app.middlewares.exception_handler import BusinessException

security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
):
    """获取当前登录用户"""
    if not credentials:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="未提供认证令牌",
        )

    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="令牌无效或已过期",
        )

    user_id = payload.get("user_id")
    if not user_id:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="令牌无效",
        )

    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="用户不存在",
        )

    return user
