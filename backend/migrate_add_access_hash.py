"""
数据库迁移脚本：为 applications 表添加 access_hash 字段
并为已有应用生成唯一的access_hash值
"""
import os
import sys
import asyncio
import urllib.parse
from loguru import logger
import uuid

from dotenv import load_dotenv
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)


async def main():
    logger.info("=" * 60)
    logger.info("数据库迁移：为 applications 表添加 access_hash 字段")
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
            WHERE table_name = 'applications' AND column_name = 'access_hash'
        """)
        
        if result:
            logger.info("字段 access_hash 已存在，跳过添加")
        else:
            logger.info("正在添加 access_hash 字段...")
            await conn.execute("""
                ALTER TABLE applications 
                ADD COLUMN access_hash VARCHAR(32)
            """)
            await conn.execute("""
                ALTER TABLE applications 
                ADD CONSTRAINT applications_access_hash_key UNIQUE (access_hash)
            """)
            logger.success("字段 access_hash 添加成功")

        # 为已有应用生成access_hash
        logger.info("正在为已有应用生成access_hash...")
        apps = await conn.fetch("SELECT id, access_hash FROM applications")
        
        updated_count = 0
        for app in apps:
            if not app['access_hash']:
                new_hash = uuid.uuid4().hex
                await conn.execute(
                    "UPDATE applications SET access_hash = $1 WHERE id = $2",
                    new_hash, app['id']
                )
                updated_count += 1
                logger.debug(f"  应用 ID {app['id']} -> access_hash: {new_hash}")
        
        if updated_count > 0:
            logger.success(f"成功为 {updated_count} 个应用生成了access_hash")
        else:
            logger.info("所有应用已有access_hash，无需更新")

        await conn.close()
        logger.info("=" * 60)
        logger.success("迁移完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"迁移过程发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
