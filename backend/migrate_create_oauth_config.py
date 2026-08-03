"""
数据库迁移脚本：创建 oauth_config 表
存储OAuth2认证配置信息
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
    logger.info("数据库迁移：创建 oauth_config 表")
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

        # 检查表是否存在
        table_check = await conn.fetch("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'oauth_config'
            )
        """)
        
        if table_check[0]['exists']:
            logger.info("oauth_config 表已存在")
        else:
            logger.info("正在创建 oauth_config 表...")
            
            await conn.execute("""
                CREATE TABLE oauth_config (
                    id SERIAL PRIMARY KEY,
                    authorization_url VARCHAR(500) NOT NULL,
                    token_url VARCHAR(500) NOT NULL,
                    user_info_url VARCHAR(500) NOT NULL,
                    scope VARCHAR(200) NOT NULL,
                    client_id VARCHAR(200) NOT NULL,
                    client_secret VARCHAR(500) NOT NULL,
                    field_mapping TEXT,
                    redirect_url VARCHAR(500) NOT NULL,
                    enabled BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)
            
            # 添加字段注释
            comments = {
                "oauth_config": "OAuth2配置表",
                "id": "配置ID",
                "authorization_url": "授权端地址",
                "token_url": "Token端地址",
                "user_info_url": "用户信息端地址",
                "scope": "连接范围",
                "client_id": "客户端ID",
                "client_secret": "客户端密钥",
                "field_mapping": "字段映射JSON",
                "redirect_url": "回调地址",
                "enabled": "是否启用",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            }
            
            for table, comment in comments.items():
                if table == "oauth_config":
                    await conn.execute(f"COMMENT ON TABLE oauth_config IS '{comment}'")
                else:
                    await conn.execute(f"COMMENT ON COLUMN oauth_config.{table} IS '{comment}'")
            
            logger.success("oauth_config 表创建成功")

        # 检查是否需要插入默认配置（ID=1）
        config_check = await conn.fetch("""
            SELECT COUNT(*) as cnt FROM oauth_config WHERE id = 1
        """)
        
        if config_check[0]['cnt'] == 0:
            logger.info("正在插入默认OAuth2配置...")
            await conn.execute("""
                INSERT INTO oauth_config (
                    id, authorization_url, token_url, user_info_url,
                    scope, client_id, client_secret, field_mapping,
                    redirect_url, enabled
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            """, 
                1,
                'http://172.1.8.71:89/oauth2/authorize/ai-group',
                'http://172.1.8.71:89/api/oauth2/token',
                'http://172.1.8.71:89/api/oauth2/userinfo',
                'profile',
                'a8ce57a48fa9484ca94cf6ce4aad6664',
                'iv9gmv4wizyqy44vg83fika9q5ud6m6s',
                '{"username":"preferred_username","nick_name":"nickname","email":"email"}',
                'http://localhost:5173/admin/api/oauth2',
                False,
            )
            logger.success("默认OAuth2配置已插入")

        await conn.close()
        logger.info("=" * 60)
        logger.success("迁移完成！")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"迁移过程发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
