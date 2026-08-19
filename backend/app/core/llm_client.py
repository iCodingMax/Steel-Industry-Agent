"""
大模型客户端封装
统一调用Xinference LLM服务

Xinference 是自托管的 LLM 推理服务，提供 OpenAI 兼容的 API 格式：
  /v1/chat/completions  → 对话补全（非流式 + 流式）
  /v1/embeddings        → 文本向量嵌入（RAG 检索用）
  /v1/rerank            → 文档重排序（RAG 精排用）

本类封装了四个核心能力：
  1. chat_completion()         → 非流式对话（用于意图分类、SQL生成等一次性任务）
  2. chat_completion_stream()  → 流式对话（用于知识问答、数据解读等需要逐字输出的场景）
  3. embedding()               → 文本向量化（用于 RAG 索引构建和检索）
  4. rerank()                  → 文档重排（用于 RAG 检索结果精排，提升相关性）

三个模型的分工：
  qwen3（对话模型）      → 生成自然语言回答
  bge-m3（嵌入模型）     → 把文本转为 1024 维向量
  bge-reranker-large    → 对检索结果重新排序，提升 Top-K 精度
"""
from typing import List, Dict, Optional, AsyncIterator
import httpx
from loguru import logger

from app.core.config import settings


class LLMClient:
    """大模型客户端（单例模式，模块级 llm_client 实例供全局使用）"""

    def __init__(self):
        self.base_url = f"{settings.XINFERENCE_BASE_URL}/v1"
        self.api_key = "not-needed"  # Xinference 自托管，无需 API Key
        self.model = settings.XINFERENCE_LLM_MODEL  # 默认对话模型：qwen3
        self.max_tokens = settings.LLM_MAX_TOKENS  # 最大输出 token 数
        self.temperature = settings.LLM_TEMPERATURE  # 温度参数（0=确定性，1=创造性）

    def _get_headers(self) -> Dict[str, str]:
        """获取请求头（OpenAI 兼容格式）"""
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
        非流式聊天补全（等待完整响应后返回）

        适用场景：意图分类、SQL 生成、Skill 执行 —— 这些场景需要完整结果才能继续处理
        超时：120 秒（非流式调用需要等待 LLM 完整生成）

        :param messages: OpenAI 格式消息列表 [{"role": "system/user/assistant", "content": "..."}]
        :param temperature: 温度参数覆盖（None 用默认值）
        :param max_tokens: 最大输出 token 覆盖
        :param model: 模型名称覆盖（支持切换不同模型）
        :return: LLM 生成的完整文本
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": False,  # 非流式模式
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
                # OpenAI 格式：choices[0].message.content 是完整文本
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
        流式聊天补全（逐块 yield 文本）

        适用场景：知识问答、数据解读、闲聊 —— 这些场景需要逐字输出以提供流畅体验
        超时：300 秒（流式调用保持长连接，超时设长一些避免中断）

        SSE 协议解析：
          每行格式：data: {json}
          终止标记：data: [DONE]
          每个 chunk 格式：{"choices": [{"delta": {"content": "文本块"}}]}

        :param messages: OpenAI 格式消息列表
        :yield: 逐块文本（前端拼接收集后得到完整回答）
        """
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "stream": True,  # 流式模式
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
                    # 逐行解析 SSE 流
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # 去掉 "data: " 前缀
                            if data == "[DONE]":
                                break  # 流结束标记
                            try:
                                import json
                                chunk = json.loads(data)
                                # delta.content 是增量文本块（非完整文本）
                                if chunk["choices"] and chunk["choices"][0].get("delta", {}).get("content"):
                                    yield chunk["choices"][0]["delta"]["content"]
                            except (json.JSONDecodeError, KeyError):
                                continue  # 跳过无法解析的行（如心跳包、空行）
            except Exception as e:
                logger.error(f"LLM流式调用失败: {e}")
                raise

    async def embedding(self, texts: List[str]) -> List[List[float]]:
        """
        获取文本嵌入向量（使用 bge-m3 模型）

        适用场景：RAG 知识库索引构建（文档切片→向量化→存入 pgvector）
                  RAG 检索时用户问题向量化（用于相似度搜索）

        bge-m3 模型输出 1024 维向量，支持中英文多语言

        :param texts: 待向量化的文本列表
        :return: 嵌入向量列表 [[0.01, 0.02, ...], ...]，每个向量 1024 维
        """
        payload = {
            "model": settings.XINFERENCE_EMBED_MODEL,  # bge-m3
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
        文档重排序（使用 bge-reranker-large 模型）

        适用场景：RAG 检索的精排阶段。向量检索（bge-m3）召回 TopK*3 条候选后，
                  用 rerank 模型对候选重新打分排序，取 TopK 条作为最终结果。
                  Rerank 模型比纯向量相似度更精准，因为它能理解 query 与 doc 的语义关系。

        :param query: 用户查询文本
        :param documents: 候选文档列表
        :param top_k: 返回前 K 条（默认用 settings.RERANK_TOP_K = 5）
        :return: 重排结果 [{"index": 原始索引, "relevance_score": 相关性分数}, ...]
        """
        payload = {
            "model": settings.XINFERENCE_RERANK_MODEL,  # bge-reranker-large
            "query": query,
            "documents": documents,
            "top_n": top_k or settings.RERANK_TOP_K,
            "return_documents": False,  # 只返回索引和分数，不返回文档内容
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


# 模块级单例：全局共享一个 LLMClient 实例
llm_client = LLMClient()
