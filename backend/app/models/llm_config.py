"""
大模型配置模型
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


class LLMConfig(Base):
    """大模型配置表"""

    __tablename__ = "llm_configs"

    id = Column(Integer, primary_key=True, index=True, comment="配置ID")
    name = Column(String(100), nullable=False, comment="配置名称")
    type = Column(String(20), nullable=False, comment="类型: xinference/newapi/openai")
    base_url = Column(String(255), nullable=False, comment="服务地址")
    api_key = Column(String(255), nullable=True, comment="API密钥")
    model_name = Column(String(100), nullable=False, comment="模型名称")
    model_type = Column(String(20), nullable=True, comment="模型类型: embedding/rerank/llm")
    max_tokens = Column(Integer, default=2048, comment="最大输出token")
    temperature = Column(Float, default=0.7, comment="温度参数")
    top_p = Column(Float, nullable=True, comment="Top-p采样")
    extra_params = Column(JSONB, nullable=True, comment="额外参数(JSON)")
    is_default = Column(Boolean, default=False, comment="是否默认配置")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self, include_secret: bool = False) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "baseUrl": self.base_url,
            "apiKey": self.api_key if include_secret else (self.api_key[:6] + "..." if self.api_key else None),
            "modelName": self.model_name,
            "modelType": self.model_type,
            "maxTokens": self.max_tokens,
            "temperature": self.temperature,
            "topP": self.top_p,
            "extraParams": self.extra_params if self.extra_params else {},
            "isDefault": self.is_default,
            "status": self.status,
            "description": self.description,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }



