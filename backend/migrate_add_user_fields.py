"""
数据库迁移脚本：为 users 表添加新字段
新增字段：name（姓名）、email（邮箱）、phone（手机号）、status（状态）、oauth_provider（OAuth来源）、updated_at（更新时间）
同时更新现有用户的默认值
"""
import os
import sys
import asyncio
from loguru import logger

from dotenv import load_dotenv
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(env_path)


async def main():
    logger.info("=" * 60)
    logger.info("数据库迁移：为 users 表添加新字段")
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

        # 要添加的字段
        columns_to_add = [
            ("name", "VARCHAR(50)", "NULL", "姓名"),
            ("email", "VARCHAR(100)", "NULL", "邮箱"),
            ("phone", "VARCHAR(20)", "NULL", "手机号"),
            ("status", "VARCHAR(20)", "'active'", "状态"),
            ("oauth_provider", "VARCHAR(50)", "NULL", "OAuth来源"),
            ("updated_at", "TIMESTAMP", "NOW()", "更新时间"),
        ]

        for col_name, col_type, col_default, col_comment in columns_to_add:
            # 检查字段是否已存在
            result = await conn.fetch("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' AND column_name = $1
            """, col_name)
            
            if result:
                logger.info(f"字段 {col_name} 已存在，跳过添加")
            else:
                logger.info(f"正在添加字段 {col_name} ({col_comment})...")
                await conn.execute(f"""
                    ALTER TABLE users 
                    ADD COLUMN {col_name} {col_type} DEFAULT {col_default}
                """)
                # 添加字段注释
                await conn.execute(f"""
                    COMMENT ON COLUMN users.{col_name} IS '{col_comment}'
                """)
                logger.success(f"字段 {col_name} 添加成功")

        # 更新现有用户的默认值
        logger.info("正在更新现有用户数据...")
        
        # 将现有用户的角色从默认admin改为user（保持admin账号不变）
        # 先检查是否需要更新
        users = await conn.fetch("SELECT id, username, role, status FROM users")
        logger.info(f"当前用户数: {len(users)}")
        
        for user in users:
            user_id = user['id']
            username = user['username']
            
            # 确保status字段有默认值
            if user['status'] is None:
                await conn.execute(
                    "UPDATE users SET status = 'active' WHERE id = $1",
                    user_id
                )
                logger.debug(f"  用户 {username} 设置状态为 active")
        
        # 更新默认admin用户的force_change_password为False
        await conn.execute("""
            UPDATE users SET force_change_password = FALSE WHERE username = 'admin'
        """)
        logger.info("已更新admin用户的force_change_password为False")

        await conn.close()
        logger.info("=" * 60)
        logger.success("迁移完成！")
        logger.info("=" * 60)
        logger.info("新增字段列表:")
        logger.info("  - name: 姓名")
        logger.info("  - email: 邮箱")
        logger.info("  - phone: 手机号")
        logger.info("  - status: 状态 (active/disabled)")
        logger.info("  - oauth_provider: OAuth来源标识")
        logger.info("  - updated_at: 更新时间")

    except Exception as e:
        logger.error(f"迁移过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
