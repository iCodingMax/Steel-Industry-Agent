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

from app.core.database import get_db_session
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.knowledge import KnowledgeBase, Document
from app.models.datasource import DataSource
from app.models.session import Session as ChatSession
from app.middlewares.exception_handler import success_response
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
    """从现有业务表中采集审计日志（初始化用）"""
    collected = 0

    # 采集知识库操作
    kb_result = await db.execute(select(KnowledgeBase))
    for kb in kb_result.scalars().all():
        # 检查是否已存在
        exists = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                and_(AuditLog.resource_type == "knowledge_base", AuditLog.resource_id == kb.id, AuditLog.action == "create")
            )
        )
        if (exists.scalar() or 0) == 0:
            log = AuditLog(
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
            db.add(log)
            collected += 1

    # 采集文档上传操作
    doc_result = await db.execute(select(Document))
    for doc in doc_result.scalars().all():
        exists = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                and_(AuditLog.resource_type == "document", AuditLog.resource_id == doc.id, AuditLog.action == "create")
            )
        )
        if (exists.scalar() or 0) == 0:
            log = AuditLog(
                user_id=None,
                username="系统采集",
                action="create",
                resource_type="document",
                resource_id=doc.id,
                resource_name=doc.file_name,
                method="POST",
                path=f"/knowledge-bases/{doc.knowledge_base_id}/documents",
                status="success" if doc.status == "completed" else "failed",
                error_message=doc.error_message,
                detail={"fileType": doc.file_type, "fileSize": doc.file_size, "status": doc.status},
                created_at=doc.created_at,
            )
            db.add(log)
            collected += 1

    # 采集数据源操作
    ds_result = await db.execute(select(DataSource))
    for ds in ds_result.scalars().all():
        exists = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                and_(AuditLog.resource_type == "datasource", AuditLog.resource_id == ds.id, AuditLog.action == "create")
            )
        )
        if (exists.scalar() or 0) == 0:
            log = AuditLog(
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
            db.add(log)
            collected += 1

    # 采集会话操作
    session_result = await db.execute(select(ChatSession))
    for sess in session_result.scalars().all():
        exists = await db.execute(
            select(func.count()).select_from(AuditLog).where(
                and_(AuditLog.resource_type == "session", AuditLog.resource_id == sess.id, AuditLog.action == "create")
            )
        )
        if (exists.scalar() or 0) == 0:
            log = AuditLog(
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
            db.add(log)
            collected += 1

    await db.commit()
    return success_response(data={"collected": collected}, message=f"采集完成，共新增 {collected} 条审计日志")
