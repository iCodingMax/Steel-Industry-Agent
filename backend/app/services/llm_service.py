"""
大模型服务
统一封装LLM调用，支持OpenAI/国产模型切换
"""
import httpx
from typing import Optional, List, Dict
from loguru import logger

from app.core.config import settings


class LLMService:
    """大模型服务类"""

    def __init__(self):
        self.base_url = settings.NEWAPI_BASE_URL
        self.api_key = settings.NEWAPI_API_KEY
        self.model = settings.NEWAPI_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        """
        单轮对话
        :param prompt: 用户输入
        :param system_prompt: 系统提示词
        :param history: 对话历史
        :return: 模型回复
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            if history:
                messages.extend(history)

            messages.append({"role": "user", "content": prompt})

            import json
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                    },
                )
                response.raise_for_status()
                raw_data = await response.aread()
                data = json.loads(raw_data)

            content = data["choices"][0]["message"]["content"]
            logger.info(f"LLM调用完成: 模型={self.model}, 输入长度={len(prompt)}, 输出长度={len(content)}")
            return content

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM调用HTTP错误: status={e.response.status_code}, body={e.response.text[:500]}")
            raise Exception(f"大模型调用失败(HTTP {e.response.status_code}): 请检查模型配置，base_url={self.base_url}, model={self.model}")
        except httpx.ConnectError as e:
            logger.error(f"LLM连接失败: {e}")
            raise Exception(f"大模型服务连接失败: 请检查 {self.base_url} 是否可访问")
        except httpx.TimeoutException as e:
            logger.error(f"LLM调用超时: {e}")
            raise Exception(f"大模型调用超时(60s): 请检查模型服务状态或网络连接")
        except KeyError as e:
            logger.error(f"LLM返回格式异常: {e}, raw_data={data if 'data' in dir() else 'N/A'}")
            raise Exception(f"大模型返回格式异常: {str(e)}")
        except Exception as e:
            logger.error(f"LLM调用失败: {e}")
            raise Exception(f"大模型调用失败: {str(e)}")

    async def chat_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ):
        """
        流式对话
        :param prompt: 用户输入
        :param system_prompt: 系统提示词
        :param history: 对话历史
        :yield: 流式输出内容片段
        """
        try:
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})

            if history:
                messages.extend(history)

            messages.append({"role": "user", "content": prompt})

            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": self.max_tokens,
                        "temperature": self.temperature,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                import json
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                continue

            logger.info(f"LLM流式调用完成: 模型={self.model}")

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM流式调用HTTP错误: status={e.response.status_code}")
            raise Exception(f"大模型流式调用失败(HTTP {e.response.status_code}): 请检查模型配置")
        except httpx.ConnectError as e:
            logger.error(f"LLM流式连接失败: {e}")
            raise Exception(f"大模型服务连接失败: 请检查 {self.base_url} 是否可访问")
        except httpx.TimeoutException as e:
            logger.error(f"LLM流式调用超时: {e}")
            raise Exception(f"大模型流式调用超时: 请检查模型服务状态")
        except Exception as e:
            logger.error(f"LLM流式调用失败: {e}")
            raise Exception(f"大模型流式调用失败: {str(e)}")

    async def classify_intent(
        self,
        question: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        意图分类
        :param question: 用户问题
        :param system_prompt: 分类提示词
        :return: 分类结果（knowledge/data/hybrid）
        """
        default_prompt = """你是一个意图分类助手，请根据用户问题判断其意图类型。

分类规则：
- knowledge: 用户询问工艺知识、技术规范、操作规程等文档类问题
- data: 用户查询生产数据、指标数值、统计报表等数据类问题
- hybrid: 用户问题同时涉及知识查询和数据查询

请直接返回分类结果（knowledge/data/hybrid），不要返回其他内容。"""

        result = await self.chat(
            prompt=question,
            system_prompt=system_prompt or default_prompt,
        )
        # 清理结果
        intent = result.strip().lower()
        if intent not in ["knowledge", "data", "hybrid"]:
            intent = "hybrid"  # 默认混合模式

        logger.info(f"意图分类完成: 问题={question}, 结果={intent}")
        return intent


# 服务实例
llm_service = LLMService()