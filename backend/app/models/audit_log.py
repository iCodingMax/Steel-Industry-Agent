"""
审计日志模型模块
定义系统操作审计日志的数据模型

记录内容：
- 用户操作类型（create/update/delete/login/query）
- 操作资源类型和ID
- 请求方法、路径和IP地址
- 操作状态和错误信息
- 操作详情（JSON格式）

使用场景：
- 安全审计：追踪敏感操作
- 问题排查：记录操作过程便于追溯
- 合规检查：满足数据安全合规要求

注意：
- 通过中间件自动记录HTTP请求日志
- 不记录敏感数据（如密码）
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.core.base_model import Base


class AuditLog(Base):
    """
    审计日志表
    记录系统所有用户操作，用于安全审计和问题追踪
    通过中间件自动记录，无需手动创建
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, comment="日志ID")
    user_id = Column(Integer, nullable=True, index=True, comment="操作用户ID")
    username = Column(String(100), nullable=True, comment="操作用户名")
    action = Column(String(50), nullable=False, index=True, comment="操作类型: create/update/delete/login/query")
    resource_type = Column(String(50), nullable=False, index=True, comment="资源类型: knowledge_base/document/datasource/session等")
    resource_id = Column(Integer, nullable=True, comment="资源ID")
    resource_name = Column(String(255), nullable=True, comment="资源名称")
    method = Column(String(10), nullable=True, comment="HTTP方法: GET/POST/PUT/DELETE")
    path = Column(String(500), nullable=True, comment="请求路径")
    ip_address = Column(String(50), nullable=True, comment="操作IP地址")
    status = Column(String(20), default="success", comment="操作状态: success/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    detail = Column(JSONB, nullable=True, comment="操作详情(JSON)")
    created_at = Column(DateTime, default=func.now(), comment="操作时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "userId": self.user_id,
            "username": self.username,
            "action": self.action,
            "resourceType": self.resource_type,
            "resourceId": self.resource_id,
            "resourceName": self.resource_name,
            "method": self.method,
            "path": self.path,
            "ipAddress": self.ip_address,
            "status": self.status,
            "errorMessage": self.error_message,
            "detail": self.detail,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
