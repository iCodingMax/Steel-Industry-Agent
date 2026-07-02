"""
路由分发服务
功能：意图识别、路由分发、混合分析
"""
import time
from typing import List, Optional, Tuple
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from app.services.llm_service import llm_service
from app.services.vector_service import knowledge_qa_service
from app.services.chatbi_service import chatbi_service
from app.schemas.knowledge import KnowledgeQuery


class IntentClassifier:
    """意图分类器"""

    @staticmethod
    async def classify(question: str) -> str:
        """
        意图分类
        :param question: 用户问题
        :return: 意图类型（knowledge/data/hybrid）
        """
        intent = await llm_service.classify_intent(question)
        logger.info(f"意图分类完成: 问题={question}, 意图={intent}")
        return intent


class RouterService:
    """路由分发服务"""

    @staticmethod
    async def route(
        db: AsyncSession,
        question: str,
        knowledge_base_id: Optional[int] = None,
        datasource_id: Optional[int] = None,
    ) -> Tuple[str, List[dict], List[dict], float]:
        """
        路由分发
        :param db: 数据库会话
        :param question: 用户问题
        :param knowledge_base_id: 知识库ID
        :param datasource_id: 数据源ID
        :return: (回答内容, 知识引用, SQL溯源, 查询耗时)
        """
        start_time = time.time()

        # 1. 意图分类
        intent = await IntentClassifier.classify(question)

        references = []
        sql_traces = []
        answer = ""

        try:
            if intent == "knowledge":
                # 知识问答通道
                if knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=question,
                            topK=5,
                        )
                        answer, refs, query_time = await knowledge_qa_service.answer(db, query, kb)
                        references = [ref.model_dump() for ref in refs]
                    else:
                        answer = "抱歉，指定的知识库不存在。"
                else:
                    answer = "请先选择知识库进行知识问答。"

            elif intent == "data":
                # 数据查询通道
                explanation, results, traces, query_time = await chatbi_service.query(
                    db, question, datasource_id
                )
                answer = explanation
                sql_traces = traces

            elif intent == "hybrid":
                # 混合分析通道（MVP：串行执行）
                # 先执行知识问答
                if knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=question,
                            topK=3,
                        )
                        knowledge_answer, refs, _ = await knowledge_qa_service.answer(db, query, kb)
                        references = [ref.model_dump() for ref in refs]

                # 再执行数据查询
                explanation, results, traces, _ = await chatbi_service.query(
                    db, question, datasource_id
                )
                sql_traces = traces

                # 融合结果
                if knowledge_answer and explanation:
                    answer = f"【知识解答】\n{knowledge_answer}\n\n【数据分析】\n{explanation}"
                elif knowledge_answer:
                    answer = knowledge_answer
                elif explanation:
                    answer = explanation
                else:
                    answer = "抱歉，无法找到相关信息或数据。"

            else:
                # Fallback
                answer = "抱歉，无法理解您的问题。请尝试重新描述。"

            query_time = time.time() - start_time
            logger.info(f"路由分发完成: 意图={intent}, 耗时={query_time:.2f}s")

            return answer, references, sql_traces, query_time

        except Exception as e:
            logger.error(f"路由分发失败: {e}")
            return f"处理失败: {str(e)}", [], [], time.time() - start_time


# 服务实例
intent_classifier = IntentClassifier()
router_service = RouterService()