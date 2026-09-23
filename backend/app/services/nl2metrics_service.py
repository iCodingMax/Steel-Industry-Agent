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
import json
import re
import time
from typing import List, Optional, Tuple
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.metric import Metric
from app.models.dimension import Dimension
from app.models.datasource import DataSource
from app.services.llm_service import llm_service
from app.services.nl2sql_service import NL2SQLEngine


class _MatchBreaker:
    """
    指标匹配熔断器（进程内状态，轻量实现）

    背景：指标库存在但用户问题均与指标无关时，每次查询仍会白白消耗一次
    指标匹配 LLM 调用（约1-3秒）。熔断器在连续多次无匹配后跳过匹配，
    直接落入 NL2SQL 兜底；指标库发生增删改时由 MetricService 重置熔断。

    规则：
    - 连续 consecutive_limit 次无匹配 → 进入熔断，breaker_open=True
    - 熔断后 cooldown_seconds 内所有查询跳过指标匹配
    - 冷却期结束后放行一次探测查询（半开状态），命中则恢复，否则继续熔断
    """

    def __init__(self, consecutive_limit: int = 5, cooldown_seconds: float = 600.0):
        self.consecutive_limit = consecutive_limit
        self.cooldown_seconds = cooldown_seconds
        self._miss_streak = 0          # 连续无匹配计数
        self._open_until = 0.0         # 熔断截止时间戳（0=未熔断）

    def should_skip(self) -> bool:
        """判断当前是否应跳过指标匹配（熔断生效中）"""
        if self._open_until == 0.0:
            return False
        if time.time() >= self._open_until:
            # 冷却期结束：进入半开状态，放行本次作为探测查询
            self._open_until = 0.0
            logger.info("指标匹配熔断冷却结束，进入半开状态放行探测")
            return False
        return True

    def record_miss(self) -> None:
        """记录一次无匹配；连续无匹配达到阈值时开启熔断"""
        self._miss_streak += 1
        if self._miss_streak >= self.consecutive_limit:
            self._open_until = time.time() + self.cooldown_seconds
            self._miss_streak = 0
            logger.warning(
                f"指标连续{self.consecutive_limit}次无匹配，熔断{self.cooldown_seconds}秒"
                f"（期间跳过指标匹配直接走NL2SQL，指标库变更时自动重置）"
            )

    def record_hit(self) -> None:
        """记录一次命中，恢复计数"""
        self._miss_streak = 0

    def reset(self) -> None:
        """重置熔断状态（指标库增删改时调用）"""
        self._miss_streak = 0
        self._open_until = 0.0


# 模块级熔断器实例（进程内共享）
match_breaker = _MatchBreaker()


class NL2MetricsEngine:
    """
    NL2Metrics指标查询引擎
    通过自然语言匹配预定义指标，生成精确的SQL查询语句
    优先于NL2SQL执行，提高查询效率和准确性
    """

    # 指标向量召回参数（方案8）：候选池大小与相似度阈值
    METRIC_RECALL_CANDIDATES = 8
    METRIC_RECALL_SIM_THRESHOLD = 0.5

    @staticmethod
    async def _vector_recall_metrics(
        db: AsyncSession,
        question: str,
        candidate_limit: int,
    ) -> Optional[List[Metric]]:
        """
        指标向量召回（方案8）：问题向量 Top-K 候选，供 LLM 精选

        降级规则（返回 None 表示"向量不可用，调用方回退全量 LLM 匹配"）：
            - Metric.embedding 列缺失（pgvector 未安装，降级占位列定义仍存在，此判断保底）
            - 问题向量化失败
            - 检索异常
        过滤规则：status=active 且 embedding 非空，余弦相似度降序取前 candidate_limit
        """
        if Metric.embedding is None:
            return None
        try:
            from pgvector.sqlalchemy import Vector  # noqa: F401 驱动可用性探测
            from app.services.sql_example_service import SqlExampleService
            query_vec = await SqlExampleService._embed_question(question.strip())
            if query_vec is None:
                return None
            sim_expr = 1.0 - Metric.embedding.cosine_distance(query_vec)
            stmt = (
                select(Metric)
                .where(
                    Metric.status == "active",
                    Metric.embedding.is_not(None),
                )
                .order_by(sim_expr.desc())
                .limit(candidate_limit)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return list(rows) if rows else []
        except ImportError:
            logger.warning("[NL2Metrics] pgvector未安装，指标向量召回降级为LLM全量匹配")
            return None
        except Exception as e:
            logger.warning(f"[NL2Metrics] 指标向量召回异常，回退LLM全量匹配: {type(e).__name__}: {e}")
            return None

    @staticmethod
    async def match_metrics(
        db: AsyncSession,
        question: str,
        top_k: int = 3,
    ) -> List[Tuple[Metric, float]]:
        """
        匹配相关指标（方案8：向量召回 Top-K 候选 → LLM 语义精选）

        流程：
            1. 向量召回：问题向量化，与指标召回键（名称+描述+标签）余弦相似度 Top-K 候选
            2. LLM 精选：候选列表远小于全量，Prompt 精简、匹配更快更准
            3. 无匹配返回空列表（触发熔断计数）

        降级：向量不可用（pgvector 缺失/检索异常）时回退 LLM 全量指标匹配（原逻辑）

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

        # 方案8：优先向量召回缩小候选池，失败/无候选回退全量
        recall_metrics = await NL2MetricsEngine._vector_recall_metrics(
            db, question, NL2MetricsEngine.METRIC_RECALL_CANDIDATES
        )
        if recall_metrics:
            metrics = recall_metrics
            logger.info(
                f"[NL2Metrics] 向量召回候选: {len(metrics)}个（相似度Top-{NL2MetricsEngine.METRIC_RECALL_CANDIDATES}）"
            )
        elif recall_metrics == []:
            # 有向量基础设施但无任何召回候选（可能存量指标均未向量化）
            logger.info("[NL2Metrics] 向量召回无候选（存量指标未向量化），回退LLM全量匹配")
        # recall_metrics 为 None 时：pgvector 缺失或检索异常，同样回退全量

        # 构建指标列表文本，包含查询表名，用于LLM语义匹配
        metric_list = "\n".join([
            f"- {m.name}: {m.description} (分组: {m.group_name}, 查询表: {NL2MetricsEngine._extract_table_name(m.sql_expression)})"
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

重要：请结合指标的"查询表"和"描述"进行判断，确保匹配的指标所查询的数据表与用户问题语义一致。
例如：用户问"矿石化验数据"时，应匹配查询表包含"lab_ingredient"的指标，而非查询"condition_result"表的指标。

如果没有任何指标与用户问题相关，请返回"无匹配"。
只返回指标名称或"无匹配"，不要返回其他内容。"""

        # 调用LLM进行匹配
        response = await llm_service.chat(prompt)
        matched_names = [line.strip() for line in response.strip().split("\n") if line.strip()]

        # 检查是否无匹配
        if matched_names and "无匹配" in matched_names[0]:
            logger.info(f"LLM判断无匹配指标: 问题={question[:50]}...")
            return []

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
    def _extract_table_name(sql: str) -> str:
        """
        从SQL表达式中提取主表名

        :param sql: SQL表达式
        :return: 表名（提取失败返回空字符串）
        """
        if not sql:
            return ""
        import re
        match = re.search(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

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

    # 方案7：数据库日期类型前缀（覆盖 MySQL/PostgreSQL/SQLServer 常见类型）
    _DATE_TYPE_PREFIXES = ("date", "datetime", "timestamp", "time")

    @staticmethod
    async def _load_date_columns(db: AsyncSession, datasource_id) -> set:
        """
        从 TableSchema 加载数据源下所有日期类型列（方案7：替代硬编码列名白名单）

        识别规则：columns JSON 中列 type 以 date/datetime/timestamp/time 开头
        （不区分大小写，覆盖 MySQL/PostgreSQL/SQLServer 常见日期类型）。
        降级：数据源未绑定 / Schema 缺失 / 解析异常 → 空集合（回退 data_type 判断）。

        :return: {(table_name, column_name)} 集合（均小写）
        """
        if datasource_id is None:
            return set()
        try:
            from app.models.datasource import TableSchema
            stmt = select(TableSchema.table_name, TableSchema.columns).where(
                TableSchema.datasource_id == datasource_id
            )
            rows = (await db.execute(stmt)).all()
            date_cols = set()
            for table_name, columns_data in rows:
                columns = []
                if isinstance(columns_data, str):
                    try:
                        columns = json.loads(columns_data) if columns_data else []
                    except Exception:
                        columns = []
                elif isinstance(columns_data, list):
                    columns = columns_data
                for col in columns:
                    col_type = str(col.get("type", "") or "").lower()
                    if col_type.startswith(NL2MetricsEngine._DATE_TYPE_PREFIXES):
                        col_name = str(col.get("name", "") or "").lower()
                        if col_name:
                            date_cols.add((str(table_name).lower(), col_name))
            if date_cols:
                logger.debug(f"[方案7] Schema日期列识别: {len(date_cols)}个（数据源{datasource_id}）")
            return date_cols
        except Exception as e:
            logger.warning(f"[方案7] Schema日期列加载异常(回退data_type判断): {type(e).__name__}: {e}")
            return set()

    @staticmethod
    def _is_date_dimension(dim: Dimension, date_columns: set) -> bool:
        """
        判断维度是否为日期维度（方案7）

        判定优先级：
            1. 维度自身 data_type == "date"（人工录入语义类型）
            2. Schema 列类型命中日期类型集合（真实物理类型）
            3. 兜底：常见日期列名约定（列名以 date/time 结尾或等于 date）
        """
        # 1. 语义类型
        if (dim.data_type or "").lower() == "date":
            return True
        # 2. Schema 物理类型（表名+列名二元组匹配；列名全局唯一场景直接命中）
        col_lower = (dim.column_name or "").lower()
        table_lower = (dim.table_name or "").lower()
        if (table_lower, col_lower) in date_columns:
            return True
        # 3. 列名约定兜底（Schema 缺失/未同步场景）
        return col_lower.endswith("_date") or col_lower.endswith("date") or col_lower.endswith("_time") or col_lower == "time"

    @staticmethod
    def _remove_time_filter_from_template(sql: str) -> str:
        """
        从SQL模板中移除时间过滤条件（包含{start_date}和{end_date}占位符的条件）

        当用户未指定时间范围时，移除模板中的时间过滤条件，避免默认添加时间限制。

        :param sql: 包含{start_date}和{end_date}占位符的SQL模板
        :return: 移除时间过滤条件后的SQL语句

        处理模式：
            1. AND field >= '{start_date}' AND field < '{end_date}'（前面有其他WHERE条件）
            2. WHERE field >= '{start_date}' AND field < '{end_date}' AND（后面有其他条件）
            3. WHERE field >= '{start_date}' AND field < '{end_date}'（唯一的WHERE条件）
            4. BETWEEN '{start_date}' AND '{end_date}' 模式
            5. 兜底：无法匹配时使用极宽日期范围（1900~2999）
        """
        # 模式1: 移除 AND 连接的时间条件（前面有其他WHERE条件）
        sql = re.sub(
            r"\s+AND\s+\w+\s*>=?\s*['\"]?\{start_date\}['\"]?\s+AND\s+\w+\s*<=?\s*['\"]?\{end_date\}['\"]?",
            "",
            sql,
            flags=re.IGNORECASE
        )

        # 模式2: 移除 WHERE + 时间条件 + AND（后面有其他条件）
        sql = re.sub(
            r"\s+WHERE\s+\w+\s*>=?\s*['\"]?\{start_date\}['\"]?\s+AND\s+\w+\s*<=?\s*['\"]?\{end_date\}['\"]?\s+AND\b",
            " WHERE",
            sql,
            flags=re.IGNORECASE
        )

        # 模式3: 移除 WHERE + 时间条件（唯一的WHERE条件）
        sql = re.sub(
            r"\s+WHERE\s+\w+\s*>=?\s*['\"]?\{start_date\}['\"]?\s+AND\s+\w+\s*<=?\s*['\"]?\{end_date\}['\"]?",
            "",
            sql,
            flags=re.IGNORECASE
        )

        # 模式4: 处理 BETWEEN 模式
        sql = re.sub(
            r"\s+AND\s+\w+\s+BETWEEN\s*['\"]?\{start_date\}['\"]?\s+AND\s+['\"]?\{end_date\}['\"]?",
            "",
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r"\s+WHERE\s+\w+\s+BETWEEN\s*['\"]?\{start_date\}['\"]?\s+AND\s+['\"]?\{end_date\}['\"]?\s+AND\b",
            " WHERE",
            sql,
            flags=re.IGNORECASE
        )
        sql = re.sub(
            r"\s+WHERE\s+\w+\s+BETWEEN\s*['\"]?\{start_date\}['\"]?\s+AND\s+['\"]?\{end_date\}['\"]?",
            "",
            sql,
            flags=re.IGNORECASE
        )

        # 清理残留语法（空WHERE、WHERE AND等）
        sql = re.sub(r"\s+WHERE\s+(ORDER|GROUP|LIMIT|;|$)", r" \1", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\s+WHERE\s+AND\b", " WHERE", sql, flags=re.IGNORECASE)

        # 兜底：如果仍有残留占位符，使用极宽日期范围
        if "{start_date}" in sql or "{end_date}" in sql:
            logger.warning("无法完全移除时间过滤条件，使用极宽日期范围兜底")
            sql = sql.replace("{start_date}", "1900-01-01").replace("{end_date}", "2999-12-31")

        sql = " ".join(sql.split())
        return sql

    @staticmethod
    async def generate_sql(
        db: AsyncSession,
        metric: Metric,
        dimensions: List[Tuple[Dimension, str]],
        question: str = "",
    ) -> str:
        """
        生成指标查询SQL
        根据指标模板和维度条件生成最终的SQL查询语句

        :param db: 数据库会话
        :param metric: 目标指标（包含SQL模板）
        :param dimensions: 维度过滤条件列表
        :param question: 用户原始问题（用于时间范围解析）
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

        # 方案7：从 TableSchema 读取维度绑定列的真实类型，构建日期列集合
        # （替代原硬编码列名白名单 PRODUCE_DATE/DATE/CREATED_AT/HEAT_DATE）
        date_columns = await NL2MetricsEngine._load_date_columns(db, metric.datasource_id)

        # 分离日期维度和非日期维度
        date_dims = []
        other_dims = []
        for dim, value in dimensions:
            if NL2MetricsEngine._is_date_dimension(dim, date_columns):
                date_dims.append((dim, value))
            else:
                other_dims.append((dim, value))

        logger.debug(f"日期维度: {len(date_dims)}, 非日期维度: {len(other_dims)}")

        # 日期解析工具函数
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
        # 优先从原始问题解析时间范围（比LLM维度提取更准确）
        question_time_range = NL2SQLEngine._parse_time_range(question) if question else None

        if question_time_range:
            # 从原始问题成功解析时间范围
            start_date = question_time_range["start"]
            end_date = question_time_range["end"]
            base_sql = base_sql.replace("{start_date}", start_date).replace("{end_date}", end_date)
            logger.debug(f"从问题解析时间范围: {start_date} ~ {end_date}")
        elif date_dims:
            # 回退到维度提取的日期值
            _, date_val = date_dims[0]
            start_date, end_date = parse_date_value(date_val)
            if start_date and end_date:
                base_sql = base_sql.replace("{start_date}", start_date).replace("{end_date}", end_date)
                logger.debug(f"日期替换完成: {start_date} ~ {end_date}")
            else:
                # 解析失败，移除时间过滤条件
                base_sql = NL2MetricsEngine._remove_time_filter_from_template(base_sql)
                # 将日期维度作为普通条件追加
                other_dims.extend(date_dims)
                logger.debug("日期解析失败，已移除时间过滤条件")
        else:
            # 没有用户指定时间，移除SQL模板中的时间过滤条件
            base_sql = NL2MetricsEngine._remove_time_filter_from_template(base_sql)
            logger.debug("用户未指定时间，已移除时间过滤条件")

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

        # 熔断检查：近期连续无匹配时跳过指标匹配，直接落入NL2SQL兜底
        if match_breaker.should_skip():
            logger.info("指标匹配熔断生效中，跳过NL2Metrics直接走NL2SQL")
            return None, None, None

        try:
            # 步骤1：匹配指标（使用LLM语义匹配）
            matched_metrics = await NL2MetricsEngine.match_metrics(db, question)
            if not matched_metrics:
                logger.info("NL2Metrics查询失败: 未匹配到指标")
                match_breaker.record_miss()
                return None, None, None

            match_breaker.record_hit()
            metric, score = matched_metrics[0]
            logger.debug(f"匹配到指标: {metric.name}, 分数={score}")

            # 步骤2：提取维度过滤条件
            dimensions = await NL2MetricsEngine.extract_dimensions(db, question, metric)
            logger.debug(f"提取到维度条件: {len(dimensions)}个")

            # 步骤3：生成SQL语句
            sql = await NL2MetricsEngine.generate_sql(db, metric, dimensions, question)

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