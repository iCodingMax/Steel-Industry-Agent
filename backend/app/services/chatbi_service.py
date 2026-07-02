"""
ChatBI智能问数服务
功能：NL2Metrics优先 + NL2SQL兜底 + 结果解释 + 图表类型推荐
"""
import re
import time
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
    """ChatBI智能问数服务"""

    # 图表类型关键词映射
    CHART_KEYWORDS = {
        "line": ["折线", "趋势", "走势", "变化趋势", "曲线", "波动"],
        "bar": ["柱状", "条形", "对比", "比较", "排名", "排行", "各.*数量"],
        "pie": ["饼图", "占比", "比例", "分布", "构成", "百分比"],
    }

    @staticmethod
    def suggest_chart_type(question: str) -> str:
        """
        根据用户问题推荐图表类型
        :param question: 用户问题
        :return: 推荐的图表类型 (line/bar/pie/table)
        """
        for chart_type, keywords in ChatBIService.CHART_KEYWORDS.items():
            for kw in keywords:
                if re.search(kw, question):
                    return chart_type
        return "bar"

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
        datasource_id: Optional[int] = None,
    ) -> Tuple[str, Optional[List[dict]], List[dict], float, Optional[str], Optional[List[dict]], str]:
        """
        智能问数流程
        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID（可选）
        :return: (结果解释, 数据结果, SQL溯源, 查询耗时, 解释prompt, 字段元信息, 推荐图表类型)
        """
        start_time = time.time()

        sql_traces = []
        results = None
        explanation = ""
        column_meta = None
        chart_type = ChatBIService.suggest_chart_type(question)

        try:
            # 1. 尝试NL2Metrics
            sql, metrics_explanation, matched_metric = await nl2metrics_engine.query(db, question)

            if sql and matched_metric:
                # NL2Metrics成功
                datasource_id = matched_metric.datasource_id
                ds_stmt = select(DataSource).where(DataSource.id == datasource_id)
                ds_result = await db.execute(ds_stmt)
                datasource = ds_result.scalar_one_or_none()

                if datasource:
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
                    else:
                        logger.warning(f"NL2Metrics SQL执行失败: {error}")

            # 2. NL2Metrics失败，尝试NL2SQL兜底
            if results is None:
                # 如果没有指定数据源，选择第一个可用数据源
                if datasource_id is None:
                    ds_stmt = select(DataSource).where(DataSource.status == "active").limit(1)
                    ds_result = await db.execute(ds_stmt)
                    datasource = ds_result.scalar_one_or_none()
                    if datasource:
                        datasource_id = datasource.id
                    else:
                        return "抱歉，未找到可用的数据源。", None, [], time.time() - start_time, None, None, chart_type

                sql, data, error, meta = await nl2sql_engine.query(db, question, datasource_id)
                logger.info(f"NL2SQL查询结果: sql={sql}, data_count={len(data) if data else 0}, error={error}")
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

            query_time = time.time() - start_time
            logger.info(f"ChatBI查询完成: 问题={question}, 结果数={len(results) if results else 0}, 耗时={query_time:.2f}s")

            explanation_prompt = ChatBIService._build_explanation_prompt(question, sql_traces, results) if results else None
            return explanation, results, sql_traces, query_time, explanation_prompt, column_meta, chart_type

        except Exception as e:
            logger.error(f"ChatBI查询失败: {e}")
            return f"查询失败: {str(e)}", None, [], time.time() - start_time, None, None, chart_type

    @staticmethod
    def _build_explanation_prompt(
        question: str,
        sql_traces: List[dict],
        results: List[dict],
    ) -> str:
        """构建解释prompt（用于流式生成）"""
        if not results:
            return "查询结果为空。"

        import json
        result_count = len(results)
        sample_data = results[:5]
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
        :param question: 用户问题
        :param sql: 执行的SQL
        :param results: 查询结果
        :return: 自然语言解释
        """
        if not results:
            return "查询结果为空。"

        # 构建结果摘要
        import json
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
        return explanation


# 服务实例
chatbi_service = ChatBIService()