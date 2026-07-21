import asyncio
import httpx
from app.core.config import settings

async def test_llm():
    base_url = f"{settings.XINFERENCE_BASE_URL}/v1"
    print(f"测试LLM服务: {base_url}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer not-needed",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "qwen3",
                    "messages": [{"role": "user", "content": "hello"}],
                    "max_tokens": 20,
                    "temperature": 0.7,
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            print(f"成功! 响应: {content}")
    except httpx.HTTPStatusError as e:
        print(f"HTTP错误: {e.response.status_code}")
        print(f"响应体: {e.response.text[:500]}")
    except httpx.ConnectError as e:
        print(f"连接失败: {e}")
    except httpx.TimeoutException as e:
        print(f"超时: {e}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())