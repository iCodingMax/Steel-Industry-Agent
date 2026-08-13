"""
向量索引与检索服务（基于LlamaIndex + pgvector）

本模块提供钢铁行业知识库的向量检索能力，主要包含两个核心类：

1. VectorIndexService：向量索引服务
   - 负责将文档切片转换为向量并存储到pgvector数据库
   - 提供向量检索功能，支持基于segment_id的去重逻辑
   - 缓存向量存储实例，避免重复创建连接

2. KnowledgeQAService：知识问答服务
   - 整合向量检索与LLM生成，实现RAG流程
   - 构建上下文并调用LLM生成回答
   - 返回回答内容及引用来源

关键技术点：
- 使用Xinference作为嵌入模型服务（bge-m3）
- 使用pgvector作为向量存储引擎
- 支持基于segment_id的去重，避免返回重复片段
- 支持内容去重，确保引用来源不重复
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
    """
    向量索引服务类

    负责文档切片的向量化存储和检索，是RAG系统的核心组件之一。
    采用类变量缓存机制，避免重复创建向量存储实例，提升性能。

    属性：
        _embed_model: 嵌入模型实例（通过Xinference调用bge-m3）
        _vector_stores: 知识库ID到VectorStore实例的映射字典（缓存）
    """

    _embed_model = None
    _vector_stores = {}  # 知识库ID -> VectorStore实例

    @classmethod
    def _get_embed_model(cls):
        """
        获取嵌入模型实例（通过Xinference OpenAI兼容接口）

        该方法采用懒加载模式，首次调用时初始化嵌入模型，后续调用直接返回缓存实例。
        使用text-embedding-ada-002作为占位model参数，绕过LlamaIndex的模型名校验，
        实际通过model_name参数指定调用的模型（bge-m3）。

        返回：
            OpenAIEmbedding: 嵌入模型实例
        """
        if cls._embed_model is None:
            from llama_index.embeddings.openai import OpenAIEmbedding
            
            # 使用text-embedding-ada-002作为model参数绕过LlamaIndex模型名校验
            # 通过model_name参数指定实际调用的模型名(bge-m3)
            cls._embed_model = OpenAIEmbedding(
                model="text-embedding-ada-002",  # 占位，绕过枚举校验
                model_name=settings.XINFERENCE_EMBED_MODEL,  # 实际模型名
                api_base=f"{settings.XINFERENCE_BASE_URL}/v1",
                api_key="not-needed",
                timeout=300,  # 增加超时时间至 5 分钟，防止大批量切片处理超时
                embed_batch_size=32,  # 限制单次发送的文本数量，将大请求拆分为小批次，降低服务端压力
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

        从数据库中读取指定知识库下的所有文档切片，将其转换为向量并存储到pgvector数据库。
        构建完成后，向量存储实例会被缓存到类变量中，以便后续检索时快速使用。

        :param db: 数据库会话，用于查询文档切片
        :param knowledge_base: 知识库配置对象，包含知识库ID和切片参数
        :return: 索引文档数量

        流程步骤：
            1. 查询知识库下所有文档切片
            2. 将切片转换为LlamaIndex Document格式
            3. 创建PGVectorStore实例（连接pgvector数据库）
            4. 构建VectorStoreIndex并持久化向量
            5. 缓存向量存储实例
        """
        try:
            # 步骤1：获取知识库下所有已完成的切片
            logger.info(f"开始构建向量索引: 知识库ID={knowledge_base.id}, 知识库名称={knowledge_base.name}")
            stmt = select(DocumentSegment).where(
                DocumentSegment.knowledge_base_id == knowledge_base.id
            )
            result = await db.execute(stmt)
            segments = list(result.scalars().all())
            logger.info(f"查询到文档切片数量: {len(segments)}")

            if not segments:
                logger.warning(f"知识库无切片数据: {knowledge_base.id}")
                return 0

            # 步骤2：转换为LlamaIndex Document格式
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
            logger.info(f"转换为LlamaIndex Document完成: {len(llama_docs)}条")

            # 步骤3：获取嵌入模型
            embed_model = cls._get_embed_model()

            # 步骤4：构建向量索引（使用pgvector）
            from llama_index.vector_stores.postgres import PGVectorStore
            from llama_index.core import VectorStoreIndex, StorageContext

            logger.info(f"创建PGVectorStore: table=kb_{knowledge_base.id}, host={settings.PGVECTOR_HOST}")
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

            # 构建索引（向量化并入库）
            logger.info("开始向量化并构建索引...")
            index = VectorStoreIndex.from_documents(
                llama_docs,
                storage_context=storage_context,
                embed_model=embed_model,
            )

            # 步骤5：缓存向量存储实例，供后续检索使用
            cls._vector_stores[knowledge_base.id] = vector_store

            logger.success(f"向量索引构建完成: 知识库ID={knowledge_base.id}, 文档数量={len(llama_docs)}")
            return len(llama_docs)

        except Exception as e:
            logger.error(f"向量索引构建失败: 知识库ID={knowledge_base.id}, 错误={e}", exc_info=True)
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

        根据用户问题在指定知识库中进行相似度检索，返回匹配的文档片段。
        检索结果会进行去重处理，确保同一segment_id只返回分数最高的片段。

        :param db: 数据库会话，用于查询文档信息
        :param query: 查询请求对象，包含问题和检索参数
        :param knowledge_base: 知识库配置对象
        :return: 检索结果列表，包含片段内容、分数和元数据

        流程步骤：
            1. 获取嵌入模型实例
            2. 获取或加载向量存储实例
            3. 创建VectorStoreIndex并执行检索（获取3倍topK结果）
            4. 基于segment_id去重，保留分数最高的片段
            5. 按分数排序，取前topK结果
            6. 查询文档名称，构造返回结果
        """
        try:
            logger.info(f"开始向量检索: 知识库ID={knowledge_base.id}, 问题={query.question[:50]}...")

            # 步骤1：获取嵌入模型
            embed_model = cls._get_embed_model()

            # 步骤2：获取向量存储（如果不存在则重新加载）
            vector_store = cls._vector_stores.get(knowledge_base.id)
            if vector_store is None:
                logger.info(f"向量存储未缓存，重新加载: 知识库ID={knowledge_base.id}")
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

            # 步骤3：创建索引并执行检索
            from llama_index.core import VectorStoreIndex
            index = VectorStoreIndex.from_vector_store(
                vector_store,
                embed_model=embed_model,
            )

            # 执行检索（获取更多结果以便去重，取topK*3）
            retriever = index.as_retriever(similarity_top_k=query.topK * 3)
            nodes = retriever.retrieve(query.question)
            logger.info(f"原始检索结果数: {len(nodes)}")

            # 步骤4：去重：基于segment_id，保留分数最高的
            # 解决同一文档切片可能被多次检索到的问题
            unique_nodes = {}
            for node in nodes:
                segment_id = node.metadata.get("segment_id")
                if segment_id is None:
                    continue
                
                # 如果该segment_id已存在，只保留分数更高的
                if segment_id in unique_nodes:
                    if node.score and node.score > unique_nodes[segment_id].score:
                        unique_nodes[segment_id] = node
                else:
                    unique_nodes[segment_id] = node
            logger.info(f"去重后结果数: {len(unique_nodes)}")

            # 步骤5：相似度阈值过滤（低于阈值的结果不返回）
            threshold = query.scoreThreshold if hasattr(query, 'scoreThreshold') else 0.0
            if threshold > 0:
                filtered_nodes = {k: v for k, v in unique_nodes.items() if (v.score or 0) >= threshold}
                logger.info(f"相似度阈值过滤: threshold={threshold}, 过滤前={len(unique_nodes)}, 过滤后={len(filtered_nodes)}")
                unique_nodes = filtered_nodes

            # 步骤6：按分数排序，取前topK
            sorted_nodes = sorted(unique_nodes.values(), key=lambda n: n.score or 0, reverse=True)[:query.topK]

            # 步骤6：转换结果，查询文档名称
            results = []
            for node in sorted_nodes:
                segment_id = node.metadata.get("segment_id")
                document_id = node.metadata.get("document_id")

                # 获取文档名称（用于前端展示引用来源）
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

            logger.info(f"向量检索完成: 问题={query.question[:30]}..., 原始结果数={len(nodes)}, 去重后={len(results)}")
            return results

        except Exception as e:
            logger.error(f"向量检索失败: 问题={query.question[:30]}..., 错误={e}", exc_info=True)
            raise BusinessException(code=500, message=f"向量检索失败: {str(e)}")

    @classmethod
    async def delete_index(cls, knowledge_base_id: int) -> None:
        """
        删除向量索引

        从缓存中移除指定知识库的向量存储实例。
        注意：PGVectorStore会自动管理表，这里只需移除缓存引用。

        :param knowledge_base_id: 知识库ID
        """
        try:
            vector_store = cls._vector_stores.get(knowledge_base_id)
            if vector_store:
                # 删除向量表（PGVectorStore会自动管理表，这里移除缓存即可）
                cls._vector_stores.pop(knowledge_base_id, None)
                logger.info(f"向量索引删除完成: 知识库ID={knowledge_base_id}")
            else:
                logger.warning(f"向量索引不存在: 知识库ID={knowledge_base_id}")
        except Exception as e:
            logger.error(f"向量索引删除失败: 知识库ID={knowledge_base_id}, 错误={e}", exc_info=True)


class KnowledgeQAService:
    """
    知识问答服务类

    整合向量检索与LLM生成能力，实现完整的RAG流程。
    将检索到的知识片段作为上下文传递给LLM，生成基于知识库的回答。

    核心流程：
        1. 调用VectorIndexService进行向量检索
        2. 对检索结果进行内容去重
        3. 构建上下文Prompt
        4. 调用LLM生成回答
        5. 返回回答内容及引用来源
    """

    @classmethod
    async def answer(
        cls,
        db: AsyncSession,
        query: KnowledgeQuery,
        knowledge_base: KnowledgeBase,
        history: Optional[List[dict]] = None,
    ) -> tuple[str, List[KnowledgeQueryResult], float]:
        """
        知识问答

        根据用户问题在知识库中检索相关知识，并生成回答。

        :param db: 数据库会话
        :param query: 查询请求对象，包含问题和检索参数
        :param knowledge_base: 知识库配置对象
        :param history: 对话历史（多轮对话上下文）
        :return: (回答内容, 引用列表, 查询耗时)

        流程步骤：
            1. 调用向量检索获取相关知识片段
            2. 内容去重：相同内容的引用只保留第一个
            3. 构建上下文文本（按文档编号组织）
            4. 构建Prompt并调用LLM生成回答（传入历史上下文）
            5. 返回回答、引用列表和耗时
        """
        import time
        start_time = time.time()

        try:
            logger.info(f"开始知识问答: 知识库ID={knowledge_base.id}, 问题={query.question[:50]}...")

            # 步骤1：检索相关知识
            references = await VectorIndexService.search(db, query, knowledge_base)
            logger.info(f"检索到引用数量: {len(references)}")

            if not references:
                logger.warning(f"未找到相关知识: {query.question[:30]}...")
                return "抱歉，未找到相关知识内容。", [], time.time() - start_time

            # 步骤2：去重：内容相同的引用只保留第一个
            # 这是第二层去重，确保返回给用户的引用内容不重复
            seen_contents = set()
            unique_refs = []
            for ref in references:
                content_key = ref.content.strip()
                if content_key not in seen_contents:
                    seen_contents.add(content_key)
                    unique_refs.append(ref)
            logger.info(f"内容去重后引用数量: {len(unique_refs)}")

            # 步骤3：构建上下文文本
            # 将多个知识片段按编号组织，便于LLM理解和引用
            context_parts = []
            for i, ref in enumerate(unique_refs):
                context_parts.append(f"【文档{i+1}】{ref.content}")
            context_text = "\n\n".join(context_parts)
            logger.debug(f"构建上下文完成: {len(context_text)}字符")

            # 步骤4：调用LLM生成回答
            from app.services.llm_service import llm_service

            prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{query.question}

请提供准确、简洁的回答，并在回答中标注引用来源（如"根据文档1..."）。"""

            answer = await llm_service.chat(prompt, history=history)
            logger.info(f"LLM生成回答完成: 回答长度={len(answer)}")

            # 步骤5：计算耗时并返回结果
            query_time = time.time() - start_time
            logger.info(f"知识问答完成: 问题={query.question[:30]}..., 耗时={query_time:.2f}s")

            return answer, unique_refs, query_time

        except Exception as e:
            logger.error(f"知识问答失败: 问题={query.question[:30]}..., 错误={e}", exc_info=True)
            raise BusinessException(code=500, message=f"知识问答失败: {str(e)}")


# 服务实例（供其他模块调用）
vector_index_service = VectorIndexService()
knowledge_qa_service = KnowledgeQAService()