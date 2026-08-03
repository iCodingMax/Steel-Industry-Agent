"""
对话用户 Schema 模块
定义对话用户相关的请求和响应模型
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


class ChatUserCreate(BaseModel):
    """创建对话用户请求"""
    username: str = Field(description="用户名", min_length=1, max_length=50)
    name: Optional[str] = Field(default=None, description="姓名")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, description="手机号")
    status: str = Field(default="active", description="状态: active/disabled")

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("用户名不能为空")
        return v.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("active", "disabled"):
            raise ValueError("状态必须是 active 或 disabled")
        return v


class ChatUserUpdate(BaseModel):
    """更新对话用户请求"""
    name: Optional[str] = Field(default=None, description="姓名")
    email: Optional[str] = Field(default=None, description="邮箱")
    phone: Optional[str] = Field(default=None, description="手机号")
    status: Optional[str] = Field(default=None, description="状态: active/disabled")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("active", "disabled"):
            raise ValueError("状态必须是 active 或 disabled")
        return v


class ChatUserResponse(BaseModel):
    """对话用户响应"""
    id: int
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: str
    userSource: str
    lastLoginAt: Optional[datetime] = None
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class ChatUserListResponse(BaseModel):
    """对话用户列表响应"""
    total: int
    items: List[ChatUserResponse]


class ChatUserQuery(BaseModel):
    """对话用户查询参数"""
    keyword: Optional[str] = Field(default=None, description="关键词搜索（用户名/姓名/邮箱）")
    status: Optional[str] = Field(default=None, description="状态筛选")
    page: int = Field(default=1, ge=1, description="页码")
    pageSize: int = Field(default=20, ge=1, le=100, description="每页数量")
