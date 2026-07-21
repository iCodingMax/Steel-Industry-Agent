import httpx
import asyncio
import json

async def test():
    token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInVzZXJfaWQiOjEsInJvbGUiOiJhZG1pbiIsImV4cCI6MTc4NDY4MTc5N30.1y4sMs33Orcaj0Lr-Liy6ncFPDyduKqnkiVzBUPvO9k"
    async with httpx.AsyncClient(timeout=120.0) as client:
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
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        print(f"Event: {data.get('type')}")
                        if data.get('type') == 'content':
                            print(f"Content: {data.get('content')}")
                        elif data.get('type') == 'error':
                            print(f"Error: {data.get('message')}")
                    except:
                        print(f"Raw: {line[:100]}")

asyncio.run(test())