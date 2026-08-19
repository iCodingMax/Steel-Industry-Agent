"""
JWT认证依赖

职责：为需要登录的路由提供统一的用户认证能力。
     路由只需声明 Depends(get_current_user) 即可自动完成鉴权。

依赖注入链（FastAPI Depends 机制）：
  HTTPBearer(auto_error=False)     → 从 Authorization 头提取 Bearer token
  ↓
  get_db_session()                 → 获取数据库会话（PostgreSQL）
  ↓
  decode_token(token)              → JWT 解码，提取 user_id
  ↓
  auth_service.get_user_by_id()    → 查库验证用户是否存在
  ↓
  返回 User 对象（注入到路由函数参数中）

auto_error=False 的原因：
  HTTPBearer 默认在缺少 token 时直接返回 403。
  设为 False 让我们自己控制错误响应格式（统一 {code, message, data}）。
"""
from fastapi import Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db_session
from app.utils.security import decode_token
from app.services.auth_service import auth_service
from app.middlewares.exception_handler import BusinessException

# HTTPBearer 安全方案：从 Authorization: Bearer <token> 头提取 token
# auto_error=False → 缺少 token 时不自动报错，由 get_current_user 手动处理
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session),
):
    """
    获取当前登录用户（FastAPI 依赖注入）

    使用方式：在路由函数参数中声明 user: User = Depends(get_current_user)
    FastAPI 会在请求到达路由前自动执行此函数，完成鉴权。

    四重校验：
      1. credentials 是否存在（Authorization 头是否携带 Bearer token）
      2. JWT 解码是否成功（token 是否有效且未过期）
      3. payload 中是否包含 user_id
      4. 用户在数据库中是否真实存在（防止已删除用户的 token 仍可用）
    """
    if not credentials:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="未提供认证令牌",
        )

    # 提取 JWT token 并解码
    token = credentials.credentials
    payload = decode_token(token)

    if not payload:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="令牌无效或已过期",
        )

    # 从 JWT payload 提取 user_id（签发 token 时写入）
    user_id = payload.get("user_id")
    if not user_id:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="令牌无效",
        )

    # 查库验证用户真实存在（防止 token 对应的用户已被删除）
    user = await auth_service.get_user_by_id(db, user_id)
    if not user:
        raise BusinessException(
            code=status.HTTP_401_UNAUTHORIZED,
            message="用户不存在",
        )

    # 验证通过，返回 User 对象注入到路由函数
    return user
