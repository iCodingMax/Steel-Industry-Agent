import httpx
import asyncio
import json

async def test():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4NDY4MTc5N30.1y4sMs33Orcaj0Lr-Liy6ncFPDyduKqnkiVzBUPvO9k"
    
    # 设置更长的超时时间
    async with httpx.AsyncClient(timeout=300.0) as client:
        async with client.stream(
            "POST",
            "http://localhost:8000/api/v1/sessions/stream",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "sessionId": 1,
                "question": "hello",
                "knowledgeBaseId": None,
                "datasourceId": None,
            },
        ) as response:
            print(f"Status: {response.status_code}")
            full_content = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        print(f"Event: {data.get('type')}")
                        if data.get('type') == 'content':
                            content = data.get('content', '')
                            print(f"Content chunk: {content[:50]}")
                            full_content += content
                        elif data.get('type') == 'error':
                            print(f"Error: {data.get('message')}")
                    except Exception as e:
                        print(f"Parse error: {e}, Raw: {line[:100]}")
            
            print(f"\nFull content: {full_content}")

asyncio.run(test())