"""
认证相关Schema
"""
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class LoginResponse(BaseModel):
    """登录响应"""
    token: str = Field(..., description="访问令牌")
    expiresIn: int = Field(..., description="过期时间(秒)")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    oldPassword: str = Field(..., description="原密码")
    newPassword: str = Field(..., description="新密码", min_length=6)


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    name: Optional[str] = Field(None, description="姓名")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    role: str = Field(..., description="角色")
    status: Optional[str] = Field("active", description="状态")
    createdAt: Optional[str] = Field(None, description="创建时间")
    updatedAt: Optional[str] = Field(None, description="更新时间")
    lastLoginAt: Optional[str] = Field(None, description="最后登录时间")
    forceChangePassword: bool = Field(True, description="是否强制改密")
