"""
审计日志API
功能：审计日志列表查询、统计汇总、从现有业务表自动采集
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel
from datetime import datetime
from loguru import logger

from app.core.database import get_db_session
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document
from app.models.datasource import DataSource
from app.models.session import Session as ChatSession
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user

router = APIRouter()


@router.get("/stats", summary="审计统计概览")
async def get_audit_stats(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取审计日志统计概览"""
    # 基础过滤条件
    conditions = []
    if start_date:
        conditions.append(AuditLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        conditions.append(AuditLog.created_at <= end_dt)

    base_where = and_(*conditions) if conditions else True

    # 总记录数
    total_result = await db.execute(select(func.count()).select_from(AuditLog).where(base_where))
    total = total_result.scalar() or 0

    # 成功数
    success_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(and_(base_where, AuditLog.status == "success"))
    )
    success_count = success_result.scalar() or 0

    # 失败数
    failed_result = await db.execute(
        select(func.count()).select_from(AuditLog).where(and_(base_where, AuditLog.status == "failed"))
    )
    failed_count = failed_result.scalar() or 0

    # 成功率
    success_rate = round(success_count / total * 100, 1) if total > 0 else 0

    # 按操作类型分组统计
    action_stats_result = await db.execute(
        select(AuditLog.action, func.count().label("count"))
        .where(base_where)
        .group_by(AuditLog.action)
    )
    action_stats = [{"action": row[0], "count": row[1]} for row in action_stats_result.all()]

    # 按资源类型分组统计
    resource_stats_result = await db.execute(
        select(AuditLog.resource_type, func.count().label("count"))
        .where(base_where)
        .group_by(AuditLog.resource_type)
    )
    resource_stats = [{"resourceType": row[0], "count": row[1]} for row in resource_stats_result.all()]

    return success_response(data={
        "total": total,
        "successCount": success_count,
        "failedCount": failed_count,
        "successRate": success_rate,
        "actionStats": action_stats,
        "resourceStats": resource_stats,
    })


@router.get("", summary="获取审计日志列表")
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
    action: Optional[str] = Query(None, description="操作类型筛选"),
    resource_type: Optional[str] = Query(None, description="资源类型筛选"),
    status: Optional[str] = Query(None, description="状态筛选: success/failed"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    keyword: Optional[str] = Query(None, description="关键词搜索"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取审计日志列表（支持多维度筛选）"""
    conditions = []
    if action:
        conditions.append(AuditLog.action == action)
    if resource_type:
        conditions.append(AuditLog.resource_type == resource_type)
    if status:
        conditions.append(AuditLog.status == status)
    if start_date:
        conditions.append(AuditLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d"))
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
        conditions.append(AuditLog.created_at <= end_dt)
    if keyword:
        conditions.append(
            (AuditLog.username.contains(keyword)) |
            (AuditLog.resource_name.contains(keyword)) |
            (AuditLog.path.contains(keyword))
        )

    where_clause = and_(*conditions) if conditions else True

    # 查询总数
    count_result = await db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
    total = count_result.scalar() or 0

    # 查询列表
    stmt = (
        select(AuditLog)
        .where(where_clause)
        .order_by(AuditLog.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()

    return success_response(data={
        "list": [log.to_dict() for log in logs],
        "total": total,
    })


@router.post("/collect", summary="从现有业务数据采集审计日志")
async def collect_audit_logs(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """从现有业务表中采集审计日志（全量查重，确保不遗漏）"""
    from app.models.application import Application
    from app.models.tool_config import ToolConfig
    from app.models.session import Message, Session as ChatSessionModel
    from sqlalchemy import text as sql_text

    collected = 0

    # 修复序列：确保audit_logs_id_seq与MAX(id)同步，防止主键冲突
    try:
        await db.execute(sql_text(
            "SELECT setval('audit_logs_id_seq', COALESCE((SELECT MAX(id) FROM audit_logs), 1), true)"
        ))
    except Exception as seq_err:
        logger.warning(f"修复audit_logs序列失败（可忽略）: {seq_err}")

    # 预加载所有已采集的 (resource_type, resource_id, action) 集合，避免逐条查询
    existing_result = await db.execute(
        select(
            AuditLog.resource_type,
            AuditLog.resource_id,
            AuditLog.action,
        ).where(AuditLog.username == "系统采集")
    )
    existing_set = {(row[0], row[1], row[2]) for row in existing_result.all()}

    def is_collected(resource_type: str, resource_id: int, action: str) -> bool:
        return (resource_type, resource_id, action) in existing_set

    def add_audit_log(**kwargs):
        nonlocal collected
        log = AuditLog(**kwargs)
        db.add(log)
        collected += 1

    try:
        # ---------- 1. 采集应用操作 ----------
        app_result = await db.execute(select(Application))
        for app in app_result.scalars().all():
            if not is_collected("application", app.id, "create"):
                add_audit_log(
                    user_id=app.created_by,
                    username="系统采集",
                    action="create",
                    resource_type="application",
                    resource_id=app.id,
                    resource_name=app.name,
                    method="POST",
                    path="/applications",
                    status="success",
                    detail={"modelName": app.model_name, "status": app.status},
                    created_at=app.created_at,
                )

        # ---------- 2. 采集知识库操作 ----------
        kb_result = await db.execute(select(KnowledgeBase))
        for kb in kb_result.scalars().all():
            if not is_collected("knowledge_base", kb.id, "create"):
                add_audit_log(
                    user_id=kb.created_by,
                    username="系统采集",
                    action="create",
                    resource_type="knowledge_base",
                    resource_id=kb.id,
                    resource_name=kb.name,
                    method="POST",
                    path="/knowledge-bases",
                    status="success",
                    detail={"embeddingModel": kb.embedding_model, "chunkSize": kb.chunk_size},
                    created_at=kb.created_at,
                )

        # ---------- 3. 采集文档操作 ----------
        doc_result = await db.execute(select(Document))
        for doc in doc_result.scalars().all():
            if not is_collected("document", doc.id, "create"):
                add_audit_log(
                    user_id=None,
                    username="系统采集",
                    action="create",
                    resource_type="document",
                    resource_id=doc.id,
                    resource_name=doc.file_name or "未知文档",
                    method="POST",
                    path=f"/knowledge-bases/{doc.knowledge_base_id}/documents" if doc.knowledge_base_id else "/documents",
                    status="success" if doc.status == "completed" else "failed",
                    error_message=doc.error_message,
                    detail={"fileType": doc.file_type, "fileSize": doc.file_size, "status": doc.status},
                    created_at=doc.created_at,
                )

        # ---------- 4. 采集数据源操作 ----------
        ds_result = await db.execute(select(DataSource))
        for ds in ds_result.scalars().all():
            if not is_collected("datasource", ds.id, "create"):
                add_audit_log(
                    user_id=ds.created_by,
                    username="系统采集",
                    action="create",
                    resource_type="datasource",
                    resource_id=ds.id,
                    resource_name=ds.name,
                    method="POST",
                    path="/datasources",
                    status="success",
                    detail={"type": ds.type, "host": ds.host, "database": ds.database},
                    created_at=ds.created_at,
                )

        # ---------- 5. 采集会话操作 ----------
        session_result = await db.execute(select(ChatSession))
        for sess in session_result.scalars().all():
            if not is_collected("session", sess.id, "create"):
                add_audit_log(
                    user_id=sess.user_id,
                    username="系统采集",
                    action="create",
                    resource_type="session",
                    resource_id=sess.id,
                    resource_name=sess.title or "新对话",
                    method="POST",
                    path="/sessions",
                    status="success",
                    detail={"intentType": sess.intent_type},
                    created_at=sess.created_at,
                )

        # ---------- 6. 采集工具配置操作 ----------
        tool_result = await db.execute(select(ToolConfig))
        for tool in tool_result.scalars().all():
            if not is_collected("tool_config", tool.id, "create"):
                add_audit_log(
                    user_id=tool.created_by if hasattr(tool, 'created_by') else None,
                    username="系统采集",
                    action="create",
                    resource_type="tool_config",
                    resource_id=tool.id,
                    resource_name=tool.name,
                    method="POST",
                    path="/tools",
                    status="success",
                    detail={"toolType": tool.tool_type, "description": (tool.description or "")[:100]},
                    created_at=tool.created_at if hasattr(tool, 'created_at') else datetime.now(),
                )

        # ---------- 7. 采集消息操作（全量查重，不依赖时间过滤） ----------
        # 预加载会话标题映射，避免逐条查询
        sess_title_result = await db.execute(
            select(ChatSessionModel.id, ChatSessionModel.title)
        )
        sess_title_map = {row[0]: row[1] for row in sess_title_result.all()}

        msg_result = await db.execute(select(Message).limit(500))
        for msg in msg_result.scalars().all():
            if not is_collected("message", msg.id, "create"):
                session_title = sess_title_map.get(msg.session_id, "会话消息")
                add_audit_log(
                    user_id=None,  # Message模型无user_id字段
                    username="系统采集",
                    action="create",
                    resource_type="message",
                    resource_id=msg.id,
                    resource_name=(session_title or "会话消息")[:50],
                    method="POST",
                    path="/messages",
                    status="success",
                    detail={"role": msg.role, "intent": getattr(msg, 'intent', None)},
                    created_at=msg.created_at,
                )

        # flush到数据库，让get_db_session的auto-commit完成最终提交
        if collected > 0:
            await db.flush()

        logger.info(f"审计日志采集完成，共新增 {collected} 条")
        return success_response(
            data={"collected": collected},
            message=f"采集完成，共新增 {collected} 条审计日志"
        )

    except Exception as e:
        logger.error(f"审计日志采集失败: {str(e)}", exc_info=True)
        raise BusinessException(code=500, message=f"采集失败: {str(e)}")
