"""
数据库迁移脚本：创建对话用户表 chat_users
"""
import os
import sys
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()


async def migrate():
    """执行数据库迁移"""
    print("=" * 60)
    print("数据库迁移：创建对话用户表 chat_users")
    print("=" * 60)
    
    # 连接数据库
    conn = await asyncpg.connect(
        host=os.getenv('PG_HOST', 'localhost'),
        port=int(os.getenv('PG_PORT', '5432')),
        user=os.getenv('PG_USER', 'postgres'),
        password=os.getenv('PG_PASSWORD', ''),
        database=os.getenv('PG_DB', 'steel_agent')
    )
    
    try:
        # 检查表是否存在
        table_exists = await conn.fetchval(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'chat_users')"
        )
        
        if table_exists:
            print("ℹ️  表 chat_users 已存在，跳过创建")
        else:
            # 创建 chat_users 表
            await conn.execute("""
                CREATE TABLE chat_users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(50),
                    email VARCHAR(100),
                    phone VARCHAR(20),
                    status VARCHAR(20) DEFAULT 'active',
                    user_source VARCHAR(20) DEFAULT 'local',
                    last_login_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            print("✅ 表 chat_users 创建成功")
            
            # 添加字段注释
            await conn.execute("""
                COMMENT ON TABLE chat_users IS '对话用户表，存储对话用户信息用于对话记录隔离'
            """)
            print("✅ 表注释添加成功")
            
            columns_comments = {
                "id": "用户ID",
                "username": "用户名",
                "name": "姓名",
                "email": "邮箱",
                "phone": "手机号",
                "status": "状态: active/disabled",
                "user_source": "用户来源: oauth2/local",
                "last_login_at": "最后登录时间",
                "created_at": "创建时间",
                "updated_at": "更新时间",
            }
            
            for col, comment in columns_comments.items():
                await conn.execute(
                    f"COMMENT ON COLUMN chat_users.{col} IS '{comment}'"
                )
            print("✅ 字段注释添加成功")
            
            # 创建索引
            await conn.execute("CREATE INDEX idx_chat_users_username ON chat_users(username)")
            print("✅ 用户名索引创建成功")
        
        # 验证表结构
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'chat_users'
            ORDER BY ordinal_position
        """)
        
        print("\n📋 表结构验证：")
        print("-" * 40)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")
        
        print("\n" + "=" * 60)
        print("✅ 迁移完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 迁移失败: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
