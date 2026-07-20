"""
MySQL -> PostgreSQL 数据迁移脚本

使用方式:
    python migrate_db.py

注意事项:
    1. 确保 MySQL 和 PostgreSQL 服务都已启动
    2. 确保 PostgreSQL 已创建 steel_agent 数据库
    3. 迁移前请备份 MySQL 数据
    4. 迁移过程中请停止后端服务，确保数据一致性
"""
import json
import os
import sys
import urllib.parse
from loguru import logger

from dotenv import load_dotenv
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

import app.models.user
import app.models.datasource
import app.models.metric
import app.models.dimension
import app.models.term
import app.models.llm_config
import app.models.knowledge
import app.models.session
import app.models.audit_log

from app.core.base_model import Base


def create_target_tables(pg_engine):
    """在 PostgreSQL 中创建目标表结构"""
    logger.info("正在创建 PostgreSQL 目标表结构...")
    
    inspector = inspect(pg_engine)
    existing_tables = set(inspector.get_table_names())
    logger.info(f"现有表: {existing_tables}")
    
    Base.metadata.create_all(pg_engine)
    
    inspector = inspect(pg_engine)
    new_tables = set(inspector.get_table_names())
    logger.info(f"创建后表: {new_tables}")
    logger.info(f"新创建表: {new_tables - existing_tables}")
    
    logger.success("PostgreSQL 目标表结构创建完成")


def truncate_tables(pg_engine):
    """清空 PostgreSQL 表数据（按外键依赖顺序）"""
    logger.info("正在清空 PostgreSQL 表数据...")
    
    tables_order = [
        'audit_logs', 'traces', 'messages', 'document_segments', 'documents',
        'knowledge_bases', 'sessions', 'llm_configs', 'terms', 'dimensions',
        'metrics', 'table_schemas', 'datasources', 'users'
    ]
    
    pg_session = sessionmaker(bind=pg_engine)()
    try:
        pg_session.execute(text("SET session_replication_role = 'replica';"))
        
        for table_name in tables_order:
            try:
                pg_session.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE;'))
                logger.info(f"  已清空表: {table_name}")
            except Exception as e:
                logger.warning(f"  清空表 {table_name} 失败: {e}")
        
        pg_session.execute(text("SET session_replication_role = 'origin';"))
        pg_session.commit()
        logger.success("PostgreSQL 表数据清空完成")
    except Exception as e:
        pg_session.rollback()
        logger.error(f"清空表失败: {e}")
        raise
    finally:
        pg_session.close()


def migrate_table(mysql_engine, pg_engine, table_name, json_columns=None, boolean_columns=None):
    """迁移单个表的数据"""
    logger.info(f"迁移表: {table_name}")

    mysql_session = sessionmaker(bind=mysql_engine)()
    pg_session = sessionmaker(bind=pg_engine)()

    try:
        result = mysql_session.execute(text(f"SELECT * FROM {table_name}"))
        rows = result.fetchall()
        if not rows:
            logger.info(f"  表 {table_name} 无数据，跳过")
            return 0

        columns = [col for col in result.keys()]
        row_count = len(rows)

        reserved_words = ['references']
        escaped_cols = [f'"{col}"' if col.lower() in reserved_words else col for col in columns]
        placeholders = ", ".join([f":{col}" for col in columns])
        insert_template = f'INSERT INTO "{table_name}" ({", ".join(escaped_cols)}) VALUES ({placeholders})'

        json_cols = json_columns or []
        bool_cols = boolean_columns or []

        for row in rows:
            row_dict = dict(zip(columns, row))
            
            for col in json_cols:
                if col in row_dict and row_dict[col] is not None:
                    if isinstance(row_dict[col], str):
                        try:
                            parsed = json.loads(row_dict[col])
                            row_dict[col] = json.dumps(parsed, ensure_ascii=False)
                        except (json.JSONDecodeError, TypeError):
                            row_dict[col] = json.dumps({}, ensure_ascii=False)
                    elif isinstance(row_dict[col], (dict, list)):
                        row_dict[col] = json.dumps(row_dict[col], ensure_ascii=False)
                    else:
                        row_dict[col] = json.dumps({}, ensure_ascii=False)
            
            for col in bool_cols:
                if col in row_dict:
                    val = row_dict[col]
                    if val is None:
                        row_dict[col] = False
                    elif isinstance(val, int):
                        row_dict[col] = bool(val)
                    else:
                        row_dict[col] = bool(val)

            pg_session.execute(text(insert_template), row_dict)

        pg_session.commit()
        logger.info(f"  成功迁移 {row_count} 条记录")
        return row_count

    except Exception as e:
        pg_session.rollback()
        logger.error(f"  迁移失败: {e}")
        raise
    finally:
        mysql_session.close()
        pg_session.close()


def main():
    logger.info("=" * 60)
    logger.info("MySQL -> PostgreSQL 数据迁移")
    logger.info("=" * 60)

    try:
        SOURCE_DB_NAME = "steel_agent"

        mysql_user = os.getenv("BUSINESS_DB_USER", "root")
        mysql_password = os.getenv("BUSINESS_DB_PASSWORD", "")
        mysql_host = os.getenv("BUSINESS_DB_HOST", "localhost")
        mysql_port = int(os.getenv("BUSINESS_DB_PORT", "3306"))

        logger.info(f"环境变量 BUSINESS_DB_USER: {mysql_user}")
        logger.info(f"环境变量 BUSINESS_DB_PASSWORD: {mysql_password[:3]}***" if mysql_password else "空")
        logger.info(f"环境变量 BUSINESS_DB_HOST: {mysql_host}")

        mysql_password_encoded = urllib.parse.quote(mysql_password, safe='')
        mysql_url = (
            f"mysql+pymysql://{mysql_user}:{mysql_password_encoded}"
            f"@{mysql_host}:{mysql_port}/{SOURCE_DB_NAME}"
        )
        mysql_engine = create_engine(mysql_url, echo=False)

        pg_user = os.getenv("PG_USER", "postgres")
        pg_password = os.getenv("PG_PASSWORD", "")
        pg_host = os.getenv("PG_HOST", "localhost")
        pg_port = int(os.getenv("PG_PORT", "5432"))
        pg_db = os.getenv("PG_DB", "steel_agent")

        logger.info(f"环境变量 PG_USER: {pg_user}")
        logger.info(f"环境变量 PG_PASSWORD: {pg_password[:3]}***" if pg_password else "空")

        pg_engine = create_engine(
            f"postgresql+psycopg://",
            connect_args={
                "host": pg_host,
                "port": pg_port,
                "user": pg_user,
                "password": pg_password,
                "dbname": pg_db,
            },
            echo=False,
        )

        logger.info(f"MySQL 连接: {mysql_host}:{mysql_port}/{SOURCE_DB_NAME}")
        logger.info(f"PostgreSQL 连接: {pg_host}:{pg_port}/{pg_db}")

        try:
            with mysql_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.success("MySQL 连接成功")
        except Exception as e:
            logger.error(f"MySQL 连接失败: {e}")
            sys.exit(1)

        try:
            with pg_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.success("PostgreSQL 连接成功")
        except Exception as e:
            logger.error(f"PostgreSQL 连接失败: {e}")
            sys.exit(1)

        create_target_tables(pg_engine)
        truncate_tables(pg_engine)

        tables_to_migrate = [
            ("users", [], ["force_change_password"]),
            ("datasources", [], []),
            ("table_schemas", ["columns"], []),
            ("metrics", ["tags"], []),
            ("dimensions", [], []),
            ("terms", ["synonyms", "related_terms"], []),
            ("llm_configs", ["extra_params"], ["is_default"]),
            ("knowledge_bases", [], []),
            ("documents", [], []),
            ("document_segments", ["meta_data"], []),
            ("sessions", [], []),
            ("messages", ["references", "sql_traces", "data_result", "column_meta", "thinking_steps"], []),
            ("traces", [], []),
            ("audit_logs", ["detail"], []),
        ]

        total_rows = 0
        for table_name, json_cols, bool_cols in tables_to_migrate:
            try:
                count = migrate_table(mysql_engine, pg_engine, table_name, json_cols, bool_cols)
                total_rows += count
            except Exception as e:
                logger.error(f"表 {table_name} 迁移失败: {e}")
                logger.warning("继续迁移其他表...")

        logger.info("=" * 60)
        logger.success(f"迁移完成！总计迁移 {total_rows} 条记录")
        logger.info("=" * 60)

        mysql_engine.dispose()
        pg_engine.dispose()

    except Exception as e:
        logger.error(f"迁移过程发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
