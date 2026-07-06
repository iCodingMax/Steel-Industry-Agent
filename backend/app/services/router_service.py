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

    @staticmethod
    async def split_hybrid_question(question: str) -> Tuple[str, str]:
        """
        将混合问题拆分为数据子问题和知识子问题
        :param question: 用户原始混合问题
        :return: (数据子问题, 知识子问题)
        """
        prompt = f"""请将以下混合问题拆分为两部分：数据查询部分和知识问答部分。

用户问题：{question}

请按以下格式返回，每行一个：
数据问题：xxx
知识问题：xxx

如果某部分不存在，则留空。只返回结果，不要解释。"""

        result = await llm_service.chat(prompt)
        logger.info(f"混合问题拆分结果: {result}")

        data_question = ""
        knowledge_question = ""

        for line in result.strip().split("\n"):
            line = line.strip()
            if line.startswith("数据问题：") or line.startswith("数据问题:"):
                data_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("知识问题：") or line.startswith("知识问题:"):
                knowledge_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()

        # 如果拆分失败，使用原问题
        if not data_question and not knowledge_question:
            data_question = question
            knowledge_question = question

        logger.info(f"拆分完成: 数据问题={data_question}, 知识问题={knowledge_question}")
        return data_question, knowledge_question


class RouterService:
    """路由分发服务"""

    @staticmethod
    async def route(
        db: AsyncSession,
        question: str,
        knowledge_base_id: Optional[int] = None,
        datasource_id: Optional[int] = None,
    ) -> Tuple[str, List[dict], List[dict], float, Optional[List[dict]], Optional[List[dict]], Optional[str]]:
        """
        路由分发
        :param db: 数据库会话
        :param question: 用户问题
        :param knowledge_base_id: 知识库ID
        :param datasource_id: 数据源ID
        :return: (回答内容, 知识引用, SQL溯源, 查询耗时, 数据结果, 字段元信息, 推荐图表类型)
        """
        start_time = time.time()

        # 1. 意图分类
        intent = await IntentClassifier.classify(question)

        references = []
        sql_traces = []
        answer = ""
        data_result = None
        column_meta = None
        chart_type = None

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
                explanation, results, traces, query_time, _, column_meta, chart_type = await chatbi_service.query(
                    db, question, datasource_id
                )
                answer = explanation
                data_result = results
                sql_traces = traces

            elif intent == "hybrid":
                # 混合分析通道：先拆分子问题，再分别路由
                data_question, knowledge_question = await IntentClassifier.split_hybrid_question(question)

                knowledge_answer = ""
                explanation = ""
                results = None

                # 执行知识问答（使用拆分后的知识子问题）
                if knowledge_question and knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=knowledge_question,
                            topK=3,
                        )
                        knowledge_answer, refs, _ = await knowledge_qa_service.answer(db, query, kb)
                        references = [ref.model_dump() for ref in refs]

                # 执行数据查询（使用拆分后的数据子问题）
                if data_question and datasource_id:
                    explanation, results, traces, _, _, column_meta, chart_type = await chatbi_service.query(
                        db, data_question, datasource_id
                    )
                    data_result = results
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

            return answer, references, sql_traces, query_time, data_result, column_meta, chart_type

        except Exception as e:
            logger.error(f"路由分发失败: {e}")
            return f"处理失败: {str(e)}", [], [], time.time() - start_time, None, None, None


# 服务实例
intent_classifier = IntentClassifier()
router_service = RouterService()