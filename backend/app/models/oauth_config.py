"""
OAuth2配置模型
存储系统OAuth2认证配置信息

配置类型：
- system: 系统用户配置（登录工业智能助手平台的用户）
- chat: 对话用户配置（发布应用集成的业务系统用户）
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func

from app.core.base_model import Base


class OAuthConfig(Base):
    """
    OAuth2配置表
    存储OAuth2统一认证相关配置
    
    config_type区分不同场景的配置：
    - system: 系统用户配置（平台登录认证）
    - chat: 对话用户配置（应用集成认证）
    """

    __tablename__ = "oauth_config"

    id = Column(Integer, primary_key=True, comment="配置ID")
    config_type = Column(String(20), nullable=False, default="system", comment="配置类型: system/chat")
    authorization_url = Column(String(500), nullable=False, comment="授权端地址")
    token_url = Column(String(500), nullable=False, comment="Token端地址")
    user_info_url = Column(String(500), nullable=False, comment="用户信息端地址")
    scope = Column(String(200), nullable=False, comment="连接范围")
    client_id = Column(String(200), nullable=False, comment="客户端ID")
    client_secret = Column(String(500), nullable=False, comment="客户端密钥")
    field_mapping = Column(Text, nullable=True, comment="字段映射JSON")
    redirect_url = Column(String(500), nullable=False, comment="回调地址")
    enabled = Column(Boolean, default=False, comment="是否启用")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        import json
        try:
            field_mapping = json.loads(self.field_mapping) if self.field_mapping else {}
        except (json.JSONDecodeError, TypeError):
            field_mapping = {}

        return {
            "id": self.id,
            "configType": self.config_type,
            "authorizationUrl": self.authorization_url,
            "tokenUrl": self.token_url,
            "userInfoUrl": self.user_info_url,
            "scope": self.scope,
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
            "fieldMapping": field_mapping,
            "redirectUrl": self.redirect_url,
            "enabled": self.enabled,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
