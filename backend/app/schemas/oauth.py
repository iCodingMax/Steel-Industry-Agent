"""
OAuth2配置相关Schema
"""
from typing import Optional, Dict, Literal
from pydantic import BaseModel, Field


class OAuthConfigUpdate(BaseModel):
    """更新OAuth2配置请求"""
    configType: Literal["system", "chat"] = Field(default="system", description="配置类型: system/chat")
    authorizationUrl: str = Field(..., description="授权端地址")
    tokenUrl: str = Field(..., description="Token端地址")
    userInfoUrl: str = Field(..., description="用户信息端地址")
    scope: str = Field(..., description="连接范围")
    clientId: str = Field(..., description="客户端ID")
    clientSecret: str = Field(..., description="客户端密钥")
    fieldMapping: Optional[Dict] = Field(None, description="字段映射")
    redirectUrl: str = Field(..., description="回调地址")
    enabled: bool = Field(default=False, description="是否启用")


class OAuthConfigResponse(BaseModel):
    """OAuth2配置响应"""
    id: int
    configType: str = "system"
    authorizationUrl: str
    tokenUrl: str
    userInfoUrl: str
    scope: str
    clientId: str
    clientSecret: str
    fieldMapping: Optional[Dict] = None
    redirectUrl: str
    enabled: bool
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class OAuthLoginResponse(BaseModel):
    """OAuth2登录响应"""
    token: str
    expiresIn: int
    user: dict
