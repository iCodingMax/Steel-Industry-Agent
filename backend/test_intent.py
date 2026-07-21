import asyncio
from app.services.llm_service import llm_service

async def test():
    result = await llm_service.classify_intent("hello")
    print(f"意图分类结果: {result}")
    
    result2 = await llm_service.classify_intent("你好")
    print(f"意图分类结果(你好): {result2}")
    
    result3 = await llm_service.classify_intent("展示2023年8月的每日吹炼次数")
    print(f"意图分类结果(数据查询): {result3}")

asyncio.run(test())