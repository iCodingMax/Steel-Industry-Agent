"""
对话用户认证 API 路由
提供对话用户登录和认证相关接口

主要接口：
1. POST /chat-auth/login - 对话用户账号密码登录
2. GET /chat-auth/oauth-config - 获取对话OAuth2配置（公开）

说明：对话用户与系统用户隔离，账号密码登录仅验证 chat_users 表。
"""
from datetime import timedelta
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db_session
from app.models.chat_user import ChatUser
from app.services.oauth_service import oauth_service, CONFIG_TYPE_CHAT
from app.utils.security import verify_password, create_access_token, hash_password
from app.core.config import settings
from app.middlewares.exception_handler import success_response, BusinessException

router = APIRouter(prefix="/chat-auth", tags=["对话用户认证"])


class ChatLoginRequest(BaseModel):
    """对话用户登录请求"""
    username: str
    password: str


@router.post("/login", summary="对话用户账号密码登录")
async def chat_user_login(
    data: ChatLoginRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    对话用户账号密码登录
    
    仅在 chat_users 表验证用户，与系统用户表（users）隔离。
    支持两种情况：
    1. 用户存在且已设置密码（password_hash非空），直接验证密码
    2. 用户存在但未设置密码（OAuth首次登录后首次账号登录），自动设置新密码
    
    若用户不存在则拒绝登录。
    """
    from sqlalchemy import select
    from datetime import datetime
    
    # 查找对话用户
    stmt = select(ChatUser).where(ChatUser.username == data.username)
    result = await db.execute(stmt)
    chat_user = result.scalar_one_or_none()
    
    if not chat_user:
        raise BusinessException(code=401, message="用户名或密码错误")
    
    # 检查对话用户状态
    if chat_user.status != "active":
        raise BusinessException(code=401, message="用户已被禁用，请联系管理员")
    
    # 验证或设置密码
    if chat_user.password_hash:
        # 已有密码，验证密码
        if not verify_password(data.password, chat_user.password_hash):
            raise BusinessException(code=401, message="用户名或密码错误")
    else:
        # 首次账号密码登录（通常是OAuth同步的用户），自动设置密码
        chat_user.password_hash = hash_password(data.password)
        chat_user.force_change_password = False
        logger.info(f"对话用户首次账号登录，设置密码: {data.username}")
    
    # 更新登录信息
    chat_user.last_login_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(chat_user)
    
    # 生成对话用户令牌
    token = create_access_token(
        data={
            "sub": chat_user.username,
            "chat_user_id": chat_user.id,
            "type": "chat",
        },
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    
    return success_response(data={
        "token": token,
        "expiresIn": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user": chat_user.to_dict(),
    })


@router.get("/oauth-config", summary="获取对话OAuth2配置")
async def get_chat_oauth_config(
    db: AsyncSession = Depends(get_db_session),
):
    """
    获取对话用户OAuth2配置（公开接口）
    用于应用登录页面判断OAuth是否启用
    """
    config = await oauth_service.get_config(db, CONFIG_TYPE_CHAT)
    if config:
        return success_response(data=config.to_dict())
    return success_response(data={
        "configType": "chat",
        "enabled": False,
        "clientId": None,
        "redirectUrl": None,
        "authorizationUrl": None,
        "tokenUrl": None,
        "userInfoUrl": None,
        "scope": None,
        "fieldMapping": {},
    })
