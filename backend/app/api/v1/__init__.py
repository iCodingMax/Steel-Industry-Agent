"""
v1 API 路由模块
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.oauth import router as oauth_router
from app.api.v1.user import router as user_router
from app.api.v1.chat_user import router as chat_user_router
from app.api.v1.chat_auth import router as chat_auth_router
from app.api.v1.datasource import router as datasource_router
from app.api.v1.metric import router as metric_router
from app.api.v1.dimension import router as dimension_router
from app.api.v1.term import router as term_router
from app.api.v1.llm_config import router as llm_config_router
from app.api.v1.knowledge import router as knowledge_router
from app.api.v1.application import router as application_router
from app.api.v1.chatbi import router as chatbi_router
from app.api.v1.chat import router as chat_router
from app.api.v1.health import router as health_router
from app.api.v1.audit_log import router as audit_log_router
from app.api.v1.tool import router as tool_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(oauth_router, prefix="/oauth", tags=["OAuth2认证"])
api_router.include_router(user_router, prefix="/users", tags=["用户管理"])
api_router.include_router(chat_user_router, tags=["对话用户"])
api_router.include_router(chat_auth_router, tags=["对话用户认证"])
api_router.include_router(datasource_router, prefix="/datasources", tags=["数据源管理"])
api_router.include_router(metric_router, prefix="/metrics", tags=["指标管理"])
api_router.include_router(dimension_router, prefix="/dimensions", tags=["维度管理"])
api_router.include_router(term_router, prefix="/terms", tags=["术语管理"])
api_router.include_router(llm_config_router, prefix="/llm-configs", tags=["LLM配置"])
api_router.include_router(knowledge_router, prefix="/knowledge-bases", tags=["知识库管理"])
api_router.include_router(application_router, prefix="/applications", tags=["应用管理"])
api_router.include_router(chatbi_router, prefix="/chatbi", tags=["智能问数"])
api_router.include_router(chat_router, prefix="/sessions", tags=["对话管理"])
api_router.include_router(audit_log_router, prefix="/audit-logs", tags=["审计日志"])
api_router.include_router(health_router, prefix="/health", tags=["健康检查"])
api_router.include_router(tool_router, tags=["工具管理"])
