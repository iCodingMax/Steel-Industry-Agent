"""
知识库相关Schema
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求"""
    name: str = Field(..., description="知识库名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="知识库描述")
    embeddingModel: str = Field(default="bge-m3", description="嵌入模型名称")
    chunkSize: int = Field(default=500, description="文本切片大小", ge=100, le=2000)
    chunkOverlap: int = Field(default=100, description="切片重叠长度", ge=0, le=500)


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求"""
    name: Optional[str] = Field(None, description="知识库名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="知识库描述")
    embeddingModel: Optional[str] = Field(None, description="嵌入模型名称")
    chunkSize: Optional[int] = Field(None, description="文本切片大小", ge=100, le=2000)
    chunkOverlap: Optional[int] = Field(None, description="切片重叠长度", ge=0, le=500)
    status: Optional[str] = Field(None, description="状态")


class KnowledgeBaseResponse(BaseModel):
    """知识库响应"""
    id: int
    name: str
    description: Optional[str]
    embeddingModel: str
    chunkSize: int
    chunkOverlap: int
    status: str
    documentCount: int = 0
    createdAt: Optional[str]
    updatedAt: Optional[str]
    createdBy: Optional[int]


class DocumentUpload(BaseModel):
    """文档上传请求"""
    knowledgeBaseId: int = Field(..., description="知识库ID")
    fileName: str = Field(..., description="文件名")
    fileType: str = Field(..., description="文件类型")


class DocumentResponse(BaseModel):
    """文档响应"""
    id: int
    knowledgeBaseId: int
    fileName: str
    filePath: str
    fileType: str
    fileSize: Optional[int]
    pageCount: Optional[int]
    status: str
    errorMessage: Optional[str]
    segmentCount: int
    createdAt: Optional[str]
    updatedAt: Optional[str]


class DocumentSegmentResponse(BaseModel):
    """文档切片响应"""
    id: int
    documentId: int
    knowledgeBaseId: int
    content: str
    segmentIndex: int
    startChar: Optional[int]
    endChar: Optional[int]
    metadata: dict
    createdAt: Optional[str]


class KnowledgeQuery(BaseModel):
    """知识检索请求"""
    knowledgeBaseId: int = Field(..., description="知识库ID")
    question: str = Field(..., description="查询问题", min_length=1)
    topK: int = Field(default=5, description="返回结果数量", ge=1, le=20)


class KnowledgeQueryResult(BaseModel):
    """知识检索结果"""
    segmentId: int
    documentId: int
    documentName: str
    content: str
    score: float
    metadata: dict


class KnowledgeAnswerResponse(BaseModel):
    """知识问答响应"""
    answer: str
    references: List[KnowledgeQueryResult]
    queryTime: float