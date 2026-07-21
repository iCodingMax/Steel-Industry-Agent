"""
大模型客户端封装
统一调用Xinference LLM服务
"""
from typing import List, Dict, Optional, AsyncIterator
import httpx
from loguru import logger

from app.core.config import settings


class LLMClient:
    """大模型客户端"""

    def __init__(self):
        self.base_url = f"{settings.XINFERENCE_BASE_URL}/v1"
        self.api_key = "not-needed"
        self.model = settings.XINFERENCE_LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> str:
        """
        非流式聊天补全

        :param messages: 消息列表 [{"role": "user", "content": "..."}]
        :param temperature: 温度参数
        :param max_tokens: 最大输出token
        :param model: 模型名称
        :return: 生成的文本
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result["choices"][0]["message"]["content"]
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                raise

    async def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        """
        流式聊天补全

        :param messages: 消息列表
        :param temperature: 温度参数
        :param max_tokens: 最大输出token
        :param model: 模型名称
        :yield: 逐块生成的文本
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                break
                            try:
                                import json
                                chunk = json.loads(data)
                                if chunk["choices"] and chunk["choices"][0].get("delta", {}).get("content"):
                                    yield chunk["choices"][0]["delta"]["content"]
                            except (json.JSONDecodeError, KeyError):
                                continue
            except Exception as e:
                logger.error(f"LLM流式调用失败: {e}")
                raise

    async def embedding(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本嵌入向量（使用Xinference）

        :param texts: 文本列表
        :return: 嵌入向量列表
        """
        payload = {
            "model": settings.XINFERENCE_EMBED_MODEL,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{settings.XINFERENCE_BASE_URL}/v1/embeddings",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return [item["embedding"] for item in result["data"]]
            except Exception as e:
                logger.error(f"Embedding调用失败: {e}")
                raise

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
    ) -> List[Dict]:
        """
        重排（使用Xinference Rerank模型）

        :param query: 查询文本
        :param documents: 文档列表
        :param top_k: 返回前k条
        :return: 重排结果列表 [{"index": int, "relevance_score": float}]
        """
        payload = {
            "model": settings.XINFERENCE_RERANK_MODEL,
            "query": query,
            "documents": documents,
            "top_n": top_k or settings.RERANK_TOP_K,
            "return_documents": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{settings.XINFERENCE_BASE_URL}/v1/rerank",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
                return result.get("results", [])
            except Exception as e:
                logger.error(f"Rerank调用失败: {e}")
                raise


llm_client = LLMClient()
