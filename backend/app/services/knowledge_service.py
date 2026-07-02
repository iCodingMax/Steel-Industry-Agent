"""
文档解析服务（基于LlamaIndex）
功能：文档加载、文本切片、向量入库、知识检索问答
"""
import os
import json
import asyncio
from typing import List, Optional, Tuple
from pathlib import Path
from loguru import logger

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase, Document, DocumentSegment
from app.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeQuery,
    KnowledgeQueryResult,
)
from app.middlewares.exception_handler import BusinessException


class DocumentParserService:
    """文档解析服务类"""

    SUPPORTED_FILE_TYPES = ["txt", "pdf", "md", "docx"]

    @staticmethod
    def _get_file_type(file_name: str) -> str:
        """获取文件类型"""
        ext = Path(file_name).suffix.lower().lstrip(".")
        if ext in DocumentParserService.SUPPORTED_FILE_TYPES:
            return ext
        raise BusinessException(code=400, message=f"不支持的文件类型: {ext}")

    @staticmethod
    async def load_document(file_path: str, file_type: str) -> List[str]:
        """
        加载文档内容
        :param file_path: 文件路径
        :param file_type: 文件类型
        :return: 文档文本段落列表
        """
        try:
            if file_type == "txt":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return [content]

            elif file_type == "md":
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return [content]

            elif file_type == "pdf":
                from pypdf import PdfReader
                reader = PdfReader(file_path)
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text.strip():
                        pages.append(text)
                logger.info(f"PDF文档加载完成: {file_path}, 共{len(pages)}页")
                return pages

            elif file_type == "docx":
                from docx import Document
                doc = Document(file_path)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                logger.info(f"DOCX文档加载完成: {file_path}, 共{len(paragraphs)}段落")
                return paragraphs

            else:
                raise BusinessException(code=400, message=f"不支持的文件类型: {file_type}")

        except Exception as e:
            logger.error(f"文档加载失败: {file_path}, 错误: {e}")
            raise BusinessException(code=500, message=f"文档加载失败: {str(e)}")

    @staticmethod
    def split_text(
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> List[Tuple[str, int, int]]:
        """
        文本切片
        :param text: 原始文本
        :param chunk_size: 切片大小
        :param chunk_overlap: 重叠长度
        :return: [(切片内容, 起始位置, 结束位置)]
        """
        from llama_index.core.text_splitter import SentenceSplitter

        splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        chunks = splitter.split_text(text)
        # 计算每个切片的位置信息
        result = []
        current_pos = 0
        for chunk in chunks:
            start_pos = text.find(chunk[:50], current_pos)  # 查找切片起始位置
            if start_pos == -1:
                start_pos = current_pos
            end_pos = start_pos + len(chunk)
            result.append((chunk, start_pos, end_pos))
            current_pos = end_pos - chunk_overlap  # 考虑重叠

        logger.info(f"文本切片完成: 原文长度{len(text)}, 切片数量{len(result)}")
        return result

    @staticmethod
    async def process_document(
        db: AsyncSession,
        document: Document,
        knowledge_base: KnowledgeBase,
        storage_dir: str = "./storage/documents",
    ) -> int:
        """
        处理文档：加载、切片、存储
        :param db: 数据库会话
        :param document: 文档记录
        :param knowledge_base: 知识库配置
        :param storage_dir: 文档存储目录
        :return: 切片数量
        """
        try:
            # 更新文档状态为处理中
            document.status = "processing"
            await db.commit()

            # 加载文档内容
            file_path = document.file_path
            file_type = document.file_type
            paragraphs = await DocumentParserService.load_document(file_path, file_type)

            # 合并所有段落
            full_text = "\n\n".join(paragraphs)

            # 切片
            chunks = DocumentParserService.split_text(
                full_text,
                chunk_size=knowledge_base.chunk_size,
                chunk_overlap=knowledge_base.chunk_overlap,
            )

            # 存储切片到数据库
            for idx, (content, start_char, end_char) in enumerate(chunks):
                segment = DocumentSegment(
                    document_id=document.id,
                    knowledge_base_id=knowledge_base.id,
                    content=content,
                    segment_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    metadata=json.dumps({
                        "file_name": document.file_name,
                        "file_type": document.file_type,
                    }),
                )
                db.add(segment)

            # 更新文档状态和切片数量
            document.status = "completed"
            document.segment_count = len(chunks)
            await db.commit()

            logger.info(f"文档处理完成: {document.file_name}, 切片数量: {len(chunks)}")
            return len(chunks)

        except Exception as e:
            document.status = "failed"
            document.error_message = str(e)
            await db.commit()
            logger.error(f"文档处理失败: {document.file_name}, 错误: {e}")
            raise BusinessException(code=500, message=f"文档处理失败: {str(e)}")


class KnowledgeBaseService:
    """知识库服务类"""

    @staticmethod
    async def create(
        db: AsyncSession,
        data: KnowledgeBaseCreate,
        user_id: Optional[int] = None,
    ) -> KnowledgeBase:
        """创建知识库"""
        kb = KnowledgeBase(
            name=data.name,
            description=data.description,
            embedding_model=data.embeddingModel,
            chunk_size=data.chunkSize,
            chunk_overlap=data.chunkOverlap,
            created_by=user_id,
        )
        db.add(kb)
        await db.commit()
        await db.refresh(kb)
        logger.info(f"创建知识库: {kb.name} (ID: {kb.id})")
        return kb

    @staticmethod
    async def get_by_id(db: AsyncSession, kb_id: int) -> Optional[KnowledgeBase]:
        """根据ID获取知识库"""
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[KnowledgeBase]:
        """获取所有知识库"""
        stmt = select(KnowledgeBase).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(
        db: AsyncSession,
        kb_id: int,
        data: KnowledgeBaseUpdate,
    ) -> Optional[KnowledgeBase]:
        """更新知识库"""
        kb = await KnowledgeBaseService.get_by_id(db, kb_id)
        if not kb:
            raise BusinessException(code=404, message="知识库不存在")

        update_data = data.model_dump(exclude_unset=True)
        # 处理字段名映射
        field_mapping = {
            "embeddingModel": "embedding_model",
            "chunkSize": "chunk_size",
            "chunkOverlap": "chunk_overlap",
        }
        for key, value in update_data.items():
            db_key = field_mapping.get(key, key)
            if hasattr(kb, db_key):
                setattr(kb, db_key, value)

        await db.commit()
        await db.refresh(kb)
        logger.info(f"更新知识库: {kb.name} (ID: {kb.id})")
        return kb

    @staticmethod
    async def delete(db: AsyncSession, kb_id: int) -> None:
        """删除知识库"""
        kb = await KnowledgeBaseService.get_by_id(db, kb_id)
        if not kb:
            raise BusinessException(code=404, message="知识库不存在")

        # 删除关联的切片
        await db.execute(
            delete(DocumentSegment).where(DocumentSegment.knowledge_base_id == kb_id)
        )
        # 删除关联的文档
        await db.execute(
            delete(Document).where(Document.knowledge_base_id == kb_id)
        )
        # 删除知识库
        await db.delete(kb)
        await db.commit()
        logger.info(f"删除知识库: {kb.name} (ID: {kb_id})")


class DocumentService:
    """文档服务类"""

    @staticmethod
    async def create(
        db: AsyncSession,
        knowledge_base_id: int,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: Optional[int] = None,
    ) -> Document:
        """创建文档记录"""
        doc = Document(
            knowledge_base_id=knowledge_base_id,
            file_name=file_name,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            status="pending",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        logger.info(f"创建文档记录: {file_name} (ID: {doc.id})")
        return doc

    @staticmethod
    async def get_by_id(db: AsyncSession, doc_id: int) -> Optional[Document]:
        """根据ID获取文档"""
        stmt = select(Document).where(Document.id == doc_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_knowledge_base(
        db: AsyncSession,
        kb_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        """获取知识库下的所有文档"""
        stmt = select(Document).where(Document.knowledge_base_id == kb_id).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete(db: AsyncSession, doc_id: int) -> None:
        """删除文档"""
        doc = await DocumentService.get_by_id(db, doc_id)
        if not doc:
            raise BusinessException(code=404, message="文档不存在")

        # 删除关联的切片
        await db.execute(
            delete(DocumentSegment).where(DocumentSegment.document_id == doc_id)
        )
        # 删除文件
        if os.path.exists(doc.file_path):
            os.remove(doc.file_path)
        # 删除文档记录
        await db.delete(doc)
        await db.commit()
        logger.info(f"删除文档: {doc.file_name} (ID: {doc_id})")


# 服务实例
document_parser_service = DocumentParserService()
knowledge_base_service = KnowledgeBaseService()
document_service = DocumentService()