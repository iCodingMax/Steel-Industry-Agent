"""
ChatBI智能问数服务

本模块提供钢铁行业智能问数能力，支持两种查询模式：

1. NL2Metrics优先模式：基于用户问题匹配预定义指标，按预定义逻辑查询
   - 优点：查询结果准确，符合业务口径
   - 适用：已有明确指标定义的查询场景

2. NL2SQL兜底模式：未匹配指标时生成SQL查询（通过Xinference调用LLM）
   - 优点：灵活应对各种数据查询需求
   - 适用：临时查询、复杂分析场景

核心功能：
- 图表类型推荐：根据用户问题关键词推荐合适的图表类型
- SQL安全过滤：拦截危险操作（DROP/DELETE/TRUNCATE等）
- SQL语法校验：使用sqlglot校验SQL语法
- 执行控制：超时限制30秒、返回行数限制1000行
- 术语映射：行业术语→标准字段转换
- 结果解释：生成自然语言解释查询结果

调用关系：
    ChatBIService.query()
        ├── nl2metrics_engine.query()  # NL2Metrics优先
        ├── nl2sql_engine.query()      # NL2SQL兜底
        └── llm_service.chat()         # 结果解释
"""
import re
import time
import json
from typing import Optional, List, Tuple
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric import Metric
from app.models.datasource import DataSource
from app.services.nl2metrics_service import nl2metrics_engine
from app.services.nl2sql_service import nl2sql_engine
from app.services.llm_service import llm_service
from app.schemas.knowledge import KnowledgeQueryResult


class ChatBIService:
    """
    ChatBI智能问数服务

    整合NL2Metrics和NL2SQL两种查询引擎，实现智能问数功能。
    优先使用NL2Metrics匹配预定义指标，匹配失败则使用NL2SQL生成查询。

    属性：
        CHART_KEYWORDS: 图表类型关键词映射字典
            - line: 折线图相关关键词（趋势、走势等）
            - bar: 柱状图相关关键词（对比、排名等）
            - pie: 饼图相关关键词（占比、比例等）
    """

    # 图表类型关键词映射：用于根据用户问题自动推荐图表类型
    CHART_KEYWORDS = {
        "line": ["折线", "趋势", "走势", "变化趋势", "曲线", "波动"],
        "bar": ["柱状", "条形", "对比", "比较", "排名", "排行", "各.*数量"],
        "pie": ["饼图", "占比", "比例", "分布", "构成", "百分比"],
    }

    @staticmethod
    def suggest_chart_type(question: str) -> str:
        """
        根据用户问题推荐图表类型

        通过关键词匹配用户问题中的图表需求，返回推荐的图表类型。
        支持折线图(line)、柱状图(bar)、饼图(pie)，默认返回柱状图(bar)。

        :param question: 用户问题
        :return: 推荐的图表类型 (line/bar/pie/table)

        匹配逻辑：
            1. 遍历图表类型及其关键词
            2. 使用正则表达式匹配问题中是否包含关键词
            3. 匹配成功则返回对应图表类型
            4. 无匹配则返回默认类型bar
        """
        for chart_type, keywords in ChatBIService.CHART_KEYWORDS.items():
            for kw in keywords:
                if re.search(kw, question):
                    logger.debug(f"图表类型匹配: 问题={question[:30]}..., 类型={chart_type}, 关键词={kw}")
                    return chart_type
        logger.debug(f"图表类型未匹配，使用默认: bar")
        return "bar"

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
        datasource_id: Optional[int] = None,
    ) -> Tuple[str, Optional[List[dict]], List[dict], float, Optional[str], Optional[List[dict]], str]:
        """
        智能问数流程

        执行完整的智能问数流程，优先尝试NL2Metrics，失败则使用NL2SQL兜底。

        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID（可选）
        :return: (结果解释, 数据结果, SQL溯源, 查询耗时, 解释prompt, 字段元信息, 推荐图表类型)

        返回值说明：
            result_explanation: 自然语言解释（字符串或None）
            data_results: 查询结果数据（列表或None）
            sql_traces: SQL溯源信息（列表）
            query_time: 查询耗时（秒，浮点数）
            explanation_prompt: 解释生成Prompt（用于流式生成，字符串或None）
            column_meta: 字段元信息（列表或None）
            chart_type: 推荐图表类型（字符串）

        流程步骤：
            1. 验证数据源可用性（可选）
            2. 根据问题推荐图表类型
            3. 尝试NL2Metrics匹配预定义指标
               - 匹配成功：执行指标SQL，获取结果
               - 匹配失败：进入NL2SQL兜底
            4. NL2SQL兜底：生成SQL并执行
            5. 构建结果解释Prompt（用于流式生成）
            6. 返回查询结果
        """
        start_time = time.time()
        logger.info(f"开始ChatBI查询: 问题={question[:50]}...")

        # 验证数据源可用性，不可用则自动fallback
        if datasource_id:
            ds_check = select(DataSource).where(DataSource.id == datasource_id, DataSource.status == "active")
            ds_result = await db.execute(ds_check)
            if not ds_result.scalar_one_or_none():
                logger.warning(f"数据源ID={datasource_id}不存在或未激活，自动选择可用数据源")
                datasource_id = None

        sql_traces = []
        results = None
        explanation = ""
        column_meta = None
        chart_type = ChatBIService.suggest_chart_type(question)

        try:
            # 步骤1：尝试NL2Metrics（优先模式）
            logger.info("尝试NL2Metrics查询...")
            sql, metrics_explanation, matched_metric = await nl2metrics_engine.query(db, question)

            if sql and matched_metric:
                # NL2Metrics匹配成功
                logger.info(f"NL2Metrics匹配成功: 指标={matched_metric.name}, SQL={sql[:80]}...")
                datasource_id = matched_metric.datasource_id
                ds_stmt = select(DataSource).where(DataSource.id == datasource_id, DataSource.status == "active")
                ds_result = await db.execute(ds_stmt)
                datasource = ds_result.scalar_one_or_none()

                if datasource:
                    # 执行指标SQL
                    success, error, data, meta = await nl2sql_engine.validate_and_execute(db, sql, datasource)
                    if success:
                        results = data
                        column_meta = meta
                        explanation = metrics_explanation
                        sql_traces.append({
                            "sql": sql,
                            "source": "nl2metrics",
                            "metric": matched_metric.name,
                            "rows": len(results),
                        })
                        logger.info(f"NL2Metrics执行成功: 结果数={len(results)}")
                    else:
                        logger.warning(f"NL2Metrics SQL执行失败: {error}")
                else:
                    logger.warning(f"NL2Metrics匹配的数据源ID={datasource_id}不存在，重置为自动选择")
                    datasource_id = None

            # 步骤2：NL2Metrics失败，尝试NL2SQL兜底
            if results is None:
                logger.info("NL2Metrics未匹配或执行失败，尝试NL2SQL兜底...")
                # 如果没有指定数据源，选择第一个可用数据源
                if datasource_id is None:
                    ds_stmt = select(DataSource).where(DataSource.status == "active").limit(1)
                    ds_result = await db.execute(ds_stmt)
                    datasource = ds_result.scalar_one_or_none()
                    if datasource:
                        datasource_id = datasource.id
                        logger.info(f"自动选择数据源: {datasource.name}")
                    else:
                        logger.error("未找到可用的数据源")
                        return "抱歉，未找到可用的数据源。", None, [], time.time() - start_time, None, None, chart_type

                # 调用NL2SQL引擎生成并执行SQL
                sql, data, error, meta = await nl2sql_engine.query(db, question, datasource_id)
                logger.info(f"NL2SQL查询结果: sql={sql[:80]}..., data_count={len(data) if data else 0}, error={error}")
                column_meta = meta

                if sql:
                    if data:
                        results = data
                        sql_traces.append({
                            "sql": sql,
                            "source": "nl2sql",
                            "rows": len(results),
                        })
                        if error and "自动放宽" in error:
                            explanation = error
                        else:
                            explanation = ""
                    else:
                        results = []
                        sql_traces.append({
                            "sql": sql,
                            "source": "nl2sql",
                            "rows": 0,
                        })
                        explanation = f"查询完成，但未找到数据。{error or ''}"
                else:
                    explanation = f"抱歉，无法生成有效的查询。错误: {error or 'SQL生成失败'}"

            # 步骤3：计算耗时并构建解释Prompt
            query_time = time.time() - start_time
            logger.info(f"ChatBI查询完成: 问题={question[:30]}..., 结果数={len(results) if results else 0}, 耗时={query_time:.2f}s")

            # 构建解释Prompt（用于流式生成回答）
            explanation_prompt = ChatBIService._build_explanation_prompt(question, sql_traces, results) if results else None
            return explanation, results, sql_traces, query_time, explanation_prompt, column_meta, chart_type

        except Exception as e:
            logger.error(f"ChatBI查询失败: 问题={question[:30]}..., 错误={e}", exc_info=True)
            return f"查询失败: {str(e)}", None, [], time.time() - start_time, None, None, chart_type

    @staticmethod
    def _build_explanation_prompt(
        question: str,
        sql_traces: List[dict],
        results: List[dict],
    ) -> str:
        """
        构建解释Prompt（用于流式生成）

        为LLM构建用于生成结果解释的Prompt，包含用户问题、执行的SQL和查询结果。

        :param question: 用户问题
        :param sql_traces: SQL溯源信息列表
        :param results: 查询结果数据
        :return: 解释生成Prompt

        Prompt结构：
            - 用户问题
            - 执行的SQL
            - 查询结果（前5条示例）
            - 解释要求（数据概况、关键数值、对问题的回答）
        """
        if not results:
            return "查询结果为空。"

        result_count = len(results)
        sample_data = results[:5]  # 取前5条作为示例，避免Prompt过长
        sql = sql_traces[0]['sql'] if sql_traces else ''

        return f"""请根据用户问题、执行的SQL和查询结果，生成自然语言解释。

用户问题：{question}

执行的SQL：
{sql}

查询结果（共{result_count}条，展示前5条）：
{json.dumps(sample_data, ensure_ascii=False, default=str)}

请用简洁、专业的语言解释查询结果，包括：
1. 查询到的数据概况
2. 关键数值或趋势
3. 对用户问题的回答

解释内容："""

    @staticmethod
    async def explain_results(
        question: str,
        sql: str,
        results: List[dict],
    ) -> str:
        """
        生成结果解释

        根据用户问题、执行的SQL和查询结果，调用LLM生成自然语言解释。

        :param question: 用户问题
        :param sql: 执行的SQL
        :param results: 查询结果
        :return: 自然语言解释

        使用场景：非流式响应时，直接生成完整的结果解释。
        """
        if not results:
            return "查询结果为空。"

        result_count = len(results)
        sample_data = results[:5]  # 取前5条作为示例

        prompt = f"""请根据用户问题、执行的SQL和查询结果，生成自然语言解释。

用户问题：{question}

执行的SQL：
{sql}

查询结果（共{result_count}条，展示前5条）：
{json.dumps(sample_data, ensure_ascii=False, default=str)}

请用简洁、专业的语言解释查询结果，包括：
1. 查询到的数据概况
2. 关键数值或趋势
3. 对用户问题的回答

解释内容："""

        explanation = await llm_service.chat(prompt)
        logger.info(f"结果解释生成完成: 长度={len(explanation)}")
        return explanation


# 服务实例（供其他模块调用）
chatbi_service = ChatBIService()