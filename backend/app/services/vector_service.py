"""
向量索引与检索服务（基于LlamaIndex + pgvector）
"""
import os
import json
from typing import List, Optional
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase, DocumentSegment, Document
from app.schemas.knowledge import KnowledgeQuery, KnowledgeQueryResult
from app.core.config import settings
from app.middlewares.exception_handler import BusinessException


class VectorIndexService:
    """向量索引服务类"""

    _embed_model = None
    _vector_stores = {}  # 知识库ID -> VectorStore实例

    @classmethod
    def _get_embed_model(cls):
        """获取嵌入模型实例（通过Xinference OpenAI兼容接口）"""
        if cls._embed_model is None:
            from llama_index.embeddings.openai import OpenAIEmbedding
            
            # 使用text-embedding-ada-002作为model参数绕过LlamaIndex模型名校验
            # 通过model_name参数指定实际调用的模型名(bge-m3)
            cls._embed_model = OpenAIEmbedding(
                model="text-embedding-ada-002",  # 占位，绕过枚举校验
                model_name=settings.XINFERENCE_EMBED_MODEL,  # 实际模型名
                api_base=f"{settings.XINFERENCE_BASE_URL}/v1",
                api_key="not-needed",
            )
            logger.info(f"嵌入模型初始化完成: {settings.XINFERENCE_EMBED_MODEL} (via Xinference)")
        return cls._embed_model

    @classmethod
    async def build_index(
        cls,
        db: AsyncSession,
        knowledge_base: KnowledgeBase,
    ) -> int:
        """
        构建向量索引
        :param db: 数据库会话
        :param knowledge_base: 知识库配置
        :return: 索引文档数量
        """
        try:
            # 获取知识库下所有已完成的切片
            stmt = select(DocumentSegment).where(
                DocumentSegment.knowledge_base_id == knowledge_base.id
            )
            result = await db.execute(stmt)
            segments = list(result.scalars().all())

            if not segments:
                logger.warning(f"知识库无切片数据: {knowledge_base.id}")
                return 0

            # 转换为LlamaIndex Document格式
            from llama_index.core import Document as LlamaDocument

            llama_docs = []
            for seg in segments:
                doc = LlamaDocument(
                    text=seg.content,
                    metadata={
                        "segment_id": seg.id,
                        "document_id": seg.document_id,
                        "knowledge_base_id": seg.knowledge_base_id,
                        "segment_index": seg.segment_index,
                    },
                )
                llama_docs.append(doc)

            # 获取嵌入模型
            embed_model = cls._get_embed_model()

            # 构建向量索引（使用pgvector）
            from llama_index.vector_stores.postgres import PGVectorStore
            from llama_index.core import VectorStoreIndex, StorageContext

            # 创建PGVectorStore
            vector_store = PGVectorStore.from_params(
                database=settings.PGVECTOR_DATABASE,
                host=settings.PGVECTOR_HOST,
                password=settings.PGVECTOR_PASSWORD,
                port=settings.PGVECTOR_PORT,
                user=settings.PGVECTOR_USER,
                table_name=f"kb_{knowledge_base.id}",
                embed_dim=1024,  # bge-m3维度
            )

            # 创建存储上下文
            storage_context = StorageContext.from_defaults(vector_store=vector_store)

            # 构建索引
            index = VectorStoreIndex.from_documents(
                llama_docs,
                storage_context=storage_context,
                embed_model=embed_model,
            )

            # 缓存向量存储实例
            cls._vector_stores[knowledge_base.id] = vector_store

            logger.info(f"向量索引构建完成: 知识库ID={knowledge_base.id}, 文档数量={len(llama_docs)}")
            return len(llama_docs)

        except Exception as e:
            logger.error(f"向量索引构建失败: {e}")
            raise BusinessException(code=500, message=f"向量索引构建失败: {str(e)}")

    @classmethod
    async def search(
        cls,
        db: AsyncSession,
        query: KnowledgeQuery,
        knowledge_base: KnowledgeBase,
    ) -> List[KnowledgeQueryResult]:
        """
        向量检索
        :param db: 数据库会话
        :param query: 查询请求
        :param knowledge_base: 知识库配置
        :return: 检索结果列表
        """
        try:
            # 获取嵌入模型
            embed_model = cls._get_embed_model()

            # 获取向量存储（如果不存在则重新加载）
            vector_store = cls._vector_stores.get(knowledge_base.id)
            if vector_store is None:
                from llama_index.vector_stores.postgres import PGVectorStore
                vector_store = PGVectorStore.from_params(
                    database=settings.PGVECTOR_DATABASE,
                    host=settings.PGVECTOR_HOST,
                    password=settings.PGVECTOR_PASSWORD,
                    port=settings.PGVECTOR_PORT,
                    user=settings.PGVECTOR_USER,
                    table_name=f"kb_{knowledge_base.id}",
                    embed_dim=1024,
                )
                cls._vector_stores[knowledge_base.id] = vector_store

            # 创建索引
            from llama_index.core import VectorStoreIndex
            index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=embed_model,
            )

            # 执行检索
            retriever = index.as_retriever(similarity_top_k=query.topK)
            nodes = retriever.retrieve(query.question)

            # 转换结果
            results = []
            for node in nodes:
                segment_id = node.metadata.get("segment_id")
                document_id = node.metadata.get("document_id")

                # 获取文档名称
                doc_stmt = select(Document).where(Document.id == document_id)
                doc_result = await db.execute(doc_stmt)
                doc = doc_result.scalar_one_or_none()
                doc_name = doc.file_name if doc else "未知文档"

                result = KnowledgeQueryResult(
                    segmentId=segment_id,
                    documentId=document_id,
                    documentName=doc_name,
                    content=node.text,
                    score=node.score or 0.0,
                    metadata=node.metadata,
                )
                results.append(result)

            logger.info(f"向量检索完成: 问题={query.question}, 结果数={len(results)}")
            return results

        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            raise BusinessException(code=500, message=f"向量检索失败: {str(e)}")

    @classmethod
    async def delete_index(cls, knowledge_base_id: int) -> None:
        """删除向量索引"""
        try:
            vector_store = cls._vector_stores.get(knowledge_base_id)
            if vector_store:
                # 删除向量表
                # PGVectorStore会自动管理表，这里移除缓存即可
                cls._vector_stores.pop(knowledge_base_id, None)
                logger.info(f"向量索引删除完成: 知识库ID={knowledge_base_id}")
        except Exception as e:
            logger.error(f"向量索引删除失败: {e}")


class KnowledgeQAService:
    """知识问答服务类"""

    @classmethod
    async def answer(
        cls,
        db: AsyncSession,
        query: KnowledgeQuery,
        knowledge_base: KnowledgeBase,
    ) -> tuple[str, List[KnowledgeQueryResult], float]:
        """
        知识问答
        :param db: 数据库会话
        :param query: 查询请求
        :param knowledge_base: 知识库配置
        :return: (回答内容, 引用列表, 查询耗时)
        """
        import time
        start_time = time.time()

        try:
            # 1. 检索相关知识
            references = await VectorIndexService.search(db, query, knowledge_base)

            if not references:
                return "抱歉，未找到相关知识内容。", [], time.time() - start_time

            # 2. 去重：内容相同的引用只保留第一个
            seen_contents = set()
            unique_refs = []
            for ref in references:
                content_key = ref.content.strip()
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    unique_refs.append(ref)

            # 3. 构建上下文
            context_parts = []
            for i, ref in enumerate(unique_refs):
                context_parts.append(f"【文档{i+1}】{ref.content}")
            context_text = "\n\n".join(context_parts)

            # 3. 调用LLM生成回答
            from app.services.llm_service import llm_service

            prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{query.question}

请提供准确、简洁的回答，并在回答中标注引用来源（如"根据文档1..."）。"""

            answer = await llm_service.chat(prompt)

            query_time = time.time() - start_time
            logger.info(f"知识问答完成: 问题={query.question}, 耗时={query_time:.2f}s")

            return answer, unique_refs, query_time

        except Exception as e:
            logger.error(f"知识问答失败: {e}")
            raise BusinessException(code=500, message=f"知识问答失败: {str(e)}")


# 服务实例
vector_index_service = VectorIndexService()
knowledge_qa_service = KnowledgeQAService()