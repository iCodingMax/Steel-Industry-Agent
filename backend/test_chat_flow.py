import asyncio
import time
from app.core.config import settings
from app.services.llm_service import llm_service

async def test_intent_classify():
    print("=== 测试意图分类 ===")
    start = time.time()
    try:
        intent = await llm_service.classify_intent("hello")
        print(f"意图分类成功: {intent}, 耗时: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"意图分类失败: {e}, 耗时: {time.time() - start:.2f}s")

async def test_chat():
    print("=== 测试LLM聊天 ===")
    start = time.time()
    try:
        result = await llm_service.chat("hello")
        print(f"聊天成功: {result[:50]}..., 耗时: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"聊天失败: {e}, 耗时: {time.time() - start:.2f}s")

async def test_chat_stream():
    print("=== 测试LLM流式聊天 ===")
    start = time.time()
    try:
        async for chunk in llm_service.chat_stream("hello"):
            print(f"收到片段: {chunk}")
        print(f"流式聊天成功, 耗时: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"流式聊天失败: {e}, 耗时: {time.time() - start:.2f}s")

async def main():
    await test_intent_classify()
    await test_chat()
    await test_chat_stream()

if __name__ == "__main__":
    asyncio.run(main())