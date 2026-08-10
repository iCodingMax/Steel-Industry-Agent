"""
应用管理模型模块
定义应用、应用提示词等数据模型

数据关系：
- Application（应用）: 存储应用配置信息
- AppPrompt（应用提示词）: 关联到 Application，存储应用专属提示词

应用设置包含：
- 基本信息：名称、描述、图标、状态
- 模型设置：LLM模型、嵌入模型、重排模型
- 提示词管理：系统提示词、用户提示词模板
- 关联知识库：绑定多个知识库
- 开场白：默认欢迎语

集成设置包含：
- iframe嵌入配置
- 自定义域名
- API密钥管理
- 公开访问链接（通过access_hash生成，16位随机十六进制）
"""
import secrets
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


def generate_access_hash() -> str:
    """生成16位随机十六进制访问hash（使用secrets.token_hex(8)）"""
    return secrets.token_hex(8)


class Application(Base):
    """
    应用配置表
    存储应用的完整配置信息
    """

    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True, comment="应用ID")
    name = Column(String(100), nullable=False, comment="应用名称")
    description = Column(Text, nullable=True, comment="应用描述")
    icon = Column(String(255), nullable=True, comment="应用图标URL")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    model_name = Column(String(100), default="glm-5.1-fp8", comment="LLM模型名称")
    embedding_model = Column(String(100), default="bge-m3", comment="嵌入模型名称")
    rerank_model = Column(String(100), default="bge-reranker-large", comment="重排模型名称")
    system_prompt = Column(Text, nullable=True, comment="系统提示词")
    user_prompt_template = Column(Text, nullable=True, comment="用户提示词模板")
    greeting_message = Column(Text, nullable=True, comment="开场白消息")
    knowledge_base_ids = Column(JSONB, nullable=True, comment="关联知识库ID列表")
    datasource_ids = Column(JSONB, nullable=True, comment="关联数据源ID列表")
    tool_config_ids = Column(JSONB, nullable=True, comment="关联工具配置ID列表(MCP/Skills)")
    score_threshold = Column(Float, default=0.6, comment="检索相似度阈值(0-1之间)")
    top_k = Column(Integer, default=3, comment="引用分段数(1-10之间)")
    iframe_height = Column(Integer, default=600, comment="iframe默认高度")
    iframe_width = Column(String(20), default="100%", comment="iframe默认宽度")
    require_auth = Column(Boolean, default=True, comment="是否需要身份验证")
    api_key = Column(String(100), nullable=True, comment="API密钥")
    max_tokens = Column(Integer, default=8192, comment="最大生成token数")
    temperature = Column(Integer, default=7, comment="温度参数(0-20，除以10为实际值)")
    top_p = Column(Integer, default=9, comment="top_p参数(0-10，除以10为实际值)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人ID")
    access_hash = Column(String(16), unique=True, nullable=True, comment="公开访问hash（16位随机十六进制）")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 自动生成access_hash（如果未提供）
        if not self.access_hash:
            self.access_hash = generate_access_hash()

    @property
    def access_hash_display(self) -> str:
        """获取公开访问hash（如果为空则自动生成）"""
        if not self.access_hash:
            self.access_hash = generate_access_hash()
        return self.access_hash

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "accessHash": self.access_hash_display,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "status": self.status,
            "modelName": self.model_name,
            "embeddingModel": self.embedding_model,
            "rerankModel": self.rerank_model,
            "systemPrompt": self.system_prompt,
            "userPromptTemplate": self.user_prompt_template,
            "greetingMessage": self.greeting_message,
            "knowledgeBaseIds": self.knowledge_base_ids if self.knowledge_base_ids else [],
            "datasourceIds": self.datasource_ids if self.datasource_ids else [],
            "toolConfigIds": self.tool_config_ids if self.tool_config_ids else [],
            "scoreThreshold": self.score_threshold if self.score_threshold is not None else 0.6,
            "topK": self.top_k if self.top_k is not None else 3,
            "iframeHeight": self.iframe_height,
            "iframeWidth": self.iframe_width,
            "requireAuth": self.require_auth,
            "apiKey": self.api_key,
            "maxTokens": self.max_tokens,
            "temperature": self.temperature / 10.0,
            "topP": self.top_p / 10.0,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "createdBy": self.created_by,
        }


class AppPrompt(Base):
    """
    应用提示词表
    存储应用专属的提示词配置
    """

    __tablename__ = "app_prompts"

    id = Column(Integer, primary_key=True, index=True, comment="提示词ID")
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False, index=True, comment="应用ID")
    name = Column(String(100), nullable=False, comment="提示词名称")
    type = Column(String(50), default="system", comment="类型: system/user/tool")
    content = Column(Text, nullable=False, comment="提示词内容")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序顺序")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "applicationId": self.application_id,
            "name": self.name,
            "type": self.type,
            "content": self.content,
            "isActive": self.is_active,
            "sortOrder": self.sort_order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }