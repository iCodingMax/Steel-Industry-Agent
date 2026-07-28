"""
大模型服务模块
统一封装LLM调用接口，支持通过Xinference部署的各类模型（OpenAI兼容协议）
主要功能：单轮对话、流式对话、意图分类

配置依赖：
- XINFERENCE_BASE_URL: Xinference服务基础地址
- XINFERENCE_LLM_MODEL: 大模型名称（如 qwen2-72b-instruct）
- LLM_MAX_TOKENS: 最大输出Token数
- LLM_TEMPERATURE: 温度参数（控制随机性）
"""
import httpx
import json
from typing import Optional, List, Dict
from loguru import logger

from app.core.config import settings


class LLMService:
    """
    大模型服务类
    封装与Xinference LLM服务的交互，提供统一的对话接口
    支持两种调用模式：
    1. 同步模式：一次性获取完整回复
    2. 流式模式：逐片段返回，提升用户体验
    """

    def __init__(self):
        """
        初始化大模型服务配置
        从全局配置中读取Xinference服务地址和模型参数
        """
        self.base_url = f"{settings.XINFERENCE_BASE_URL}/v1"
        self.api_key = "not-needed"
        self.model = settings.XINFERENCE_LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        logger.info(f"LLM服务初始化完成: base_url={self.base_url}, model={self.model}")

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
    ) -> str:
        """
        单轮同步对话
        一次性获取模型完整回复，适用于不需要实时反馈的场景（如意图分类、SQL生成）

        :param prompt: 用户输入的问题或指令
        :param system_prompt: 系统提示词，定义模型行为和角色
        :param history: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        :return: 模型生成的完整回复内容
        :raises Exception: 调用失败时抛出，包含详细错误信息
        """
        try:
            # 1. 构建消息列表
            messages = []

            # 添加系统提示词（如果有）
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                logger.debug(f"添加系统提示词，长度={len(system_prompt)}")

            # 添加对话历史（如果有）
            if history:
                messages.extend(history)
                logger.debug(f"添加对话历史，条数={len(history)}")

            # 添加用户当前输入
            messages.append({"role": "user", "content": prompt})

            # 2. 发起HTTP请求调用LLM
            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.debug(f"发起LLM调用: model={self.model}, prompt长度={len(prompt)}")
                response = await client.post(
                    f"{self.base_url}/chat/completions",
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

            # 3. 解析返回结果
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
            logger.error(f"LLM调用超时(300s): {e}")
            raise Exception(f"大模型调用超时(300s): 请检查模型服务状态或网络连接")
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
        config: Optional[Dict] = None,
    ):
        """
        流式对话
        逐片段返回模型生成内容，适用于需要实时显示回复的场景（如知识问答、数据分析）

        :param prompt: 用户输入的问题或指令
        :param system_prompt: 系统提示词，定义模型行为和角色
        :param history: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        :yield: 流式输出的文本片段，每次返回一个字符串
        :raises Exception: 调用失败时抛出，包含详细错误信息
        """
        try:
            # 1. 构建消息列表（与同步模式相同）
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                logger.debug(f"添加系统提示词，长度={len(system_prompt)}")

            if history:
                messages.extend(history)
                logger.debug(f"添加对话历史，条数={len(history)}")

            messages.append({"role": "user", "content": prompt})

            # 使用配置参数或默认值
            base_url = config.get('base_url', self.base_url) if config else self.base_url
            api_key = config.get('api_key', self.api_key) if config else self.api_key
            model = config.get('model', self.model) if config else self.model
            max_tokens = config.get('max_tokens', self.max_tokens) if config else self.max_tokens
            temperature = config.get('temperature', self.temperature) if config else self.temperature

            # 2. 发起流式HTTP请求
            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.debug(f"发起LLM流式调用: model={model}, prompt长度={len(prompt)}")
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()

                    # 3. 逐行解析流式响应
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]
                            if data_str == "[DONE]":
                                logger.debug("接收到流式结束标记 [DONE]")
                                break
                            try:
                                data = json.loads(data_str)
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    content = delta.get("content", "")
                                    if content:
                                        yield content
                            except json.JSONDecodeError:
                                logger.debug(f"JSON解析失败，跳过该行: {line[:100]}")
                                continue

            logger.info(f"LLM流式调用完成: 模型={self.model}")

        except httpx.HTTPStatusError as e:
            logger.error(f"LLM流式调用HTTP错误: status={e.response.status_code}")
            raise Exception(f"大模型流式调用失败(HTTP {e.response.status_code}): 请检查模型配置")
        except httpx.ConnectError as e:
            logger.error(f"LLM流式连接失败: {e}")
            raise Exception(f"大模型服务连接失败: 请检查 {self.base_url} 是否可访问")
        except httpx.TimeoutException as e:
            logger.error(f"LLM流式调用超时(300s): {e}")
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
        使用LLM对用户问题进行分类，决定路由到哪个处理通道

        :param question: 用户输入的问题
        :param system_prompt: 自定义分类提示词，为空时使用默认提示词
        :return: 分类结果，取值为 knowledge/data/hybrid
                 - knowledge: 知识问答通道（工艺知识、技术规范、问候语等）
                 - data: 数据查询通道（生产数据、指标统计、图表展示等）
                 - hybrid: 混合分析通道（同时包含知识和数据意图）
        """
        # 默认意图分类提示词
        # 设计原则：
        # 1. 简单问候语（hello、你好、hi）归类为knowledge，避免触发NL2SQL流程
        # 2. 纯数据查询归类为data，直接走NL2SQL或NL2Metrics
        # 3. 同时包含数据和知识要素的归类为hybrid，需要拆分处理
        default_prompt = """你是一个意图分类助手，请根据用户问题判断其意图类型。

分类规则：
- knowledge: 用户仅询问工艺知识、技术规范、操作规程、概念解释等文档类问题，以及问候语、闲聊等通用对话
- data: 用户仅查询生产数据、指标数值、统计报表、图表展示等数据类问题
- hybrid: 用户问题同时包含知识查询和数据查询两部分意图

判断要点：
- 如果问题中出现"展示"、"查询"、"统计"、"次数"、"数量"等数据相关关键词，同时出现"解释"、"什么是"、"原理"等知识相关关键词，则属于hybrid
- 包含"并且"、"同时"、"另外"、"以及"等连接词连接不同类型的问题时，通常属于hybrid
- 只要问题中有一部分涉及数据查询，另一部分涉及知识问答，就是hybrid
- 简单问候语（如hello、你好、hi等）属于knowledge意图

示例：
- "高炉炼铁的还原过程是什么" → knowledge
- "hello" → knowledge
- "你好" → knowledge
- "展示2023年8月的每日吹炼次数" → data
- "展示2023年8月的每日吹炼次数，并且解释什么是高炉炼铁的还原过程" → hybrid
- "转炉炼钢的吹炼制度有哪些？上个月吹炼次数是多少" → hybrid
- "什么是铁水预处理？同时统计一下近一周的钢水产量" → hybrid

请直接返回分类结果（knowledge/data/hybrid），不要返回其他内容。"""

        # 调用LLM进行分类
        result = await self.chat(
            prompt=question,
            system_prompt=system_prompt or default_prompt,
        )

        # 清理并验证分类结果
        intent = result.strip().lower()
        if intent not in ["knowledge", "data", "hybrid"]:
            logger.warning(f"意图分类结果异常: {result}，使用默认值 hybrid")
            intent = "hybrid"

        logger.info(f"意图分类完成: 问题={question[:50]}..., 结果={intent}")
        return intent


# 服务实例
llm_service = LLMService()
logger.info("LLM服务实例已创建，等待请求")