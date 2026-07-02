"""
用户模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from app.core.base_model import Base


class User(Base):
    """用户表"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    username = Column(String(50), unique=True, index=True, nullable=False, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    role = Column(String(20), default="admin", comment="角色")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    force_change_password = Column(Boolean, default=True, comment="是否强制改密")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "lastLoginAt": self.last_login_at.isoformat() if self.last_login_at else None,
            "forceChangePassword": self.force_change_password,
        }
