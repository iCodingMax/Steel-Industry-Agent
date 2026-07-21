"""
知识库模型模块
定义知识库、文档和文档切片的数据模型

数据关系：
- KnowledgeBase（知识库）: 包含多个 Document（文档）和 DocumentSegment（切片）
- Document（文档）: 关联到 KnowledgeBase，记录上传的文档信息
- DocumentSegment（文档切片）: 关联到 Document 和 KnowledgeBase，存储向量化的文本片段

处理流程：
1. 上传文档 → 创建 Document（status=pending）
2. 解析文档 → 更新 Document（status=processing）
3. 文本切片 → 创建 DocumentSegment
4. 向量化入库 → 更新 Document（status=completed）

注意：
- 使用 PostgreSQL JSONB 类型存储元数据
- DocumentSegment 是向量检索的最小单元
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
import enum

from app.core.base_model import Base


class KnowledgeBaseStatus(str, enum.Enum):
    """知识库状态枚举"""
    ACTIVE = "active"      # 活跃状态，可用于检索
    INACTIVE = "inactive"  # 停用状态，不可用于检索


class DocumentStatus(str, enum.Enum):
    """文档处理状态枚举"""
    PENDING = "pending"    # 待处理：文档已上传，等待解析
    PROCESSING = "processing"  # 处理中：文档正在解析和切片
    COMPLETED = "completed"    # 已完成：文档解析和向量化完成
    FAILED = "failed"      # 处理失败：解析或向量化过程出错


class KnowledgeBase(Base):
    """
    知识库配置表
    存储知识库的基本配置和参数
    支持配置嵌入模型、文本切片大小等参数
    """

    __tablename__ = "knowledge_bases"

    id = Column(Integer, primary_key=True, index=True, comment="知识库ID")
    name = Column(String(100), nullable=False, comment="知识库名称")
    description = Column(Text, nullable=True, comment="知识库描述")
    embedding_model = Column(String(100), default="bge-m3", comment="嵌入模型名称")
    chunk_size = Column(Integer, default=500, comment="文本切片大小")
    chunk_overlap = Column(Integer, default=100, comment="切片重叠长度")
    status = Column(String(20), default="active", comment="状态: active/inactive")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建人ID")

    def to_dict(self, document_count: int = 0) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "embeddingModel": self.embedding_model,
            "chunkSize": self.chunk_size,
            "chunkOverlap": self.chunk_overlap,
            "status": self.status,
            "documentCount": document_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "createdBy": self.created_by,
        }


class Document(Base):
    """
    文档表
    存储上传的原始文档信息
    记录文档的处理状态和切片数量
    """

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, comment="文档ID")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True, comment="知识库ID")
    file_name = Column(String(255), nullable=False, comment="文件名")
    file_path = Column(String(500), nullable=False, comment="文件存储路径")
    file_type = Column(String(50), nullable=False, comment="文件类型: txt/pdf/md/docx")
    file_size = Column(Integer, nullable=True, comment="文件大小(字节)")
    page_count = Column(Integer, nullable=True, comment="页数")
    status = Column(String(20), default="pending", comment="状态: pending/processing/completed/failed")
    error_message = Column(Text, nullable=True, comment="错误信息")
    segment_count = Column(Integer, default=0, comment="切片数量")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "knowledgeBaseId": self.knowledge_base_id,
            "fileName": self.file_name,
            "filePath": self.file_path,
            "fileType": self.file_type,
            "fileSize": self.file_size,
            "pageCount": self.page_count,
            "status": self.status,
            "errorMessage": self.error_message,
            "segmentCount": self.segment_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentSegment(Base):
    """
    文档切片表
    存储文档的文本切片，是向量检索的最小单元
    每个切片包含内容、位置信息和元数据
    切片内容会被向量化后存入向量数据库
    """

    __tablename__ = "document_segments"

    id = Column(Integer, primary_key=True, index=True, comment="切片ID")
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True, comment="文档ID")
    knowledge_base_id = Column(Integer, ForeignKey("knowledge_bases.id"), nullable=False, index=True, comment="知识库ID")
    content = Column(Text, nullable=False, comment="切片内容")
    segment_index = Column(Integer, nullable=False, comment="切片序号")
    start_char = Column(Integer, nullable=True, comment="起始字符位置")
    end_char = Column(Integer, nullable=True, comment="结束字符位置")
    meta_data = Column(JSONB, nullable=True, comment="元数据(JSON)")
    created_at = Column(DateTime, default=func.now(), comment="创建时间")

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "documentId": self.document_id,
            "knowledgeBaseId": self.knowledge_base_id,
            "content": self.content,
            "segmentIndex": self.segment_index,
            "startChar": self.start_char,
            "endChar": self.end_char,
            "metadata": self.meta_data if self.meta_data else {},
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }