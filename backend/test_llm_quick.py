import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            'http://172.1.2.198:9997/v1/chat/completions',
            headers={
                'Authorization': 'Bearer empty',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'qwen3',
                'messages': [{'role': 'user', 'content': 'hello'}],
                'max_tokens': 100,
                'temperature': 0.7,
            },
        )
        print(f'Status: {response.status_code}')
        data = response.json()
        content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
        print(f'Content: {content[:50]}')

asyncio.run(test())