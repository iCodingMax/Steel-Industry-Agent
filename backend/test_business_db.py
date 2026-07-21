import asyncio
import aiomysql

async def test():
    try:
        conn = await aiomysql.connect(
            host='localhost', 
            port=3306, 
            user='root', 
            password='@Maxwell2024', 
            db='steel_test', 
            charset='utf8mb4'
        )
        print('业务数据库连接成功')
        conn.close()
    except Exception as e:
        print(f'连接失败: {e}')

asyncio.run(test())