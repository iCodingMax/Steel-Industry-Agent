"""检查用户表结构和数据"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv('.env')

async def check():
    conn = await asyncpg.connect(
        host=os.getenv('PG_HOST', 'localhost'),
        port=int(os.getenv('PG_PORT', '5432')),
        user=os.getenv('PG_USER', 'postgres'),
        password=os.getenv('PG_PASSWORD', ''),
        database=os.getenv('PG_DB', 'steel_agent')
    )
    
    # 检查表结构
    columns = await conn.fetch('''
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'users'
    ''')
    print('=== users 表结构 ===')
    for col in columns:
        print(f"  {col['column_name']}: {col['data_type']}")
    
    # 查询用户数据
    users = await conn.fetch('SELECT id, username, role, status, name, email, phone, force_change_password FROM users')
    print(f'\n=== 用户数据 (共{len(users)}条) ===')
    for user in users:
        print(dict(user))
    
    await conn.close()

asyncio.run(check())
