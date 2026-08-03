"""
OAuth2认证API
提供OAuth2配置管理和认证回调接口

主要接口：
1. GET /oauth/config?config_type=system - 获取OAuth2配置
2. POST /oauth/config - 保存OAuth2配置
3. GET /oauth/login-url - 获取系统OAuth2授权URL
4. POST /oauth/callback - 系统OAuth2回调处理
5. GET /oauth/chat-login-url - 获取对话用户OAuth2授权URL
6. POST /oauth/chat-callback - 对话用户OAuth2回调处理
"""
import json
import uuid
from typing import Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, Body, Query
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db_session
from app.schemas.oauth import OAuthConfigUpdate
from app.services.oauth_service import oauth_service, CONFIG_TYPE_SYSTEM, CONFIG_TYPE_CHAT
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


class OAuthCallbackRequest(BaseModel):
    """OAuth回调请求体"""
    code: str
    state: Optional[str] = None


# ==================== 系统用户OAuth2配置接口 ====================

@router.get("/config", summary="获取系统OAuth2配置")
async def get_system_oauth_config(
    config_type: str = Query(default="system", description="配置类型: system/chat"),
    db: AsyncSession = Depends(get_db_session),
):
    """获取OAuth2配置（公开接口，用于判断是否启用OAuth2登录）"""
    config = await oauth_service.get_config(db, config_type)
    if config:
        return success_response(data=config.to_dict())
    return success_response(data={
        "configType": config_type,
        "enabled": False,
        "clientId": None,
        "clientSecret": None,
        "redirectUrl": None,
        "authorizationUrl": None,
        "tokenUrl": None,
        "userInfoUrl": None,
        "scope": None,
        "fieldMapping": {},
    })


@router.post("/config", summary="保存OAuth2配置")
async def save_oauth_config(
    data: OAuthConfigUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """保存OAuth2配置（管理员权限）"""
    config = await oauth_service.save_config(db, data)
    return success_response(data=config.to_dict(), message="OAuth2配置保存成功")


# ==================== 系统用户OAuth2登录接口 ====================

@router.get("/login-url", summary="获取系统OAuth2授权URL")
async def get_login_url(
    db: AsyncSession = Depends(get_db_session),
):
    """获取系统OAuth2授权URL，用于前端跳转"""
    config = await oauth_service.get_config(db, CONFIG_TYPE_SYSTEM)
    if not config or not config.enabled:
        raise BusinessException(code=400, message="系统OAuth2认证未启用")
    
    # 生成state参数防止CSRF
    state = str(uuid.uuid4())
    
    # 构建授权URL
    url = oauth_service.build_authorization_url(config, state)
    
    return success_response(data={
        "loginUrl": url,
        "state": state,
    })


@router.post("/callback", summary="系统OAuth2回调处理")
async def oauth_callback(
    req: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    系统OAuth2回调处理
    流程：
    1. 用code换取access_token
    2. 用access_token获取用户信息
    3. 根据字段映射转换用户信息
    4. 登录或创建本地系统用户
    5. 返回平台JWT令牌
    """
    config = await oauth_service.get_config(db, CONFIG_TYPE_SYSTEM)
    if not config or not config.enabled:
        raise BusinessException(code=400, message="系统OAuth2认证未启用")
    
    # 1. 用code换取access_token
    access_token = await oauth_service.exchange_code_for_token(config, req.code)
    if not access_token:
        raise BusinessException(code=400, message="获取访问令牌失败")
    
    # 2. 用access_token获取用户信息
    oauth_user_info = await oauth_service.get_user_info(config, access_token)
    if not oauth_user_info:
        raise BusinessException(code=400, message="获取用户信息失败")
    
    # 3. 根据字段映射转换用户信息
    mapped_user_info = oauth_service.map_user_fields(oauth_user_info, config)
    
    # 4. 登录或创建本地系统用户
    user = await oauth_service.login_or_create_user(db, mapped_user_info, config)
    if not user:
        raise BusinessException(code=400, message="用户登录失败")
    
    # 5. 生成平台JWT令牌
    token_data = oauth_service.generate_platform_token(user)
    
    return success_response(data={
        "token": token_data["token"],
        "expiresIn": token_data["expiresIn"],
        "user": user.to_dict(),
    })


# ==================== 对话用户OAuth2登录接口 ====================

@router.get("/chat-login-url", summary="获取对话用户OAuth2授权URL")
async def get_chat_login_url(
    db: AsyncSession = Depends(get_db_session),
):
    """获取对话用户OAuth2授权URL，用于应用集成"""
    config = await oauth_service.get_config(db, CONFIG_TYPE_CHAT)
    if not config or not config.enabled:
        raise BusinessException(code=400, message="对话用户OAuth2认证未启用")
    
    # 生成state参数防止CSRF
    state = str(uuid.uuid4())
    
    # 构建授权URL
    url = oauth_service.build_authorization_url(config, state)
    
    return success_response(data={
        "loginUrl": url,
        "state": state,
    })


@router.post("/chat-callback", summary="对话用户OAuth2回调处理")
async def chat_oauth_callback(
    req: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """
    对话用户OAuth2回调处理
    流程：
    1. 用code换取access_token
    2. 用access_token获取用户信息
    3. 根据字段映射转换用户信息
    4. 登录或创建本地对话用户
    5. 返回对话用户令牌
    
    注意：对话用户与系统用户隔离，OAuth登录只在chat_users表创建记录，
    不在users表创建系统用户。
    """
    config = await oauth_service.get_config(db, CONFIG_TYPE_CHAT)
    if not config or not config.enabled:
        raise BusinessException(code=400, message="对话用户OAuth2认证未启用")
    
    # 1. 用code换取access_token
    access_token = await oauth_service.exchange_code_for_token(config, req.code)
    if not access_token:
        raise BusinessException(code=400, message="获取访问令牌失败")
    
    # 2. 用access_token获取用户信息
    oauth_user_info = await oauth_service.get_user_info(config, access_token)
    if not oauth_user_info:
        raise BusinessException(code=400, message="获取用户信息失败")
    
    # 3. 根据字段映射转换用户信息
    mapped_user_info = oauth_service.map_user_fields(oauth_user_info, config)
    
    # 4. 登录或创建本地对话用户（仅在chat_users表操作，不创建系统用户）
    chat_user = await oauth_service.chat_login_or_create_user(db, mapped_user_info, config)
    if not chat_user:
        raise BusinessException(code=400, message="用户登录失败")
    
    # 5. 生成对话用户令牌
    token_data = oauth_service.generate_chat_token(chat_user)
    
    return success_response(data={
        "token": token_data["token"],
        "expiresIn": token_data["expiresIn"],
        "user": chat_user.to_dict(),
    })
