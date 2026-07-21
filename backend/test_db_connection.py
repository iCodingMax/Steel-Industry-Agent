import asyncio
import aiomysql
from app.core.config import settings

async def test_business_db():
    print("=== 测试业务数据库连接 ===")
    try:
        conn = await aiomysql.connect(
            host=settings.BUSINESS_DB_HOST,
            port=settings.BUSINESS_DB_PORT,
            user=settings.BUSINESS_DB_USER,
            password=settings.BUSINESS_DB_PASSWORD,
            db=settings.BUSINESS_DB_NAME,
            charset=settings.BUSINESS_DB_CHARSET,
        )
        async with conn.cursor() as cursor:
            await cursor.execute("SELECT 1")
            result = await cursor.fetchone()
            print(f"业务数据库连接成功: {result}")
        conn.close()
    except Exception as e:
        print(f"业务数据库连接失败: {e}")

async def test_system_db():
    print("=== 测试系统数据库连接 ===")
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from app.core.database import get_db_session
    try:
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.begin() as conn:
            result = await conn.run_sync(lambda conn: conn.execute("SELECT 1"))
            print(f"系统数据库连接成功")
        await engine.dispose()
    except Exception as e:
        print(f"系统数据库连接失败: {e}")

async def main():
    await test_business_db()
    await test_system_db()

if __name__ == "__main__":
    asyncio.run(main())