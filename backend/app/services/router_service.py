"""
路由分发服务

本模块负责用户问题的意图识别和路由分发，是系统的核心调度层。

主要组件：
1. IntentClassifier：意图分类器
   - 使用LLM对用户问题进行意图分类（knowledge/data/hybrid）
   - 支持混合问题拆分为数据子问题和知识子问题

2. RouterService：路由分发服务
   - 根据意图分类结果将问题分发到对应处理通道
   - 支持知识问答通道、数据查询通道、混合分析通道
   - 融合混合分析的结果，生成统一回答

核心流程：
    用户问题
        │
        ▼
    IntentClassifier.classify()  → 意图分类
        │
        ├── knowledge → knowledge_qa_service.answer()  # 知识问答
        ├── data      → chatbi_service.query()         # 数据查询
        └── hybrid    → 并行调用两个通道，融合结果
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
    """
    意图分类器

    使用LLM对用户问题进行意图分类，支持三种意图类型：
    - knowledge：知识问答意图（工艺知识、技术规范、概念解释等）
    - data：数据查询意图（生产数据、指标数值、统计报表等）
    - hybrid：混合意图（同时包含知识查询和数据查询）

    分类依据：
    - 用户问题中的关键词（"展示"、"查询"、"统计"等表示数据意图）
    - 用户问题中的连接词（"并且"、"同时"、"以及"等表示混合意图）
    - 问题结构（问候语、闲聊等表示知识意图）
    """

    @staticmethod
    async def classify(question: str) -> str:
        """
        意图分类

        使用LLM对用户问题进行意图分类，返回分类结果。

        :param question: 用户问题
        :return: 意图类型（knowledge/data/hybrid）

        分类规则：
            - knowledge: 用户仅询问工艺知识、技术规范、操作规程、概念解释等文档类问题，以及问候语、闲聊等通用对话
            - data: 用户仅查询生产数据、指标数值、统计报表、图表展示等数据类问题
            - hybrid: 用户问题同时包含知识查询和数据查询两部分意图

        判断要点：
            - 如果问题中出现"展示"、"查询"、"统计"、"次数"、"数量"等数据相关关键词，同时出现"解释"、"什么是"、"原理"等知识相关关键词，则属于hybrid
            - 包含"并且"、"同时"、"另外"、"以及"等连接词连接不同类型的问题时，通常属于hybrid
            - 简单问候语（如hello、你好、hi等）属于knowledge意图
        """
        intent = await llm_service.classify_intent(question)
        logger.info(f"意图分类完成: 问题={question[:30]}..., 意图={intent}")
        return intent

    @staticmethod
    async def split_hybrid_question(question: str) -> Tuple[str, str]:
        """
        将混合问题拆分为数据子问题和知识子问题

        对于hybrid类型的问题，将其拆分为两个独立的子问题，
        分别路由到数据查询通道和知识问答通道。

        :param question: 用户原始混合问题
        :return: (数据子问题, 知识子问题)

        拆分逻辑：
            1. 使用LLM将混合问题拆分为数据部分和知识部分
            2. 解析LLM返回的格式（"数据问题：xxx" 和 "知识问题：xxx"）
            3. 如果拆分失败，使用原问题作为两个子问题
        """
        prompt = f"""请将以下混合问题拆分为两部分：数据查询部分和知识问答部分。

用户问题：{question}

拆分规则（非常重要）：
1. 数据问题：提取涉及"展示"、"查询"、"统计"、"图表"等数据查询需求的部分
   - 必须完整保留所有时间范围信息（如"2023年8月"、"2025年9月第一周"等）
   - 必须完整保留所有查询条件和统计要求
   - 示例："使用折线图展示2023年8月的每日吹炼次数" 是正确的数据问题
   - 错误示例："使用折线图展示" 或 "2023年8月的每日吹炼次数"（不完整）
2. 知识问题：提取涉及"如何"、"应该"、"解释"、"什么是"、"原理"、"调整"等知识问答需求的部分
   - 保留完整的问题上下文

请按以下格式返回，每行一个：
数据问题：xxx
知识问题：xxx

如果某部分不存在，则留空。只返回结果，不要解释。

示例1（数据在前）：
用户问题："使用折线图展示2023年8月的每日吹炼次数；当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?"
拆分结果：
数据问题：使用折线图展示2023年8月的每日吹炼次数
知识问题：当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?

示例2（数据在后）：
用户问题："当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?使用折线图展示2023年8月的每日吹炼次数"
拆分结果：
数据问题：使用折线图展示2023年8月的每日吹炼次数
知识问题：当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?
"""

        result = await llm_service.chat(prompt)
        logger.info(f"混合问题拆分结果: {result[:50]}...")

        data_question = ""
        knowledge_question = ""

        # 解析LLM返回的格式
        for line in result.strip().split("\n"):
            line = line.strip()
            if line.startswith("数据问题：") or line.startswith("数据问题:"):
                data_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("知识问题：") or line.startswith("知识问题:"):
                knowledge_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()

        # 如果拆分失败，使用原问题作为两个子问题
        if not data_question and not knowledge_question:
            logger.warning(f"混合问题拆分失败，使用原问题: {question[:30]}...")
            data_question = question
            knowledge_question = question

        logger.info(f"拆分完成: 数据问题={data_question[:30]}..., 知识问题={knowledge_question[:30]}...")
        return data_question, knowledge_question


class RouterService:
    """
    路由分发服务

    根据用户问题的意图分类结果，将请求分发到对应处理通道。
    支持三种路由模式：
    1. 知识问答通道（knowledge意图）：调用knowledge_qa_service
    2. 数据查询通道（data意图）：调用chatbi_service
    3. 混合分析通道（hybrid意图）：并行调用两个通道，融合结果

    返回值统一格式：(回答内容, 知识引用, SQL溯源, 查询耗时, 数据结果, 字段元信息, 推荐图表类型)
    """

    @staticmethod
    async def route(
        db: AsyncSession,
        question: str,
        knowledge_base_id: Optional[int] = None,
        datasource_id: Optional[int] = None,
    ) -> Tuple[str, List[dict], List[dict], float, Optional[List[dict]], Optional[List[dict]], Optional[str]]:
        """
        路由分发

        根据用户问题的意图分类结果，将请求分发到对应处理通道。

        :param db: 数据库会话
        :param question: 用户问题
        :param knowledge_base_id: 知识库ID（可选，知识问答时使用）
        :param datasource_id: 数据源ID（可选，数据查询时使用）
        :return: (回答内容, 知识引用, SQL溯源, 查询耗时, 数据结果, 字段元信息, 推荐图表类型)

        返回值说明：
            answer: 最终回答内容（字符串）
            references: 知识引用列表（字典列表，包含文档名、内容、分数等）
            sql_traces: SQL溯源信息（字典列表，包含SQL语句、来源、行数等）
            query_time: 查询总耗时（秒，浮点数）
            data_result: 数据查询结果（字典列表或None）
            column_meta: 字段元信息（字典列表或None）
            chart_type: 推荐图表类型（字符串或None）

        路由逻辑：
            1. 调用IntentClassifier进行意图分类
            2. 根据意图类型分发到对应通道：
               - knowledge: 调用knowledge_qa_service进行知识问答
               - data: 调用chatbi_service进行数据查询
               - hybrid: 并行调用两个通道，融合结果
            3. 返回统一格式的结果
        """
        start_time = time.time()
        logger.info(f"开始路由分发: 问题={question[:50]}...")

        # 1. 意图分类
        intent = await IntentClassifier.classify(question)
        logger.info(f"意图分类结果: {intent}")

        # 初始化返回变量
        references = []
        sql_traces = []
        answer = ""
        data_result = None
        column_meta = None
        chart_type = None

        try:
            if intent == "knowledge":
                # 知识问答通道
                logger.info("路由到知识问答通道")
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
                        logger.info(f"知识问答完成: 引用数={len(references)}")
                    else:
                        answer = "抱歉，指定的知识库不存在。"
                        logger.warning(f"知识库不存在: ID={knowledge_base_id}")
                else:
                    answer = "请先选择知识库进行知识问答。"
                    logger.warning("未指定知识库，无法进行知识问答")

            elif intent == "data":
                # 数据查询通道
                logger.info("路由到数据查询通道")
                explanation, results, traces, query_time, _, column_meta, chart_type = await chatbi_service.query(
                    db, question, datasource_id
                )
                answer = explanation
                data_result = results
                sql_traces = traces
                logger.info(f"数据查询完成: 结果数={len(results) if results else 0}")

            elif intent == "hybrid":
                # 混合分析通道：先拆分子问题，再分别路由
                logger.info("路由到混合分析通道")
                data_question, knowledge_question = await IntentClassifier.split_hybrid_question(question)

                knowledge_answer = ""
                explanation = ""
                results = None

                # 执行知识问答（使用拆分后的知识子问题）
                if knowledge_question and knowledge_base_id:
                    logger.info("执行混合分析-知识问答部分")
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
                        logger.info(f"混合分析-知识问答完成: 引用数={len(references)}")

                # 执行数据查询（使用拆分后的数据子问题）
                if data_question and datasource_id:
                    logger.info("执行混合分析-数据查询部分")
                    explanation, results, traces, _, _, column_meta, chart_type = await chatbi_service.query(
                        db, data_question, datasource_id
                    )
                    data_result = results
                    sql_traces = traces
                    logger.info(f"混合分析-数据查询完成: 结果数={len(results) if results else 0}")

                # 融合结果（将知识回答和数据分析整合为统一回答）
                if knowledge_answer and explanation:
                    answer = f"【知识解答】\n{knowledge_answer}\n\n【数据分析】\n{explanation}"
                elif knowledge_answer:
                    answer = knowledge_answer
                elif explanation:
                    answer = explanation
                else:
                    answer = "抱歉，无法找到相关信息或数据。"
                logger.info("混合分析结果融合完成")

            else:
                # Fallback：未知意图，返回友好提示
                answer = "抱歉，无法理解您的问题。请尝试重新描述。"
                logger.warning(f"未知意图: {intent}")

            # 计算总耗时
            query_time = time.time() - start_time
            logger.info(f"路由分发完成: 意图={intent}, 耗时={query_time:.2f}s")

            return answer, references, sql_traces, query_time, data_result, column_meta, chart_type

        except Exception as e:
            logger.error(f"路由分发失败: 问题={question[:30]}..., 错误={e}", exc_info=True)
            return f"处理失败: {str(e)}", [], [], time.time() - start_time, None, None, None


# 服务实例（供其他模块调用）
intent_classifier = IntentClassifier()
router_service = RouterService()