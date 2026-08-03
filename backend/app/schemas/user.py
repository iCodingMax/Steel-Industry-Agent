"""
用户管理相关Schema
定义用户创建、更新、密码重置等请求和响应模型
"""
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class UserCreate(BaseModel):
    """创建用户请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名（3-50位）")
    password: str = Field(..., min_length=6, max_length=50, description="密码（6-50位）")
    name: Optional[str] = Field(None, max_length=50, description="姓名")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    role: str = Field(default="user", description="角色: admin/user")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v:
            if "@" not in v:
                raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v:
            if not v.isdigit():
                raise ValueError("手机号只能包含数字")
        return v


class UserUpdate(BaseModel):
    """更新用户请求"""
    name: Optional[str] = Field(None, max_length=50, description="姓名")
    email: Optional[str] = Field(None, max_length=100, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    role: Optional[str] = Field(None, description="角色: admin/user")
    status: Optional[str] = Field(None, description="状态: active/disabled")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v:
            if "@" not in v:
                raise ValueError("邮箱格式不正确")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v:
            if not v.isdigit():
                raise ValueError("手机号只能包含数字")
        return v


class PasswordReset(BaseModel):
    """重置用户密码请求"""
    password: str = Field(..., min_length=6, max_length=50, description="新密码（6-50位）")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: str
    status: str
    oauth_provider: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_login_at: Optional[str] = None


class UserListResponse(BaseModel):
    """用户列表响应"""
    total: int
    list: list[UserResponse]
