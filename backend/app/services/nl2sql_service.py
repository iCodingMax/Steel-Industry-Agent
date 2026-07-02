"""
NL2SQL兜底引擎
功能：Schema Linking、SQL生成、语法校验、安全过滤、执行控制
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
    """递归处理JSON不可序列化的类型"""
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
    """SQL安全过滤器"""

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
        :param sql: SQL语句
        :return: (是否安全, 错误信息)
        """
        sql_upper = sql.upper()

        for pattern, keyword in SQLSecurityFilter.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper):
                return False, f"SQL包含危险操作: {keyword}"

        if ";" in sql and not sql.strip().endswith(";"):
            return False, "SQL包含多条语句，禁止执行"

        return True, ""

    @staticmethod
    def sanitize(sql: str) -> str:
        """清理SQL语句"""
        # 移除注释
        sql = re.sub(r"--.*$", "", sql, flags=re.MULTILINE)
        sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
        # 移除多余空格
        sql = " ".join(sql.split())
        return sql.strip()


class SQLValidator:
    """SQL语法校验器"""

    @staticmethod
    def validate(sql: str, dialect: str = "mysql") -> Tuple[bool, str]:
        """
        校验SQL语法
        :param sql: SQL语句
        :param dialect: 数据库方言
        :return: (是否合法, 错误信息)
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
    """Schema Linking引擎"""

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
        :return: [(表名, 字段名)]
        """
        # 获取数据源Schema
        stmt = select(TableSchema).where(TableSchema.datasource_id == datasource_id)
        result = await db.execute(stmt)
        schemas = [
            s for s in result.scalars().all()
            if s.table_name not in NL2SQLEngine.SYSTEM_TABLES
        ]

        if not schemas:
            return []

        # 构建Schema描述
        schema_desc = []
        for schema in schemas:
            import json
            columns = json.loads(schema.columns) if schema.columns else []
            col_names = [col["name"] for col in columns]
            schema_desc.append(f"表 {schema.table_name}: {', '.join(col_names)}")

        schema_text = "\n".join(schema_desc)

        # 使用LLM识别相关表和字段
        prompt = f"""请根据用户问题，从数据库Schema中选择相关的表和字段。

数据库Schema：
{schema_text}

用户问题：{question}

请返回需要的表和字段，格式如下：
表名1:字段名1,字段名2
表名2:字段名3

只返回最相关的表和字段，不要返回其他内容。"""

        response = await llm_service.chat(prompt)

        # 解析结果
        links = []
        for line in response.strip().split("\n"):
            if ":" in line:
                parts = line.split(":")
                table = parts[0].strip()
                fields = [f.strip() for f in parts[1].split(",")] if len(parts) > 1 else []

                for field in fields:
                    links.append((table, field))

        logger.info(f"Schema Linking完成: 问题={question}, 链接数={len(links)}")
        return links


class NL2SQLEngine:
    """NL2SQL引擎"""

    EXEC_TIMEOUT = 30  # 执行超时（秒）
    MAX_ROWS = 1000  # 最大返回行数

    # 系统内部表，不应出现在NL2SQL的Schema中
    SYSTEM_TABLES = {
        "users", "sessions", "messages", "datasources", "table_schemas",
        "metrics", "dimensions", "terms", "knowledge_bases", "documents",
        "document_segments", "llm_configs",
    }

    @staticmethod
    def _build_sql_prompt(
        schema_text: str,
        term_text: str,
        question: str,
    ) -> str:
        """构建SQL生成的Prompt（不调用LLM）"""
        today = datetime.date.today()
        one_week_ago = today - datetime.timedelta(days=7)
        
        return f"""你是一个钢铁行业数据分析SQL专家。请根据用户问题和数据库Schema，生成一个MySQL SELECT查询语句。

数据库Schema（DDL格式）：
{schema_text}
{term_text}

用户问题：{question}

要求：
1. 只生成SELECT查询语句，禁止使用INSERT/UPDATE/DELETE/DROP等操作
2. 严格使用Schema中存在的表名和字段名，不要编造
3. 根据用户问题添加适当的WHERE条件和聚合函数
4. 如果表中存在时间相关字段（如produce_date、create_time、update_time、date等），默认添加最近一周的数据过滤：
   时间字段 >= '{one_week_ago.strftime("%Y-%m-%d")}'
5. 限制返回行数不超过{NL2SQLEngine.MAX_ROWS}行（使用LIMIT）
6. 只返回纯SQL语句，不要包含markdown代码块标记或解释文字

请直接返回SQL语句："""

    @staticmethod
    async def _generate_sql_from_prompt(prompt: str) -> str:
        """从Prompt生成SQL（纯LLM调用，不持有数据库会话）"""
        sql = await llm_service.chat(prompt)
        logger.info(f"LLM原始输出: {repr(sql)}")

        # 移除markdown代码块标记
        sql = sql.strip()
        if sql.startswith("```sql"):
            sql = sql[5:]
        elif sql.startswith("```"):
            sql = sql[3:]
        if sql.endswith("```"):
            sql = sql[:-3]
        sql = sql.strip()
        logger.info(f"移除代码块标记后SQL: {repr(sql)}")

        # 清理SQL
        sql = SQLSecurityFilter.sanitize(sql)
        logger.info(f"安全清理后SQL: {repr(sql)}")

        # 添加行数限制
        if "LIMIT" not in sql.upper():
            sql = sql.rstrip(";") + f" LIMIT {NL2SQLEngine.MAX_ROWS}"
        logger.info(f"最终执行SQL: {sql}")

        return sql

    @staticmethod
    async def generate_sql(
        db: AsyncSession,
        question: str,
        datasource_id: int,
        terms: Optional[List[Term]] = None,
    ) -> str:
        """
        生成SQL语句
        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :param terms: 业务术语列表
        :return: SQL语句
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
        schemas = [
            s for s in schema_result.scalars().all()
            if s.table_name not in NL2SQLEngine.SYSTEM_TABLES
        ]

        # 构建Schema描述
        schema_desc = []
        for schema in schemas:
            import json
            columns = json.loads(schema.columns) if schema.columns else []
            col_info = []
            for col in columns:
                col_info.append(f"{col['name']}({col['type']})")
            schema_desc.append(f"CREATE TABLE {schema.table_name} ({', '.join(col_info)})")

        schema_text = "\n".join(schema_desc)

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

        # 调用LLM生成SQL（不再提交事务，由路由层统一管理）
        sql = await NL2SQLEngine._generate_sql_from_prompt(prompt)

        logger.info(f"SQL生成完成: 问题={question}, SQL={sql}")
        return sql

    @staticmethod
    def _remove_time_filter(sql: str) -> str:
        """移除SQL中的时间过滤条件，用于重试查询"""
        import re
        new_sql = sql
        new_sql = re.sub(r"\s+AND\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+AND\s+[a-zA-Z_]+\s*<=?\s*['\"]\d{4}-\d{2}-\d{2}['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+AND\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*>=?\s*['\"]\d{4}-\d{2}-\d{2}['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = re.sub(r"\s+WHERE\s+[a-zA-Z_]+\s*<=?\s*['\"]\d{4}-\d{2}-\d{2}['\"]", "", new_sql, flags=re.IGNORECASE)
        new_sql = new_sql.replace("WHERE  AND", "WHERE").replace("WHERE AND", "WHERE").strip()
        new_sql = new_sql.replace("WHERE  ", "WHERE ").strip()
        return new_sql

    @staticmethod
    async def _fetch_column_meta(sql: str, datasource: DataSource) -> List[dict]:
        """
        从INFORMATION_SCHEMA获取SQL涉及的字段注释信息
        :param sql: SQL语句
        :param datasource: 数据源配置
        :return: 字段元信息列表 [{name, comment, type}]
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
        :param db: 数据库会话
        :param sql: SQL语句
        :param datasource: 数据源配置
        :return: (是否成功, 错误信息, 结果数据, 字段元信息)
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

        # 3. 获取字段注释（从INFORMATION_SCHEMA）
        column_meta = await NL2SQLEngine._fetch_column_meta(sql, datasource)

        # 4. 执行SQL
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

            if not results and "WHERE" in sql.upper():
                new_sql = NL2SQLEngine._remove_time_filter(sql)
                if new_sql != sql:
                    logger.info(f"一周过滤无数据，尝试移除时间条件重试，新SQL: {new_sql}")
                    retry_results = await execute_sql(new_sql)
                    if retry_results:
                        logger.info(f"移除时间条件后查询到 {len(retry_results)} 条数据")
                        return True, "（已自动放宽时间范围）", retry_results, column_meta

            return True, "", results, column_meta

        except Exception as e:
            logger.error(f"SQL执行失败: {e}")
            return False, f"SQL执行失败: {str(e)}", None, None

    @staticmethod
    async def query(
        db: AsyncSession,
        question: str,
        datasource_id: int,
    ) -> Tuple[Optional[str], Optional[List[dict]], Optional[str], Optional[List[dict]]]:
        """
        NL2SQL查询流程
        :param db: 数据库会话
        :param question: 用户问题
        :param datasource_id: 数据源ID
        :return: (SQL, 结果数据, 错误信息, 字段元信息)
        """
        max_retries = 2
        last_error = None

        for attempt in range(1, max_retries + 1):
            try:
                # 1. 获取术语
                term_stmt = select(Term).where(Term.status == "active")
                term_result = await db.execute(term_stmt)
                terms = list(term_result.scalars().all())

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
                    return sql, results, None, column_meta
                else:
                    last_error = error
                    logger.warning(f"NL2SQL第{attempt}次尝试失败: {error}")
                    if attempt < max_retries:
                        continue
                    return sql, None, error, None

            except Exception as e:
                last_error = str(e)
                logger.error(f"NL2SQL第{attempt}次查询异常: {e}")
                if attempt < max_retries:
                    continue

        return None, None, f"查询生成失败（已重试{max_retries}次）: {last_error or '请检查大模型配置'}", None


# 服务实例
schema_linking_engine = SchemaLinkingEngine()
nl2sql_engine = NL2SQLEngine()
sql_security_filter = SQLSecurityFilter()
sql_validator = SQLValidator()