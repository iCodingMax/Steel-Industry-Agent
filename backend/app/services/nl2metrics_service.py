"""
NL2Metrics指标查询引擎
功能：基于用户问题匹配预定义指标，生成SQL查询
"""
import re
from typing import List, Optional, Tuple
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric import Metric
from app.models.dimension import Dimension
from app.models.term import Term
from app.models.datasource import DataSource, TableSchema
from app.services.llm_service import llm_service


class NL2MetricsEngine:
    """NL2Metrics指标查询引擎"""

    @staticmethod
    async def match_metrics(
        db: AsyncSession,
        question: str,
        top_k: int = 3,
    ) -> List[Tuple[Metric, float]]:
        """
        匹配相关指标
        :param db: 数据库会话
        :param question: 用户问题
        :param top_k: 返回指标数量
        :return: [(指标, 匹配分数)]
        """
        # 获取所有指标
        stmt = select(Metric).where(Metric.status == "active")
        result = await db.execute(stmt)
        metrics = list(result.scalars().all())

        if not metrics:
            return []

        # 使用LLM进行语义匹配
        metric_list = "\n".join([
            f"- {m.name}: {m.description} (分组: {m.group_name})"
            for m in metrics
        ])

        prompt = f"""请根据用户问题，从以下指标列表中选择最相关的指标。

指标列表：
{metric_list}

用户问题：{question}

请返回最相关的{top_k}个指标名称，按相关性排序，格式如下：
指标名称1
指标名称2
指标名称3

只返回指标名称，不要返回其他内容。"""

        response = await llm_service.chat(prompt)
        matched_names = [line.strip() for line in response.strip().split("\n") if line.strip()]

        # 匹配指标对象
        results = []
        for name in matched_names[:top_k]:
            for metric in metrics:
                if metric.name == name or name in metric.name:
                    results.append((metric, 0.8))  # 默认匹配分数
                    break

        logger.info(f"指标匹配完成: 问题={question}, 匹配数={len(results)}")
        return results

    @staticmethod
    async def extract_dimensions(
        db: AsyncSession,
        question: str,
        metric: Metric,
    ) -> List[Tuple[Dimension, str]]:
        """
        提取维度过滤条件
        :param db: 数据库会话
        :param question: 用户问题
        :param metric: 目标指标
        :return: [(维度, 过滤值)]
        """
        # 获取指标关联的维度
        stmt = select(Dimension).where(
            Dimension.datasource_id == metric.datasource_id,
            Dimension.status == "active",
        )
        result = await db.execute(stmt)
        dimensions = list(result.scalars().all())

        if not dimensions:
            return []

        # 使用LLM提取维度值
        dim_list = "\n".join([
            f"- {d.name}: {d.description}"
            for d in dimensions
        ])

        prompt = f"""请从用户问题中提取维度过滤条件。

可用维度：
{dim_list}

用户问题：{question}

请返回需要过滤的维度及其值，格式如下：
维度名称1=过滤值1
维度名称2=过滤值2

如果没有维度过滤条件，返回"无"。"""

        response = await llm_service.chat(prompt)

        # 解析结果
        filters = []
        if "无" not in response:
            for line in response.strip().split("\n"):
                if "=" in line:
                    parts = line.split("=")
                    dim_name = parts[0].strip()
                    filter_value = parts[1].strip() if len(parts) > 1 else ""

                    for dim in dimensions:
                        if dim.name == dim_name:
                            filters.append((dim, filter_value))
                            break

        logger.info(f"维度提取完成: 指标={metric.name}, 过滤数={len(filters)}")
        return filters

    @staticmethod
    async def generate_sql(
        db: AsyncSession,
        metric: Metric,
        dimensions: List[Tuple[Dimension, str]],
    ) -> str:
        """
        生成指标查询SQL
        :param db: 数据库会话
        :param metric: 目标指标
        :param dimensions: 维度过滤条件
        :return: SQL语句
        """
        # 获取数据源信息
        ds_stmt = select(DataSource).where(DataSource.id == metric.datasource_id)
        ds_result = await db.execute(ds_stmt)
        datasource = ds_result.scalar_one_or_none()

        if not datasource:
            raise ValueError(f"数据源不存在: {metric.datasource_id}")

        # 基础SQL模板
        base_sql = metric.sql_expression

        # 添加WHERE条件
        where_clauses = []
        for dim, value in dimensions:
            # 根据维度类型构建条件
            if dim.hierarchy_level:
                where_clauses.append(f"{dim.column_name} = '{value}'")
            else:
                where_clauses.append(f"{dim.column_name} = '{value}'")

        if where_clauses:
            if "WHERE" in base_sql.upper():
                sql = base_sql + " AND " + " AND ".join(where_clauses)
            else:
                sql = base_sql + " WHERE " + " AND ".join(where_clauses)
        else:
            sql = base_sql

        logger.info(f"SQL生成完成: 指标={metric.name}, SQL={sql}")
        return sql

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[Metric]]:
        """
        NL2Metrics查询流程
        :param db: 数据库会话
        :param question: 用户问题
        :return: (SQL, 结果解释, 匹配的指标)
        """
        try:
            # 1. 匹配指标
            matched_metrics = await NL2MetricsEngine.match_metrics(db, question)
            if not matched_metrics:
                return None, None, None

            metric, score = matched_metrics[0]

            # 2. 提取维度
            dimensions = await NL2MetricsEngine.extract_dimensions(db, question, metric)

            # 3. 生成SQL
            sql = await NL2MetricsEngine.generate_sql(db, metric, dimensions)

            # 4. 生成结果解释
            explanation = f"根据您的查询，已匹配指标「{metric.name}」，查询条件：{question}"

            return sql, explanation, metric

        except Exception as e:
            logger.error(f"NL2Metrics查询失败: {e}")
            return None, None, None


# 服务实例
nl2metrics_engine = NL2MetricsEngine()