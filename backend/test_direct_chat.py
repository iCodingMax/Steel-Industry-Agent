import asyncio
from app.services.llm_service import llm_service

async def test():
    print("测试直接调用LLM聊天...")
    result = await llm_service.chat("hello")
    print(f"LLM回复: {result}")
    
    print("\n测试流式调用LLM聊天...")
    full_content = ""
    async for chunk in llm_service.chat_stream("hello"):
        full_content += chunk
        print(f"收到: {chunk}")
    print(f"完整回复: {full_content}")

asyncio.run(test())