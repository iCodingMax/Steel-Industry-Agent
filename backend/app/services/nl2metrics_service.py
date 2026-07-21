"""
NL2Metrics指标查询引擎模块
将自然语言问题转换为预定义指标的SQL查询

核心流程：
1. 指标匹配：使用LLM从预定义指标库中匹配最相关的指标
2. 维度提取：从用户问题中提取维度过滤条件
3. SQL生成：根据指标模板和维度条件生成最终SQL

适用场景：
- 用户查询已定义的业务指标（如产量、合格率、能耗等）
- 需要精确统计口径的数据分析场景

依赖：
- Metric模型：预定义指标库
- Dimension模型：维度定义
- LLMService：语义匹配
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
    """
    NL2Metrics指标查询引擎
    通过自然语言匹配预定义指标，生成精确的SQL查询语句
    优先于NL2SQL执行，提高查询效率和准确性
    """

    @staticmethod
    async def match_metrics(
        db: AsyncSession,
        question: str,
        top_k: int = 3,
    ) -> List[Tuple[Metric, float]]:
        """
        匹配相关指标
        使用LLM进行语义匹配，从预定义指标库中选择最相关的指标

        :param db: 数据库会话
        :param question: 用户问题
        :param top_k: 返回指标数量（默认3）
        :return: [(指标对象, 匹配分数)]
        """
        logger.debug(f"开始指标匹配: 问题={question[:50]}..., top_k={top_k}")

        # 获取所有活跃指标
        stmt = select(Metric).where(Metric.status == "active")
        result = await db.execute(stmt)
        metrics = list(result.scalars().all())

        if not metrics:
            logger.debug("没有找到活跃指标")
            return []

        # 构建指标列表文本，用于LLM匹配
        metric_list = "\n".join([
            f"- {m.name}: {m.description} (分组: {m.group_name})"
            for m in metrics
        ])

        # 构建LLM提示词
        prompt = f"""请根据用户问题，从以下指标列表中选择最相关的指标。

指标列表：
{metric_list}

用户问题：{question}

请返回最相关的{top_k}个指标名称，按相关性排序，格式如下：
指标名称1
指标名称2
指标名称3

只返回指标名称，不要返回其他内容。"""

        # 调用LLM进行匹配
        response = await llm_service.chat(prompt)
        matched_names = [line.strip() for line in response.strip().split("\n") if line.strip()]

        # 将匹配名称映射到指标对象
        results = []
        for name in matched_names[:top_k]:
            for metric in metrics:
                if metric.name == name or name in metric.name:
                    results.append((metric, 0.8))  # 默认匹配分数0.8
                    break

        logger.info(f"指标匹配完成: 问题={question[:50]}..., 匹配数={len(results)}")
        return results

    @staticmethod
    async def extract_dimensions(
        db: AsyncSession,
        question: str,
        metric: Metric,
    ) -> List[Tuple[Dimension, str]]:
        """
        提取维度过滤条件
        使用LLM从用户问题中提取与指标关联的维度及其过滤值

        :param db: 数据库会话
        :param question: 用户问题
        :param metric: 目标指标
        :return: [(维度对象, 过滤值)]
        """
        logger.debug(f"开始维度提取: 指标={metric.name}")

        # 获取指标关联数据源的活跃维度
        stmt = select(Dimension).where(
            Dimension.datasource_id == metric.datasource_id,
            Dimension.status == "active",
        )
        result = await db.execute(stmt)
        dimensions = list(result.scalars().all())

        if not dimensions:
            logger.debug("没有找到关联维度")
            return []

        # 构建维度列表文本
        dim_list = "\n".join([
            f"- {d.name}: {d.description}"
            for d in dimensions
        ])

        # 构建LLM提示词，提取维度过滤条件
        prompt = f"""请从用户问题中提取维度过滤条件。

可用维度：
{dim_list}

用户问题：{question}

请返回需要过滤的维度及其值，格式如下：
维度名称1=过滤值1
维度名称2=过滤值2

如果没有维度过滤条件，返回"无"。"""

        # 调用LLM提取维度值
        response = await llm_service.chat(prompt)

        # 解析LLM返回结果
        filters = []
        if "无" not in response:
            for line in response.strip().split("\n"):
                if "=" in line:
                    parts = line.split("=")
                    dim_name = parts[0].strip()
                    filter_value = parts[1].strip() if len(parts) > 1 else ""

                    # 匹配维度对象
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
        根据指标模板和维度条件生成最终的SQL查询语句

        :param db: 数据库会话
        :param metric: 目标指标（包含SQL模板）
        :param dimensions: 维度过滤条件列表
        :return: 完整的SQL语句
        :raises ValueError: 数据源不存在时抛出
        """
        logger.debug(f"开始SQL生成: 指标={metric.name}, 维度数={len(dimensions)}")

        # 获取数据源信息（用于后续扩展）
        ds_stmt = select(DataSource).where(DataSource.id == metric.datasource_id)
        ds_result = await db.execute(ds_stmt)
        datasource = ds_result.scalar_one_or_none()

        if not datasource:
            raise ValueError(f"数据源不存在: {metric.datasource_id}")

        # 获取指标的基础SQL模板
        base_sql = metric.sql_expression
        logger.debug(f"基础SQL模板: {base_sql[:100]}...")

        # 分离日期维度和非日期维度
        date_dims = []
        other_dims = []
        for dim, value in dimensions:
            if dim.data_type == "date" or dim.column_name.upper() in ("PRODUCE_DATE", "DATE", "CREATED_AT", "HEAT_DATE"):
                date_dims.append((dim, value))
            else:
                other_dims.append((dim, value))

        logger.debug(f"日期维度: {len(date_dims)}, 非日期维度: {len(other_dims)}")

        # 日期解析工具函数
        from datetime import datetime, timedelta
        import re as _re

        def fix_chinese_date(s: str) -> str:
            """修正中文日期格式为标准格式"""
            s = _re.sub(r"(\d{4})年(\d{1,2})月(\d{1,2})日", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", s)
            s = _re.sub(r"(\d{4})年(\d{1,2})月(?!\d)", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-01", s)
            return s

        def parse_date_value(val: str) -> tuple:
            """
            解析用户输入的日期值，返回(start_date, end_date)
            支持格式：2024年10月、2024年、2024-10、2024-10-01等
            """
            val = val.strip()
            # YYYY年MM月DD日
            m = _re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$", val)
            if m:
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                start = f"{year}-{month:02d}-{day:02d}"
                day += 1
                if day > 28:
                    return start, None
                return start, f"{year}-{month:02d}-{day:02d}"
            # YYYY年MM月
            m = _re.match(r"^(\d{4})年(\d{1,2})月$", val)
            if m:
                year, month = int(m.group(1)), int(m.group(2))
                if month == 12:
                    return f"{year}-12-01", f"{year+1}-01-01"
                else:
                    return f"{year}-{month:02d}-01", f"{year}-{month+1:02d}-01"
            # YYYY年
            m = _re.match(r"^(\d{4})年$", val)
            if m:
                year = int(m.group(1))
                return f"{year}-01-01", f"{year+1}-01-01"
            # 标准格式 YYYY-MM-DD
            val = fix_chinese_date(val)
            m = _re.match(r"^(\d{4})-(\d{2})-(\d{2})$", val)
            if m:
                return val, f"{m.group(1)}-{m.group(2)}-{str(int(m.group(3))+1).zfill(2)}" if int(m.group(3)) < 28 else None
            # YYYY-MM
            m = _re.match(r"^(\d{4})-(\d{2})$", val)
            if m:
                year, month = int(m.group(1)), int(m.group(2))
                if month == 12:
                    return f"{year}-12-01", f"{year+1}-01-01"
                else:
                    return f"{year}-{month:02d}-01", f"{year}-{month+1:02d}-01"
            # YYYY
            m = _re.match(r"^(\d{4})$", val)
            if m:
                return f"{m.group(1)}-01-01", f"{int(m.group(1))+1}-01-01"
            return None, None

        # 处理日期维度
        if date_dims:
            # 使用用户指定的时间范围
            _, date_val = date_dims[0]
            start_date, end_date = parse_date_value(date_val)
            if start_date and end_date:
                base_sql = base_sql.replace("{start_date}", start_date).replace("{end_date}", end_date)
                logger.debug(f"日期替换完成: {start_date} ~ {end_date}")
            else:
                # 解析失败，使用默认最近30天
                base_sql = base_sql.replace("{start_date}", (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")).replace("{end_date}", datetime.now().strftime("%Y-%m-%d"))
                # 将日期维度作为普通条件追加
                other_dims.extend(date_dims)
                logger.debug("日期解析失败，使用默认时间范围")
        else:
            # 没有用户指定时间，使用默认最近30天
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            base_sql = base_sql.replace("{start_date}", start_date).replace("{end_date}", end_date)
            logger.debug(f"使用默认时间范围: {start_date} ~ {end_date}")

        # 添加非日期维度的WHERE条件
        where_clauses = []
        for dim, value in other_dims:
            # 修正中文日期格式
            safe_value = fix_chinese_date(str(value))
            # 转义单引号防止SQL注入
            safe_value = safe_value.replace("'", "''")
            where_clauses.append(f"{dim.column_name} = '{safe_value}'")

        # 组合最终SQL
        if where_clauses:
            if "WHERE" in base_sql.upper():
                sql = base_sql + " AND " + " AND ".join(where_clauses)
            else:
                sql = base_sql + " WHERE " + " AND ".join(where_clauses)
        else:
            sql = base_sql

        logger.info(f"SQL生成完成: 指标={metric.name}, SQL长度={len(sql)}")
        return sql

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
    ) -> Tuple[Optional[str], Optional[str], Optional[Metric]]:
        """
        NL2Metrics查询流程（完整）
        执行指标匹配、维度提取、SQL生成的完整流程

        :param db: 数据库会话
        :param question: 用户问题
        :return: (SQL语句, 结果解释, 匹配的指标对象)，匹配失败时返回(None, None, None)
        """
        logger.info(f"开始NL2Metrics查询: {question[:50]}...")

        try:
            # 步骤1：匹配指标（使用LLM语义匹配）
            matched_metrics = await NL2MetricsEngine.match_metrics(db, question)
            if not matched_metrics:
                logger.info("NL2Metrics查询失败: 未匹配到指标")
                return None, None, None

            metric, score = matched_metrics[0]
            logger.debug(f"匹配到指标: {metric.name}, 分数={score}")

            # 步骤2：提取维度过滤条件
            dimensions = await NL2MetricsEngine.extract_dimensions(db, question, metric)
            logger.debug(f"提取到维度条件: {len(dimensions)}个")

            # 步骤3：生成SQL语句
            sql = await NL2MetricsEngine.generate_sql(db, metric, dimensions)

            # 步骤4：生成结果解释
            explanation = f"根据您的查询，已匹配指标「{metric.name}」，查询条件：{question}"

            logger.info(f"NL2Metrics查询成功: 指标={metric.name}")
            return sql, explanation, metric

        except Exception as e:
            logger.error(f"NL2Metrics查询失败: {e}")
            return None, None, None


# 服务实例
nl2metrics_engine = NL2MetricsEngine()
logger.info("NL2Metrics指标查询引擎实例已创建")