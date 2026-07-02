"""
审计日志模型
记录所有用户操作，用于安全审计和问题追踪
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func

from app.core.base_model import Base


class AuditLog(Base):
    """审计日志表"""

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
    detail = Column(JSON, nullable=True, comment="操作详情(JSON)")
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
