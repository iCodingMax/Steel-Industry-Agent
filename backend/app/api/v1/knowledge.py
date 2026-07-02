"""
知识库API
"""
from typing import List
from fastapi import APIRouter, Depends, Query, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pathlib import Path
import os
import uuid

from app.core.database import get_mysql_session
from app.models.knowledge import Document
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseResponse,
    DocumentResponse,
    KnowledgeQuery,
    KnowledgeAnswerResponse,
)
from app.services.knowledge_service import (
    knowledge_base_service,
    document_service,
    document_parser_service,
)
from app.services.vector_service import vector_index_service, knowledge_qa_service
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()

# 文档存储目录
STORAGE_DIR = Path("./storage/documents")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("", summary="获取知识库列表")
async def list_knowledge_bases(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取所有知识库"""
    kbs = await knowledge_base_service.get_all(db, skip, limit)
    # 查询每个知识库的文档数量
    result = []
    for kb in kbs:
        count_stmt = select(func.count()).where(Document.knowledge_base_id == kb.id)
        count_result = await db.execute(count_stmt)
        doc_count = count_result.scalar() or 0
        result.append(kb.to_dict(document_count=doc_count))
    return success_response(data=result)


@router.get("/{kb_id}", summary="获取知识库详情")
async def get_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """根据ID获取知识库"""
    kb = await knowledge_base_service.get_by_id(db, kb_id)
    if not kb:
        return success_response(data=None, message="知识库不存在")
    # 查询文档数量
    count_stmt = select(func.count()).where(Document.knowledge_base_id == kb.id)
    count_result = await db.execute(count_stmt)
    doc_count = count_result.scalar() or 0
    return success_response(data=kb.to_dict(document_count=doc_count))


@router.post("", summary="创建知识库")
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """创建新知识库"""
    kb = await knowledge_base_service.create(db, data, user.id)
    return success_response(data=kb.to_dict(document_count=0))


@router.put("/{kb_id}", summary="更新知识库")
async def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdate,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """更新知识库"""
    kb = await knowledge_base_service.update(db, kb_id, data)
    # 查询文档数量
    count_stmt = select(func.count()).where(Document.knowledge_base_id == kb.id)
    count_result = await db.execute(count_stmt)
    doc_count = count_result.scalar() or 0
    return success_response(data=kb.to_dict(document_count=doc_count))


@router.delete("/{kb_id}", summary="删除知识库")
async def delete_knowledge_base(
    kb_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """删除知识库"""
    await knowledge_base_service.delete(db, kb_id)
    await vector_index_service.delete_index(kb_id)
    return success_response(message="删除成功")


@router.get("/{kb_id}/documents", summary="获取知识库文档列表")
async def list_documents(
    kb_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取知识库下的所有文档"""
    docs = await document_service.get_by_knowledge_base(db, kb_id, skip, limit)
    return success_response(data=[doc.to_dict() for doc in docs])


@router.post("/{kb_id}/documents", summary="上传文档")
async def upload_document(
    kb_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """上传文档到知识库"""
    # 检查知识库是否存在
    kb = await knowledge_base_service.get_by_id(db, kb_id)
    if not kb:
        raise BusinessException(code=404, message="知识库不存在")

    # 获取文件类型
    file_type = Path(file.filename).suffix.lower().lstrip(".")
    if file_type not in document_parser_service.SUPPORTED_FILE_TYPES:
        raise BusinessException(code=400, message=f"不支持的文件类型: {file_type}")

    # 保存文件
    file_id = uuid.uuid4().hex
    file_path = STORAGE_DIR / f"{file_id}_{file.filename}"
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # 创建文档记录
    doc = await document_service.create(
        db,
        knowledge_base_id=kb_id,
        file_name=file.filename,
        file_path=str(file_path),
        file_type=file_type,
        file_size=len(content),
    )

    # 后台处理文档
    background_tasks.add_task(
        process_document_task,
        db,
        doc.id,
        kb.id,
    )

    return success_response(data=doc.to_dict(), message="文档上传成功，正在后台处理")


async def process_document_task(db_session, doc_id: int, kb_id: int):
    """后台处理文档任务"""
    from app.core.database import MySQLAsyncSession
    async with MySQLAsyncSession() as db:
        try:
            doc = await document_service.get_by_id(db, doc_id)
            kb = await knowledge_base_service.get_by_id(db, kb_id)
            if doc and kb:
                # 处理文档
                await document_parser_service.process_document(db, doc, kb)
                # 构建向量索引
                await vector_index_service.build_index(db, kb)
        except Exception as e:
            logger.error(f"后台处理文档失败: {e}")


@router.delete("/{kb_id}/documents/{doc_id}", summary="删除文档")
async def delete_document(
    kb_id: int,
    doc_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """删除文档"""
    await document_service.delete(db, doc_id)
    return success_response(message="删除成功")


@router.post("/{kb_id}/query", summary="知识问答")
async def query_knowledge(
    kb_id: int,
    data: KnowledgeQuery,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """知识问答检索"""
    kb = await knowledge_base_service.get_by_id(db, kb_id)
    if not kb:
        raise BusinessException(code=404, message="知识库不存在")

    answer, references, query_time = await knowledge_qa_service.answer(db, data, kb)

    response = KnowledgeAnswerResponse(
        answer=answer,
        references=references,
        queryTime=query_time,
    )
    return success_response(data=response)


@router.post("/{kb_id}/build-index", summary="构建向量索引")
async def build_vector_index(
    kb_id: int,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """手动触发向量索引构建"""
    kb = await knowledge_base_service.get_by_id(db, kb_id)
    if not kb:
        raise BusinessException(code=404, message="知识库不存在")

    count = await vector_index_service.build_index(db, kb)
    return success_response(data={"indexedDocuments": count}, message="向量索引构建完成")