"""
工具配置模型
用于管理 MCP Server 和 Skills
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


class ToolConfig(Base):
    """
    工具配置表
    统一管理 MCP Server 和 Skills 两种类型的工具
    """
    __tablename__ = "tool_configs"

    id = Column(Integer, primary_key=True, index=True, comment="工具ID")
    name = Column(String(100), nullable=False, comment="工具名称")
    description = Column(Text, nullable=True, comment="工具描述")
    tool_type = Column(String(20), nullable=False, comment="工具类型: mcp/skill")
    status = Column(String(20), default="active", comment="状态: active/inactive")

    # === MCP 专属配置 ===
    # MCP Server 配置 (JSON格式，包含 url, transport 等)
    mcp_config = Column(JSONB, nullable=True, comment="MCP Server配置")
    
    # === Skill 专属配置 ===
    # Skill 文件路径
    skill_file_path = Column(String(500), nullable=True, comment="Skill文件存储路径")
    # Skill 文件名
    skill_file_name = Column(String(255), nullable=True, comment="Skill原始文件名")

    # === 通用字段 ===
    icon = Column(String(255), nullable=True, comment="图标")
    timeout = Column(Integer, default=30, comment="执行超时时间(秒)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(Integer, nullable=True, comment="创建人ID")

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'tool_type': self.tool_type,
            'status': self.status,
            'mcp_config': self.mcp_config,
            'skill_file_path': self.skill_file_path,
            'skill_file_name': self.skill_file_name,
            'icon': self.icon,
            'timeout': self.timeout,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
        }