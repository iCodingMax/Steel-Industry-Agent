"""
数据库迁移脚本：为 sessions 表添加 llm_config_id 字段
"""
import os
import sys
import asyncio
import urllib.parse
from loguru import logger

from dotenv import load_dotenv
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)


async def main():
    logger.info("=" * 60)
    logger.info("数据库迁移：为 sessions 表添加 llm_config_id 字段")
    logger.info("=" * 60)

    try:
        pg_user = os.getenv("PG_USER", "postgres")
        pg_password = os.getenv("PG_PASSWORD", "")
        pg_host = os.getenv("PG_HOST", "localhost")
        pg_port = int(os.getenv("PG_PORT", "5432"))
        pg_db = os.getenv("PG_DB", "steel_agent")

        logger.info(f"PostgreSQL 连接: {pg_host}:{pg_port}/{pg_db}")

        import asyncpg
        conn = await asyncpg.connect(
            host=pg_host,
            port=pg_port,
            user=pg_user,
            password=pg_password,
            database=pg_db
        )
        
        logger.success("PostgreSQL 连接成功")

        # 检查字段是否已存在
        result = await conn.fetch("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'sessions' AND column_name = 'llm_config_id'
        """)
        
        if result:
            logger.info("字段 llm_config_id 已存在，跳过")
        else:
            logger.info("正在添加 llm_config_id 字段...")
            await conn.execute("""
                ALTER TABLE sessions 
                ADD COLUMN llm_config_id INTEGER
            """)
            logger.success("字段 llm_config_id 添加成功")

        await conn.close()
        logger.info("=" * 60)
        logger.success("迁移完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"迁移过程发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
