"""
对话用户模型模块
定义对话用户的数据模型

对话用户：
- 应用发布后与业务系统集成的对话用户
- 用户访问问答应用后能实现对话记录隔离
- 与业务系统通过统一身份认证中心账号信息同步
- 支持单点登录功能

用户来源：
- OAuth2: 从统一认证中心同步
- 本地创建: 管理员手动创建
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from app.core.base_model import Base


class ChatUser(Base):
    """
    对话用户表
    存储对话用户信息，用于对话记录隔离
    
    特性：
    - 每个对话用户有唯一标识，实现对话记录隔离
    - 支持从OAuth2统一认证中心同步用户信息
    - 支持本地创建对话用户
    """

    __tablename__ = "chat_users"

    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    name = Column(String(50), nullable=True, comment="姓名")
    email = Column(String(100), nullable=True, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    password_hash = Column(String(255), nullable=True, comment="密码哈希（用于账号密码登录）")
    status = Column(String(20), default="active", comment="状态: active/disabled")
    user_source = Column(String(20), default="local", comment="用户来源: oauth2/local")
    force_change_password = Column(Boolean, default=False, comment="是否强制改密（OAuth首次登录后设置密码）")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "status": self.status,
            "userSource": self.user_source,
            "forceChangePassword": self.force_change_password,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
