"""
NL2SQL兜底引擎

本模块提供钢铁行业智能问数的NL2SQL能力，支持将自然语言转换为SQL查询语句。

主要组件：
1. json_safe: JSON安全序列化工具函数
   - 处理不可序列化的类型（datetime、Decimal、UUID等）

2. SQLSecurityFilter: SQL安全过滤器
   - 拦截危险操作（DROP/DELETE/TRUNCATE等）
   - 清理SQL语句（移除注释、多余空格）

3. SQLValidator: SQL语法校验器
   - 使用sqlglot校验SQL语法
   - 确保只允许SELECT查询

4. SchemaLinkingEngine: Schema Linking引擎
   - 从用户问题识别需要的表和字段
   - 精简Schema描述，减少Prompt长度

5. NL2SQLEngine: NL2SQL引擎（核心）
   - 智能表筛选（基于钢铁行业关键词）
   - 生成SQL语句（通过Xinference调用LLM）
   - 校验并执行SQL
   - 获取字段元信息

关键技术点：
- 使用Xinference作为LLM服务
- 智能表筛选：基于钢铁行业关键词匹配相关表
- Schema Linking：使用LLM识别相关表，减少Schema大小
- 安全过滤：拦截危险操作，只允许SELECT查询
- 执行控制：超时限制30秒、返回行数限制1000行
- 自动重试：一周过滤无数据时自动放宽时间范围
"""
import re
import json
import datetime
import decimal
import uuid
import sqlglot
from typing import List, Optional, Tuple, Any
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.datasource import DataSource, TableSchema
from app.models.term import Term
from app.services.llm_service import llm_service
from app.middlewares.exception_handler import BusinessException


def json_safe(obj: Any) -> Any:
    """
    递归处理JSON不可序列化的类型

    在将数据库查询结果转换为JSON时，某些类型（如datetime、Decimal）无法直接序列化，
    需要进行转换处理。

    :param obj: 需要处理的对象
    :return: 可序列化的对象

    支持的类型转换：
        - datetime.datetime → "YYYY-MM-DD HH:MM:SS"
        - datetime.date → "YYYY-MM-DD"
        - datetime.time → "HH:MM:SS"
        - decimal.Decimal → float
        - uuid.UUID → str
        - bytes → str（UTF-8解码，错误用replace）
        - dict → 递归处理每个键值对
        - list/tuple → 递归处理每个元素
        - 其他 → 原样返回
    """
    if isinstance(obj, datetime.datetime):
        return obj.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(obj, datetime.date):
        return obj.strftime("%Y-%m-%d")
    elif isinstance(obj, datetime.time):
        return obj.strftime("%H:%M:%S")
    elif isinstance(obj, decimal.Decimal):
        return float(obj)
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    elif isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [json_safe(item) for item in obj]
    else:
        return obj


class SQLSecurityFilter:
    """
    SQL安全过滤器

    防止恶意SQL注入和危险操作，确保系统安全。

    属性：
        DANGEROUS_PATTERNS: 禁止的危险操作关键词列表
            - DROP: 删除表
            - DELETE: 删除数据
            - TRUNCATE: 清空表
            - ALTER: 修改表结构
            - CREATE: 创建对象
            - INSERT: 插入数据
            - UPDATE: 更新数据
            - GRANT/REVOKE: 权限管理
            - EXEC/EXECUTE: 执行存储过程
            - xp_*/sp_*: 系统存储过程
    """

    # 禁止的危险操作关键词（使用正则表达式进行边界匹配）
    DANGEROUS_PATTERNS = [
        (r"\bDROP\b", "DROP"),
        (r"\bDELETE\b", "DELETE"),
        (r"\bTRUNCATE\b", "TRUNCATE"),
        (r"\bALTER\b", "ALTER"),
        (r"\bCREATE\b", "CREATE"),
        (r"\bINSERT\b", "INSERT"),
        (r"\bUPDATE\b", "UPDATE"),
        (r"\bGRANT\b", "GRANT"),
        (r"\bREVOKE\b", "REVOKE"),
        (r"\bEXEC\b", "EXEC"),
        (r"\bEXECUTE\b", "EXECUTE"),
        (r"\bxp_\w+", "xp_存储过程"),
        (r"\bsp_\w+", "sp_存储过程"),
    ]

    @staticmethod
    def check(sql: str) -> Tuple[bool, str]:
        """
        检查SQL安全性

        检查SQL语句是否包含危险操作或多条语句。

        :param sql: SQL语句
        :return: (是否安全, 错误信息)

        检查逻辑：
            1. 将SQL转换为大写（便于匹配）
            2. 遍历DANGEROUS_PATTERNS，使用正则匹配
            3. 如果匹配到危险关键词，返回False和错误信息
            4. 检查是否包含多条SQL语句（分号不在末尾）
            5. 通过检查返回True和空字符串
        """
        sql_upper = sql.upper()

        for pattern, keyword in SQLSecurityFilter.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper):
                logger.warning(f"SQL安全检查失败: 包含危险操作 '{keyword}'")
                return False, f"SQL包含危险操作: {keyword}"

        if ";" in sql and not sql.strip().endswith(";"):
            logger.warning(f"SQL安全检查失败: 包含多条语句")
            return False, "SQL包含多条语句，禁止执行"

        return True, ""

    @staticmethod
    def sanitize(sql: str) -> str:
        """
        清理SQL语句

        移除SQL中的注释和多余空格，确保语句干净。

        :param sql: 原始SQL语句
        :return: 清理后的SQL语句

        清理步骤：
            1. 移除单行注释（--开头）
            2. 移除多行注释（/*...*/）
            3. 移除多余空格（多个空格合并为一个）
            4. 去除首尾空格
        """
        # 移除单行注释
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        # 移除多行注释
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        # 移除多余空格
        sql = " ".join(sql.split())
        return sql.strip()


class SQLValidator:
    """
    SQL语法校验器

    使用sqlglot库校验SQL语法的正确性，并确保只允许SELECT查询。

    校验流程：
        1. 使用sqlglot解析SQL语句
        2. 检查解析结果是否为空
        3. 检查SQL类型是否为SELECT
        4. 返回校验结果
    """

    @staticmethod
    def validate(sql: str, dialect: str = "mysql") -> Tuple[bool, str]:
        """
        校验SQL语法

        :param sql: SQL语句
        :param dialect: 数据库方言（mysql/postgres/sqlite）
        :return: (是否合法, 错误信息)

        校验逻辑：
            1. 使用sqlglot.parse()解析SQL
            2. 如果解析结果为空，返回失败
            3. 如果解析结果是列表且不为空，检查第一个语句的类型
            4. 只允许SELECT类型，其他类型返回失败
            5. 任何异常都返回失败并记录错误信息
        """
        try:
            parsed = sqlglot.parse(sql, dialect=dialect)
            
            if not parsed:
                return False, "SQL解析失败"

            if isinstance(parsed, list) and len(parsed) > 0:
                stmt_key = parsed[0].key
                if not stmt_key or stmt_key.upper() != "SELECT":
                    return False, f"只允许执行SELECT查询，当前类型: {stmt_key}"
            else:
                return False, "SQL解析结果格式异常"

            return True, ""

        except Exception as e:
            logger.error(f"SQL校验异常: {e}")
            return False, f"SQL语法错误: {str(e)}"


class SchemaLinkingEngine:
    """
    Schema Linking引擎（轻量级，只筛选相关表）

    从用户问题中识别需要查询的表，减少传递给LLM的Schema大小，
    提高SQL生成的准确性和效率。

    工作原理：
        1. 获取数据源的所有表结构
        2. 构建精简的Schema描述（只包含表名和注释）
        3. 使用LLM从表列表中选择与问题相关的表
        4. 返回关联的表名列表
    """

    @staticmethod
    async def link(
        db: AsyncSession,
        question: str,
        datasource_id: int,
    ) -> List[Tuple[str, str]]:
        """
        从问题识别需要的表和字段

        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :return: [(表名, 字段名)] - 字段名为空表示所有字段

        流程步骤：
            1. 获取数据源的所有表结构（过滤系统内部表）
            2. 构建精简的Schema描述（表名 + 表注释）
            3. 使用LLM选择与问题相关的表（最多3个）
            4. 解析LLM返回的表名列表
            5. 返回关联结果（表名, 空字段表示所有字段）
        """
        # 获取数据源Schema（过滤系统内部表）
        stmt = select(TableSchema).where(TableSchema.datasource_id == datasource_id)
        result = await db.execute(stmt)
        schemas = [
            s for s in result.scalars().all()
            if s.table_name not in NL2SQLEngine.SYSTEM_TABLES
        ]

        if not schemas:
            logger.warning(f"Schema Linking: 数据源ID={datasource_id}无可用表")
            return []

        # 构建轻量级Schema描述（只包含表名和注释）
        schema_desc = []
        for schema in schemas:
            table_comment = schema.table_comment or ""
            schema_desc.append(f"- {schema.table_name}: {table_comment}" if table_comment else f"- {schema.table_name}")

        schema_text = "\n".join(schema_desc)

        # 使用LLM识别相关表（精简Prompt）
        prompt = f"""从以下数据库表中选择与用户问题相关的表（最多3个）。

可用表：
{schema_text}

用户问题：{question}

只返回相关表名，用逗号分隔。例如：table1,table2"""

        response = await llm_service.chat(prompt)

        # 解析结果（只提取表名）
        linked_tables = []
        for table_name in response.strip().replace(" ", "").split(","):
            table_name = table_name.strip()
            if table_name:
                linked_tables.append(table_name)
        
        # 返回链接结果（表名, 空字段表示所有字段）
        links = [(table, "") for table in linked_tables]
        
        logger.info(f"Schema Linking完成: 问题={question[:30]}..., 相关表={linked_tables}")
        return links


class NL2SQLEngine:
    """
    NL2SQL引擎

    将自然语言问题转换为SQL查询语句，并执行查询。
    支持智能表筛选、安全过滤、语法校验和自动重试。

    属性：
        EXEC_TIMEOUT: 执行超时时间（秒），默认30秒
        MAX_ROWS: 最大返回行数，默认1000行
        SYSTEM_TABLES: 系统内部表集合，不应出现在NL2SQL的Schema中

    核心流程：
        1. 获取数据源信息和Schema
        2. 智能表筛选（基于关键词匹配）
        3. Schema Linking进一步筛选（如果表数量>3）
        4. 构建完整的Schema描述（包含字段注释）
        5. 构建术语提示
        6. 调用LLM生成SQL
        7. 安全检查和语法校验
        8. 执行SQL
        9. 自动重试（一周过滤无数据时放宽时间范围）
    """

    EXEC_TIMEOUT = 30  # 执行超时（秒）
    MAX_ROWS = 1000  # 最大返回行数

    # 系统内部表，不应出现在NL2SQL的Schema中
    SYSTEM_TABLES = {
        "users", "sessions", "messages", "datasources", "table_schemas",
        "metrics", "dimensions", "terms", "knowledge_bases", "documents",
        "document_segments", "llm_configs",
    }

    @staticmethod
    def _parse_time_range(question: str) -> Optional[dict]:
        """
        从中文问题中解析时间范围

        解析规则：
        - "2023年8月" -> 2023-08-01 到 2023-09-01
        - "2023年" -> 2023-01-01 到 2024-01-01
        - "8月" -> 当前年份的8月1日到9月1日
        - "2023年8月15日" -> 2023-08-15 到 2023-08-16
        - "2023年8月第一周" -> 2023-08-01 到 2023-08-08
        - "最近一周" -> 7天前到今天
        - "本月" -> 本月1日到下个月1日

        :param question: 用户问题
        :return: {"start": "2023-08-01", "end": "2023-09-01", "field": "PRODUCE_DATE"} 或 None
        """
        today = datetime.date.today()
        current_year = today.year
        
        # 匹配模式：从具体到一般
        patterns = [
            # YYYY年MM月DD日
            (r'(\d{4})年(\d{1,2})月(\d{1,2})日', lambda m: (
                datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))),
                datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) + datetime.timedelta(days=1)
            )),
            # YYYY年MM月第N周
            (r'(\d{4})年(\d{1,2})月第([一二三四五六日])周', lambda m: (
                datetime.date(int(m.group(1)), int(m.group(2)), 1),
                datetime.date(int(m.group(1)), int(m.group(2)), 8)
            )),
            # YYYY年MM月
            (r'(\d{4})年(\d{1,2})月(?!份)', lambda m: _get_month_range(int(m.group(1)), int(m.group(2)))),
            # YYYY年
            (r'(\d{4})年(?!.*月)', lambda m: (
                datetime.date(int(m.group(1)), 1, 1),
                datetime.date(int(m.group(1)) + 1, 1, 1)
            )),
            # MM月DD日
            (r'(\d{1,2})月(\d{1,2})日', lambda m: (
                datetime.date(current_year, int(m.group(1)), int(m.group(2))),
                datetime.date(current_year, int(m.group(1)), int(m.group(2))) + datetime.timedelta(days=1)
            )),
            # MM月 (没有年份，使用当前年份)
            (r'(\d{1,2})月(?!.*日)', lambda m: _get_month_range(current_year, int(m.group(1)))),
            # 最近一周
            (r'最近(一|1)周|过去(一|1)周', lambda m: (
                today - datetime.timedelta(days=7),
                today + datetime.timedelta(days=1)
            )),
            # 本周
            (r'本周', lambda m: (
                today - datetime.timedelta(days=today.weekday()),
                today + datetime.timedelta(days=7 - today.weekday())
            )),
            # 本月
            (r'本月', lambda m: (
                datetime.date(current_year, today.month, 1),
                _get_next_month_start(current_year, today.month)
            )),
            # 最近N天
            (r'最近(\d+)天', lambda m: (
                today - datetime.timedelta(days=int(m.group(1))),
                today + datetime.timedelta(days=1)
            )),
        ]

        def _get_month_range(year: int, month: int):
            """获取月份的起止日期"""
            if month == 12:
                return (
                    datetime.date(year, 12, 1),
                    datetime.date(year + 1, 1, 1)
                )
            else:
                return (
                    datetime.date(year, month, 1),
                    datetime.date(year, month + 1, 1)
                )

        def _get_next_month_start(year: int, month: int):
            """获取下个月的第一天"""
            if month == 12:
                return datetime.date(year + 1, 1, 1)
            else:
                return datetime.date(year, month + 1, 1)

        for pattern, extractor in patterns:
            match = re.search(pattern, question)
            if match:
                try:
                    start_date, end_date = extractor(match)
                    return {
                        "start": start_date.strftime("%Y-%m-%d"),
                        "end": end_date.strftime("%Y-%m-%d"),
                    }
                except (ValueError, TypeError):
                    continue

        return None

    @staticmethod
    def _build_sql_prompt(
        schema_text: str,
        term_text: str,
        question: str,
    ) -> str:
        """
        构建SQL生成的Prompt（不调用LLM）

        根据数据库Schema、业务术语和用户问题，构建用于生成SQL的Prompt。

        :param schema_text: 数据库Schema描述（DDL格式）
        :param term_text: 业务术语映射（可选）
        :param question: 用户问题
        :return: SQL生成Prompt

        Prompt结构：
            - 角色定义：钢铁行业数据分析SQL专家
            - 数据库Schema（DDL格式，包含字段注释）
            - 业务术语映射（可选）
            - 用户问题
            - 解析后的时间范围（如果有）
            - 生成要求（8条规则）

        生成要求：
            1. 只生成SELECT查询语句
            2. 严格使用Schema中存在的表名和字段名
            3. 根据用户问题添加适当的WHERE条件和聚合函数
            4. 时间范围处理：使用代码解析的时间范围，确保准确性
            5. 限制返回行数不超过MAX_ROWS
            6. 为查询字段和聚合结果添加中文别名
            7. ORDER BY子句中使用中文别名排序
            8. 只返回纯SQL语句，不要包含markdown代码块标记
        """
        # 使用代码解析时间范围，确保准确性
        time_range = NL2SQLEngine._parse_time_range(question)
        
        # 构建时间范围指令
        time_instruction = ""
        if time_range:
            time_instruction = f"""4. 时间范围处理（必须严格执行）：
   - 用户指定的时间范围已解析为：PRODUCE_DATE >= '{time_range['start']}' AND PRODUCE_DATE < '{time_range['end']}'
   - 你必须使用这个精确的时间范围，不要修改或猜测
   - 在WHERE子句中添加：PRODUCE_DATE >= '{time_range['start']}' AND PRODUCE_DATE < '{time_range['end']}'
"""
        else:
            time_instruction = """4. 时间范围处理：
   - 用户问题中没有明确的时间范围，不要在WHERE子句中添加任何时间过滤条件
"""
        
        return f"""你是一个钢铁行业数据分析SQL专家。请根据用户问题和数据库Schema，生成一个MySQL SELECT查询语句。

数据库Schema（DDL格式，字段注释即中文名称）：
{schema_text}
{term_text}

用户问题：{question}

要求：
1. 只生成SELECT查询语句，禁止使用INSERT/UPDATE/DELETE/DROP等操作
2. 严格使用Schema中存在的表名和字段名，不要编造
3. 根据用户问题添加适当的WHERE条件和聚合函数
{time_instruction}
5. 限制返回行数不超过{NL2SQLEngine.MAX_ROWS}行（使用LIMIT）
6. 为每个查询字段和聚合结果添加中文别名（AS子句），别名优先使用字段COMMENT中的中文名称；聚合函数使用语义化中文别名，如SUM(BLOW_COUNT) AS 总吹炼次数。如果别名以数字开头或包含特殊字符（如连字符-），必须用反引号括起来，例如：AS `40-25`、AS `16以上`、AS `10-5`
7. ORDER BY子句中也使用中文别名排序
8. 只返回纯SQL语句，不要包含markdown代码块标记或解释文字

请直接返回SQL语句："""

    @staticmethod
    def _validate_and_fix_sql_time_range(sql: str, question: str) -> str:
        """
        验证并修正SQL中的时间范围

        当用户指定了时间范围时，检查SQL中的时间范围是否正确，
        如果不正确（如只有一天而不是一个月），则进行修正。

        :param sql: LLM生成的SQL语句
        :param question: 用户问题
        :return: 修正后的SQL语句
        """
        # 解析用户问题中的时间范围
        time_range = NL2SQLEngine._parse_time_range(question)
        
        if not time_range:
            return sql  # 没有指定时间范围，直接返回
        
        expected_start = time_range["start"]
        expected_end = time_range["end"]
        
        # 查找SQL中现有的时间范围条件
        # 匹配模式: 字段 >= '日期' AND 字段 < '日期'
        time_pattern = r"([a-zA-Z_]+)\s*>=\s*['\"](\d{4}-\d{2}-\d{2})['\"]\s*AND\s+\1\s*<\s*['\"](\d{4}-\d{2}-\d{2})['\"]"
        match = re.search(time_pattern, sql, re.IGNORECASE)
        
        if match:
            field_name = match.group(1)
            current_start = match.group(2)
            current_end = match.group(3)
            
            # 检查时间范围是否正确
            if current_start != expected_start or current_end != expected_end:
                logger.warning(
                    f"SQL时间范围不正确: 当前={current_start}~{current_end}, "
                    f"预期={expected_start}~{expected_end}, 正在修正..."
                )
                # 替换为正确的时间范围
                old_condition = f"{field_name} >= '{current_start}' AND {field_name} < '{current_end}'"
                new_condition = f"{field_name} >= '{expected_start}' AND {field_name} < '{expected_end}'"
                sql = sql.replace(old_condition, new_condition)
                logger.info(f"时间范围修正完成: {sql[:150]}...")
        else:
            # 如果没有找到时间范围条件，添加一个
            logger.info(f"SQL中没有时间范围条件，添加预期时间范围: {expected_start}~{expected_end}")
            # 查找WHERE子句
            where_match = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
            if where_match:
                # 在WHERE后面添加时间条件
                where_pos = where_match.end()
                # 检查是否已经有AND条件
                remaining = sql[where_pos:].strip()
                if remaining.upper().startswith('AND'):
                    # 替换第一个AND为我们的时间条件
                    time_condition = f"{field_name} >= '{expected_start}' AND {field_name} < '{expected_end}'"
                    # 需要找到合适的字段名
                    # 从schema中获取或使用默认字段
                    field_match = re.search(r'SELECT\s+.*?FROM\s+(\w+)', sql, re.IGNORECASE)
                    if field_match:
                        # 使用常见的日期字段名
                        time_condition = f"PRODUCE_DATE >= '{expected_start}' AND PRODUCE_DATE < '{expected_end}'"
                    else:
                        time_condition = f"PRODUCE_DATE >= '{expected_start}' AND PRODUCE_DATE < '{expected_end}'"
                    
                    # 插入时间条件
                    sql = sql[:where_pos] + f" {time_condition} AND" + sql[where_pos + 3:]
                else:
                    # 在WHERE后面添加AND时间条件
                    time_condition = f"PRODUCE_DATE >= '{expected_start}' AND PRODUCE_DATE < '{expected_end}'"
                    sql = sql[:where_pos] + f" {time_condition} AND" + sql[where_pos:]
            else:
                # 没有WHERE子句，添加一个
                # 查找FROM子句
                from_match = re.search(r'\bFROM\s+\w+', sql, re.IGNORECASE)
                if from_match:
                    from_end = from_match.end()
                    time_condition = f" WHERE PRODUCE_DATE >= '{expected_start}' AND PRODUCE_DATE < '{expected_end}'"
                    sql = sql[:from_end] + time_condition + sql[from_end:]
        
        return sql

    @staticmethod
    def _fix_time_conflict(sql: str, question: str) -> str:
        """
        修复时间范围冲突：当用户指定了具体时间范围时，移除默认的一周过滤条件

        当LLM生成的SQL同时包含用户指定的时间范围和默认的一周过滤条件时，
        会导致时间范围冲突。此方法检测并移除默认的一周过滤条件。

        :param sql: LLM生成的SQL语句
        :param question: 用户问题
        :return: 修复时间冲突后的SQL语句
        """
        import re
        
        # 检测用户问题中是否包含明确的时间范围
        has_user_time_range = bool(re.search(
            r'(\d{4})年(\d{1,2})月(\d{1,2})日?|'  # YYYY年MM月DD日
            r'(\d{4})年(\d{1,2})月|'  # YYYY年MM月
            r'(\d{4})年|'  # YYYY年
            r'(\d{1,2})月(\d{1,2})日|'  # MM月DD日
            r'(\d{1,2})月|'  # MM月
            r'今日|昨日|今天|昨天|本周|本月|本季度|本年|最近|近期|历史',
            question
        ))
        
        if not has_user_time_range:
            return sql
            
        # 获取今天和一周前的日期
        today = datetime.date.today()
        one_week_ago = today - datetime.timedelta(days=7)
        one_week_ago_str = one_week_ago.strftime("%Y-%m-%d")
        
        # 检查SQL中是否同时包含用户时间范围和默认的一周过滤
        # 查找形如 "时间字段 >= '一周前日期'" 的条件
        week_pattern = rf"AND\s+[a-zA-Z_]+\s*>=\s*['\"]{re.escape(one_week_ago_str)}['\"]"
        
        if re.search(week_pattern, sql, re.IGNORECASE):
            logger.info(f"检测到默认一周过滤条件，用户指定了时间范围，移除冲突条件")
            # 移除默认的一周过滤条件
            sql = re.sub(week_pattern, "", sql, flags=re.IGNORECASE)
            # 清理残留
            sql = " ".join(sql.split())
            logger.info(f"时间冲突修复后SQL: {sql[:100]}...")
        
        return sql

    @staticmethod
    def _fix_alias_quoting(sql: str) -> str:
        """
        修正SQL中未加引号的别名

        当别名以数字开头或包含特殊字符（如连字符-）时，sqlglot解析会失败。
        此方法自动为这类别名添加反引号。

        :param sql: SQL语句
        :return: 修正后的SQL语句

        示例：
            AS 40-25 → AS `40-25`
            AS 16以上 → AS `16以上`
            AS 10-5 → AS `10-5`
        """
        # 匹配 AS 后面紧跟的未加引号别名（以数字开头）
        # 别名持续到遇到空格、逗号、右括号为止
        # 负向先行断言排除已加引号（反引号或双引号）的情况
        pattern = re.compile(r'\bAS\s+(?!["`])(\d[^\s,)]*)', re.IGNORECASE)

        def replace_alias(match):
            alias = match.group(1)
            return f'AS `{alias}`'

        result = pattern.sub(replace_alias, sql)
        if result != sql:
            logger.debug(f"别名引号修正: {sql[:100]}... → {result[:100]}...")
        return result

    @staticmethod
    async def _generate_sql_from_prompt(prompt: str, question: str = "") -> str:
        """
        从Prompt生成SQL（纯LLM调用，不持有数据库会话）

        :param prompt: SQL生成Prompt
        :param question: 用户问题（用于时间冲突检测和验证）
        :return: 清理后的SQL语句

        处理步骤：
            1. 调用LLM生成SQL
            2. 移除markdown代码块标记（```sql或```）
            3. 安全清理（移除注释、多余空格）
            4. 验证并修正时间范围
            5. 修复时间范围冲突
            6. 添加行数限制（如果没有LIMIT子句）
            7. 返回最终SQL
        """
        sql = await llm_service.chat(prompt)
        
        if not sql:
            logger.error("LLM返回SQL为空")
            raise BusinessException(code=500, message="大模型返回的SQL为空")
            
        logger.info(f"LLM原始输出: {repr(sql[:100])}...")

        # 移除markdown代码块标记
        sql = sql.strip()
        if sql.startswith("```sql"):
            sql = sql[5:]
        elif sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()
        logger.info(f"移除代码块标记后SQL: {repr(sql[:100])}...")

        # 清理SQL
        sql = SQLSecurityFilter.sanitize(sql)
        logger.info(f"安全清理后SQL: {repr(sql[:100])}...")

        # 修正未加引号的别名（以数字开头或包含特殊字符的别名）
        sql = NL2SQLEngine._fix_alias_quoting(sql)

        # 验证并修正时间范围（关键步骤）
        if question:
            sql = NL2SQLEngine._validate_and_fix_sql_time_range(sql, question)

        # 修复时间范围冲突
        if question:
            sql = NL2SQLEngine._fix_time_conflict(sql, question)

        # 添加行数限制
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + f" LIMIT {NL2SQLEngine.MAX_ROWS}"
        logger.info(f"最终执行SQL: {sql[:100]}...")

        return sql

    @staticmethod
    def _smart_table_filter(question: str, schemas: List[TableSchema]) -> List[TableSchema]:
        """
        智能表筛选：基于关键词匹配相关表

        根据钢铁行业关键词映射，筛选与用户问题相关的表，减少Schema大小。

        :param question: 用户问题
        :param schemas: 所有表结构列表
        :return: 筛选后的表结构列表

        钢铁行业关键词映射：
            - 转炉/吹炼 → bof_act_heat_add, bof_act_add_sum_add
            - 连铸/浇铸 → cc_heat_report_add
            - 精炼/lf/rh → lf_act_heat_add, lf_act_add_sum_add, rh_act_heat_add, rh_act_add_sum_add
            - 高炉/炉况 → hgbf1_condition_item, hgbf1_condition_result, hgbf1_expert_lab_ingredient, hgbf1_expert_loading_batch, hgbf1_l2_report_hour
            - 加料/物料 → bof_act_add_sum_add, lf_act_add_sum_add, rh_act_add_sum_add, hgbf1_expert_loading_batch
            - 化验/成分 → hgbf1_expert_lab_ingredient
            - 生产/报表 → bof_act_heat_add, cc_heat_report_add, lf_act_heat_add, rh_act_heat_add, hgbf1_l2_report_hour
            - 班次/班别 → bof_act_heat_add, cc_heat_report_add, lf_act_heat_add, rh_act_heat_add

        筛选逻辑：
            1. 将问题转换为小写
            2. 遍历关键词映射，匹配相关表
            3. 如果有匹配的表，只返回这些表
            4. 如果没有匹配，返回所有表
        """
        import re
        
        # 钢铁行业关键词映射表
        KEYWORD_TABLE_MAP = {
            # 转炉炼钢相关
            "转炉|吹炼|bof": ["bof_act_heat_add", "bof_act_add_sum_add"],
            # 连铸相关
            "连铸|浇铸|铸坯|ccm|cast": ["cc_heat_report_add"],
            # 精炼相关
            "精炼|lf|rh": ["lf_act_heat_add", "lf_act_add_sum_add", "rh_act_heat_add", "rh_act_add_sum_add"],
            # 高炉相关
            "高炉|炉况|hgbf": ["hgbf1_condition_item", "hgbf1_condition_result", 
                           "hgbf1_expert_lab_ingredient", "hgbf1_expert_loading_batch",
                           "hgbf1_l2_report_hour"],
            # 物料/加料相关
            "加料|物料|料批": ["bof_act_add_sum_add", "lf_act_add_sum_add", "rh_act_add_sum_add",
                          "hgbf1_expert_loading_batch"],
            # 化验/成分相关
            "化验|成分|元素|ingredient": ["hgbf1_expert_lab_ingredient"],
            # 生产/报表相关
            "生产|报表|统计|heat": ["bof_act_heat_add", "cc_heat_report_add", 
                                 "lf_act_heat_add", "rh_act_heat_add", "hgbf1_l2_report_hour"],
            # 班次相关
            "班次|班别|shift|crew": ["bof_act_heat_add", "cc_heat_report_add", 
                                  "lf_act_heat_add", "rh_act_heat_add"],
        }
        
        question_lower = question.lower()
        matched_tables = set()
        
        # 遍历关键词映射，匹配相关表
        for keywords, tables in KEYWORD_TABLE_MAP.items():
            if re.search(keywords, question_lower):
                matched_tables.update(tables)
        
        # 如果有匹配的表，只返回这些表
        if matched_tables:
            filtered = [s for s in schemas if s.table_name in matched_tables]
            logger.info(f"智能表筛选: 问题={question[:30]}..., 匹配表={len(filtered)}/{len(schemas)}")
            return filtered if filtered else schemas
        
        # 没有匹配，返回所有表
        return schemas

    @staticmethod
    async def generate_sql(
        db: AsyncSession,
        question: str,
        datasource_id: int,
        terms: Optional[List[Term]] = None,
    ) -> str:
        """
        生成SQL语句

        根据用户问题和数据库Schema，生成SQL查询语句。

        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :param terms: 业务术语列表（可选）
        :return: SQL语句

        流程步骤：
            1. 获取数据源信息
            2. 获取Schema（过滤系统内部表）
            3. 智能表筛选（基于关键词匹配）
            4. 如果表数量>3，使用Schema Linking进一步筛选
            5. 构建Schema描述（包含字段注释）
            6. 构建术语提示
            7. 构建Prompt并调用LLM生成SQL
            8. 返回生成的SQL
        """
        # 获取数据源信息
        ds_stmt = select(DataSource).where(DataSource.id == datasource_id)
        ds_result = await db.execute(ds_stmt)
        datasource = ds_result.scalar_one_or_none()

        if not datasource:
            raise BusinessException(code=404, message="数据源不存在")

        # 获取Schema（过滤系统内部表）
        schema_stmt = select(TableSchema).where(TableSchema.datasource_id == datasource_id)
        schema_result = await db.execute(schema_stmt)
        all_schemas = [
            s for s in schema_result.scalars().all()
            if s.table_name not in NL2SQLEngine.SYSTEM_TABLES
        ]
        
        # 智能表筛选（基于关键词匹配）
        schemas = NL2SQLEngine._smart_table_filter(question, all_schemas)
        
        # 如果筛选后表数量仍然>3，使用Schema Linking进一步筛选
        if len(schemas) > 3:
            try:
                links = await SchemaLinkingEngine.link(db, question, datasource_id)
                if links:
                    # 提取相关表名
                    linked_tables = set([link[0] for link in links])
                    schemas = [s for s in schemas if s.table_name in linked_tables]
                    logger.info(f"Schema Linking筛选后: 表数量={len(schemas)}")
            except Exception as e:
                logger.warning(f"Schema Linking失败，使用智能筛选结果: {e}")

        # 构建Schema描述（包含字段注释，便于LLM生成中文别名）
        schema_desc = []
        for schema in schemas:
            # 兼容JSONB自动反序列化(list)和旧数据(JSON字符串)
            columns_data = schema.columns
            if isinstance(columns_data, str):
                columns = json.loads(columns_data) if columns_data else []
            elif isinstance(columns_data, list):
                columns = columns_data
            else:
                columns = []
            col_info = []
            for col in columns:
                col_type = col['type']
                col_comment = col.get('comment', '') or col.get('remarks', '') or ''
                if col_comment:
                    col_info.append(f"{col['name']}({col_type}) COMMENT '{col_comment}'")
                else:
                    col_info.append(f"{col['name']}({col_type})")
            schema_desc.append(f"CREATE TABLE {schema.table_name} ({', '.join(col_info)})")

        schema_text = "\n".join(schema_desc)
        logger.debug(f"Schema描述长度: {len(schema_text)}字符")

        # 构建术语提示
        term_text = ""
        if terms:
            term_lines = []
            for t in terms:
                synonyms_list = json.loads(t.synonyms) if t.synonyms else []
                synonyms_str = "、".join(synonyms_list)
                term_lines.append(f"- {t.term}（同义词: {synonyms_str}）：{t.definition or ''}")
            term_text = "\n业务术语映射（用户可能用同义词指代以下术语）：\n" + "\n".join(term_lines)

        # 构建Prompt（不调用LLM）
        prompt = NL2SQLEngine._build_sql_prompt(schema_text, term_text, question)

        # 调用LLM生成SQL（传入question用于时间冲突检测）
        sql = await NL2SQLEngine._generate_sql_from_prompt(prompt, question)

        if not sql:
            logger.error(f"SQL生成失败: 问题={question[:30]}..., 返回结果为空")
            raise BusinessException(code=500, message="SQL生成失败，大模型返回为空")

        logger.info(f"SQL生成完成: 问题={question[:30]}..., SQL={sql[:80]}...")
        return sql

    @staticmethod
    def _remove_time_filter(sql: str) -> str:
        """
        移除SQL中的时间过滤条件，用于重试查询

        当一周过滤条件导致无数据时，自动移除时间条件重试。

        :param sql: 原始SQL语句
        :return: 移除时间条件后的SQL语句

        移除逻辑：
            1. 移除AND连接的时间条件（不影响WHERE子句）
            2. 处理WHERE + 时间条件：如果后面还有AND，将WHERE xxx AND替换为WHERE
            3. WHERE后只剩时间条件（没有其他AND条件），移除整个WHERE子句
            4. 清理残留的"WHERE  AND"等情况
        """
        import re
        new_sql = sql

        # 先移除 AND 连接的时间条件（不影响WHERE子句）
        new_sql = re.sub(r"\s+AND\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+AND\s+[a-zA-Z_]+\s*<=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]", "", new_sql, flags=re.IGNORECASE)

        # 处理 WHERE + 时间条件：如果后面还有AND，将 WHERE xxx AND 替换为 WHERE
        # 否则整行WHERE子句移除
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]\s+AND\b", " WHERE", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*<=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]\s+AND\b", " WHERE", new_sql, flags=re.IGNORECASE)

        # WHERE后只剩时间条件（没有其他AND条件），移除整个WHERE子句
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*<=?\s*['\"]\d{4}-\d{2}-\d{2}(\s+\d{2}:\d{2}:\d{2})?['\"]", "", new_sql, flags=re.IGNORECASE)

        # 清理残留
        new_sql = new_sql.replace("WHERE  AND", "WHERE").replace("WHERE AND", "WHERE")
        new_sql = new_sql.replace("WHERE  ", "WHERE ")
        new_sql = " ".join(new_sql.split())
        return new_sql

    @staticmethod
    async def _fetch_column_meta(sql: str, datasource: DataSource) -> List[dict]:
        """
        从INFORMATION_SCHEMA获取SQL涉及的字段注释信息

        获取查询结果中各字段的元信息（表名、字段名、类型、注释），
        用于前端展示字段的中文名称。

        :param sql: SQL语句
        :param datasource: 数据源配置
        :return: 字段元信息列表 [{table, name, type, comment}]

        实现逻辑：
            1. 从SQL中提取表名（FROM和JOIN子句）
            2. 过滤系统表
            3. 查询INFORMATION_SCHEMA.COLUMNS获取字段信息
            4. 返回字段元信息列表
        """
        try:
            # 从SQL中提取表名
            table_names = re.findall(r'\bFROM\s+(\w+)', sql, re.IGNORECASE)
            # 也处理 JOIN 的表
            join_tables = re.findall(r'\bJOIN\s+(\w+)', sql, re.IGNORECASE)
            table_names = list(set(table_names + join_tables))
            # 过滤系统表
            table_names = [t for t in table_names if t.lower() not in NL2SQLEngine.SYSTEM_TABLES]

            if not table_names:
                return []

            if datasource.type == "mysql":
                import aiomysql
                conn = await aiomysql.connect(
                    host=datasource.host,
                    port=datasource.port or 3306,
                    user=datasource.username,
                    password=datasource.password or "",
                    db=datasource.database,
                    charset=datasource.charset or "utf8mb4",
                )
                column_meta = []
                async with conn.cursor() as cursor:
                    placeholders = ",".join(["%s"] * len(table_names))
                    await cursor.execute(f"""
                        SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT
                        FROM INFORMATION_SCHEMA.COLUMNS
                        WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({placeholders})
                        ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """, [datasource.database] + table_names)
                    rows = await cursor.fetchall()
                    for row in rows:
                        column_meta.append({
                            "table": row[0],
                            "name": row[1],
                            "type": row[2],
                            "comment": row[3] or "",
                        })
                conn.close()
                logger.debug(f"获取字段元信息完成: {len(column_meta)}个字段")
                return column_meta
        except Exception as e:
            logger.warning(f"获取字段注释失败(不影响查询): {e}")
            return []

    @staticmethod
    async def validate_and_execute(
        db: AsyncSession,
        sql: str,
        datasource: DataSource,
    ) -> Tuple[bool, str, Optional[List[dict]], Optional[List[dict]]]:
        """
        校验并执行SQL

        执行完整的SQL校验和执行流程，包括安全检查、语法校验和执行。

        :param db: 数据库会话
        :param sql: SQL语句
        :param datasource: 数据源配置
        :return: (是否成功, 错误信息, 结果数据, 字段元信息)

        流程步骤：
            1. 安全检查（拦截危险操作）
            2. 语法校验（使用sqlglot）
            3. 修正中文日期格式（如"2023年8月" → "2023-08-01"）
            4. 获取字段注释（从INFORMATION_SCHEMA）
            5. 执行SQL（根据数据源类型选择不同的驱动）
            6. 如果无数据且有WHERE条件，自动重试（移除时间过滤）
            7. 返回执行结果

        支持的数据库类型：
            - mysql: 使用aiomysql
            - postgresql: 使用asyncpg
            - oracle: 使用oracledb
        """
        # 1. 安全检查
        is_safe, error = SQLSecurityFilter.check(sql)
        if not is_safe:
            return False, error, None, None

        # 2. 语法校验
        dialect = datasource.type if datasource.type in ["mysql", "postgres", "sqlite"] else "mysql"
        is_valid, error = SQLValidator.validate(sql, dialect)
        if not is_valid:
            return False, error, None, None

        # 2.5 修正中文日期格式（如"2023年8月" → "2023-08-01"）
        import re as _re
        def fix_chinese_date(s: str) -> str:
            # 匹配 "YYYY年MM月DD日" → "YYYY-MM-DD"（自动补零）
            s = _re.sub(r"(\d{4})年(\d{1,2})月(\d{1,2})日", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", s)
            # 匹配 "YYYY年MM月" → "YYYY-MM-01"（自动补零）
            s = _re.sub(r"(\d{4})年(\d{1,2})月(?!\d)", lambda m: f"{m.group(1)}-{int(m.group(2)):02d}-01", s)
            return s
        sql = fix_chinese_date(sql)

        # 3. 获取字段注释（从INFORMATION_SCHEMA）
        column_meta = await NL2SQLEngine._fetch_column_meta(sql, datasource)

        # 4. 执行SQL（内部函数，根据数据源类型选择驱动）
        async def execute_sql(conn_sql: str) -> Optional[List[dict]]:
            nonlocal datasource
            if datasource.type == "mysql":
                import aiomysql
                conn = await aiomysql.connect(
                    host=datasource.host,
                    port=datasource.port,
                    user=datasource.username,
                    password=datasource.password or "",
                    db=datasource.database,
                    charset=datasource.charset,
                )
                try:
                    async with conn.cursor() as cursor:
                        await cursor.execute(conn_sql)
                        rows = await cursor.fetchall()
                        columns = [desc[0] for desc in cursor.description]
                finally:
                    conn.close()
                results = [dict(zip(columns, row)) for row in rows]
                return json_safe(results)

            elif datasource.type == "postgresql":
                import asyncpg
                conn = await asyncpg.connect(
                    host=datasource.host,
                    port=datasource.port,
                    user=datasource.username,
                    password=datasource.password or "",
                    database=datasource.database,
                )
                rows = await conn.fetch(conn_sql)
                await conn.close()
                results = [dict(row) for row in rows]
                return json_safe(results)

            elif datasource.type == "oracle":
                import oracledb
                oracledb.init_oracle_client()
                pool = await oracledb.create_pool_async(
                    user=datasource.username,
                    password=datasource.password or "",
                    dsn=f"{datasource.host}:{datasource.port}/{datasource.database}",
                    min=1,
                    max=1,
                )
                async with pool.acquire() as connection:
                    async with connection.cursor() as cursor:
                        await cursor.execute(conn_sql)
                        rows = await cursor.fetchall()
                        columns = [col[0] for col in cursor.description] if cursor.description else []
                await pool.close()
                results = [dict(zip(columns, row)) for row in rows]
                return json_safe(results)
            return None

        try:
            results = await execute_sql(sql)
            if results is None:
                return False, f"不支持的数据库类型: {datasource.type}", None, None

            # 自动重试：如果无数据且有WHERE条件，移除时间过滤重试
            if not results and "WHERE" in sql.upper():
                new_sql = NL2SQLEngine._remove_time_filter(sql)
                if new_sql != sql:
                    logger.info(f"一周过滤无数据，尝试移除时间条件重试，新SQL: {new_sql[:80]}...")
                    retry_results = await execute_sql(new_sql)
                    if retry_results:
                        logger.info(f"移除时间条件后查询到 {len(retry_results)} 条数据")
                        return True, "（已自动放宽时间范围）", retry_results, column_meta

            return True, "", results, column_meta

        except Exception as e:
            logger.error(f"SQL执行失败: {e}", exc_info=True)
            return False, f"SQL执行失败: {str(e)}", None, None

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
        datasource_id: int,
    ) -> Tuple[Optional[str], Optional[List[dict]], Optional[str], Optional[List[dict]]]:
        """
        NL2SQL查询流程

        完整的NL2SQL查询流程，包含重试机制。

        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :return: (SQL, 结果数据, 错误信息, 字段元信息)

        流程步骤：
            1. 获取术语列表
            2. 生成SQL语句
            3. 获取数据源配置
            4. 校验并执行SQL
            5. 如果失败，重试（最多2次）
            6. 返回查询结果

        重试机制：
            - 最多重试2次
            - 每次失败记录错误日志
            - 最后一次失败返回错误信息
        """
        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"NL2SQL第{attempt}次尝试: 问题={question[:30]}...")

                # 1. 获取术语
                term_stmt = select(Term).where(Term.status == "active")
                term_result = await db.execute(term_stmt)
                terms = list(term_result.scalars().all())
                logger.debug(f"获取到术语数量: {len(terms)}")

                # 2. 生成SQL
                sql = await NL2SQLEngine.generate_sql(db, question, datasource_id, terms)

                # 3. 获取数据源
                ds_stmt = select(DataSource).where(DataSource.id == datasource_id)
                ds_result = await db.execute(ds_stmt)
                datasource = ds_result.scalar_one_or_none()

                if not datasource:
                    return sql, None, "数据源不存在", None

                # 4. 校验并执行
                success, error, results, column_meta = await NL2SQLEngine.validate_and_execute(db, sql, datasource)

                if success:
                    logger.info(f"NL2SQL查询成功: 问题={question[:30]}..., 结果数={len(results) if results else 0}")
                    return sql, results, None, column_meta
                else:
                    last_error = error
                    logger.warning(f"NL2SQL第{attempt}次尝试失败: {error}")
                    if attempt < max_retries:
                        continue
                    return sql, None, error, None

            except Exception as e:
                last_error = str(e)
                logger.error(f"NL2SQL第{attempt}次查询异常: {e}", exc_info=True)
                if attempt < max_retries:
                    continue

        return None, None, f"查询生成失败（已重试{max_retries}次）: {last_error or '请检查大模型配置'}", None


# 服务实例（供其他模块调用）
schema_linking_engine = SchemaLinkingEngine()
nl2sql_engine = NL2SQLEngine()
sql_security_filter = SQLSecurityFilter()
sql_validator = SQLValidator()