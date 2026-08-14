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
        config: Optional[Dict] = None,
    ) -> str:
        """
        单轮同步对话
        一次性获取模型完整回复，适用于不需要实时反馈的场景（如意图分类、SQL生成、Skill执行）

        :param prompt: 用户输入的问题或指令
        :param system_prompt: 系统提示词，定义模型行为和角色
        :param history: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        :param config: 应用级LLM配置（base_url, api_key, model, max_tokens, temperature），覆盖默认值
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

            # 使用配置参数或默认值（支持应用级配置覆盖）
            # 注意：config 中值为 None 时需 fallback 到默认值，避免传 null 给LLM服务导致500
            if config:
                base_url = config.get('base_url') or self.base_url
                api_key = config.get('api_key') or self.api_key
                model = config.get('model') or self.model
                max_tokens = config.get('max_tokens') or self.max_tokens
                temperature = config.get('temperature')
                if temperature is None:
                    temperature = self.temperature
            else:
                base_url = self.base_url
                api_key = self.api_key
                model = self.model
                max_tokens = self.max_tokens
                temperature = self.temperature

            # 2. 发起HTTP请求调用LLM
            # 对qwen3系列模型禁用thinking模式，避免Xinference解析reasoning_content时触发KeyError 'text'
            request_body = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if "qwen3" in model.lower():
                request_body["chat_template_kwargs"] = {"enable_thinking": False}
                logger.debug(f"检测到qwen3模型，已禁用thinking模式: model={model}")

            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.debug(f"发起LLM调用: model={model}, prompt长度={len(prompt)}")
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                # 先读取响应体，再解析JSON，最后检查状态码
                # 这样可以在raise_for_status()之前检测到FastAPI错误响应({"detail":"..."})
                raw_data = await response.aread()
                data = json.loads(raw_data)

            # 3. 解析返回结果
            # 3a. 检查是否为FastAPI错误响应（如 {"detail": "Model not found"}）
            #     必须在raise_for_status()之前检查，避免HTTPStatusError处理中触发KeyError
            if isinstance(data, dict) and "detail" in data and "choices" not in data:
                error_detail = data["detail"]
                if isinstance(error_detail, list):
                    error_detail = "; ".join(str(item) for item in error_detail)
                logger.error(f"LLM服务返回错误响应: detail={error_detail}, url={base_url}, model={model}")
                raise Exception(f"大模型服务返回错误: {error_detail} (base_url={base_url}, model={model})")

            # 3b. 检查HTTP状态码（非FastAPI错误的其他HTTP错误）
            response.raise_for_status()

            # 3c. 检查返回数据格式是否正确
            if (not data 
                or "choices" not in data 
                or not isinstance(data.get("choices"), list) 
                or len(data["choices"]) == 0
                or not isinstance(data["choices"][0], dict)
                or "message" not in data["choices"][0]
                or not isinstance(data["choices"][0]["message"], dict)):
                logger.error(f"LLM返回格式异常: raw_data={raw_data[:500] if raw_data else 'None'}")
                raise Exception("大模型返回格式异常：返回数据结构不符合预期")
            
            content = data["choices"][0]["message"].get("content", "")
            if content is None:
                content = ""
            logger.info(f"LLM调用完成: 模型={model}, 输入长度={len(prompt)}, 输出长度={len(content)}")
            return content

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response.text else ""
            logger.error(f"LLM调用HTTP错误: status={e.response.status_code}, body={error_body}")
            raise Exception(f"大模型调用失败(HTTP {e.response.status_code}): base_url={base_url}, model={model}, 服务端返回: {error_body}")
        except httpx.ConnectError as e:
            logger.error(f"LLM连接失败: {e}")
            raise Exception(f"大模型服务连接失败: 请检查 {self.base_url} 是否可访问")
        except httpx.TimeoutException as e:
            logger.error(f"LLM调用超时(300s): {e}")
            raise Exception(f"大模型调用超时(300s): 请检查模型服务状态或网络连接")
        except KeyError as e:
            import traceback
            raw_data_preview = raw_data[:500] if 'raw_data' in dir() and raw_data else 'N/A'
            logger.error(f"LLM返回格式异常(KeyError): 缺少键={e}, raw_data={raw_data_preview}\n{traceback.format_exc()}")
            raise Exception(f"大模型返回格式异常: 缺少键 {str(e)}, 响应内容: {raw_data_preview}")
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

            # 使用配置参数或默认值（与 chat 方法一致的 None 值处理）
            if config:
                base_url = config.get('base_url') or self.base_url
                api_key = config.get('api_key') or self.api_key
                model = config.get('model') or self.model
                max_tokens = config.get('max_tokens') or self.max_tokens
                temperature = config.get('temperature')
                if temperature is None:
                    temperature = self.temperature
            else:
                base_url = self.base_url
                api_key = self.api_key
                model = self.model
                max_tokens = self.max_tokens
                temperature = self.temperature

            # 2. 发起流式HTTP请求
            # 对qwen3系列模型禁用thinking模式，避免Xinference解析reasoning_content时触发KeyError 'text'
            request_body = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            if "qwen3" in model.lower():
                request_body["chat_template_kwargs"] = {"enable_thinking": False}
                logger.debug(f"检测到qwen3模型，已禁用thinking模式: model={model}")

            async with httpx.AsyncClient(timeout=300.0) as client:
                logger.debug(f"发起LLM流式调用: model={model}, prompt长度={len(prompt)}")
                async with client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
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
                                if ("choices" in data 
                                    and isinstance(data["choices"], list) 
                                    and len(data["choices"]) > 0
                                    and isinstance(data["choices"][0], dict)):
                                    delta = data["choices"][0].get("delta", {})
                                    if isinstance(delta, dict):
                                        content = delta.get("content", "")
                                        if content:
                                            yield content
                            except json.JSONDecodeError:
                                logger.debug(f"JSON解析失败，跳过该行: {line[:100]}")
                                continue

            logger.info(f"LLM流式调用完成: 模型={self.model}")

        except httpx.HTTPStatusError as e:
            error_body = e.response.text[:500] if e.response.text else ""
            logger.error(f"LLM流式调用HTTP错误: status={e.response.status_code}, body={error_body}")
            raise Exception(f"大模型流式调用失败(HTTP {e.response.status_code}): base_url={base_url}, model={model}, 服务端返回: {error_body}")
        except httpx.ConnectError as e:
            logger.error(f"LLM流式连接失败: {e}")
            raise Exception(f"大模型服务连接失败: 请检查 {self.base_url} 是否可访问")
        except httpx.TimeoutException as e:
            logger.error(f"LLM流式调用超时(300s): {e}")
            raise Exception(f"大模型流式调用超时: 请检查模型服务状态")
        except Exception as e:
            logger.error(f"LLM流式调用失败: {type(e).__name__}: {e}", exc_info=True)
            raise Exception(f"大模型流式调用失败: {type(e).__name__}: {str(e)}")

    async def classify_intent(
        self,
        question: str,
        system_prompt: Optional[str] = None,
        mcp_tools: Optional[List[Dict[str, str]]] = None,
        skill_tools: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        意图分类
        使用LLM对用户问题进行分类，决定路由到哪个处理通道

        :param question: 用户输入的问题
        :param system_prompt: 自定义分类提示词，为空时使用默认提示词
        :param mcp_tools: 可用MCP工具列表 [{"name": ..., "description": ...}]，
                          参考工具管理中已配置的MCP名称与描述
        :param skill_tools: 可用Skill工具列表 [{"name": ..., "description": ..., "file_name": ...}]，
                            参考工具管理中已配置的Skills名称、描述与文件
        :return: 分类结果，取值为 knowledge/data/mcp/skill/hybrid/chat
                 - chat: 闲聊对话通道（问候语、自我介绍、感谢等，直接用LLM回答，不检索知识库）
                 - knowledge: 知识问答通道（工艺知识、技术规范等，需要检索知识库）
                 - data: 数据查询通道（生产数据、指标统计、图表展示等）
                 - mcp: MCP工具调用通道（外部服务，如地图、天气等）
                 - skill: Skill工具调用通道（本地技能脚本执行）
                 - hybrid: 混合分析通道（仅包含知识问答+数据查询的组合）
        """
        # 构建MCP工具描述信息（参考工具管理中已配置的MCP名称与描述）
        if mcp_tools:
            mcp_tools_desc = "\n".join([
                f"- {t.get('name', '')}: {t.get('description', '无描述')}"
                for t in mcp_tools
            ])
        else:
            mcp_tools_desc = "(暂无配置MCP工具)"

        # 构建Skill工具描述信息（参考工具管理中已配置的Skills名称、描述与文件）
        if skill_tools:
            skill_tools_desc = "\n".join([
                f"- {t.get('name', '')}: {t.get('description', '无描述')}"
                + (f" (文件: {t['file_name']})" if t.get('file_name') else "")
                for t in skill_tools
            ])
        else:
            skill_tools_desc = "(暂无配置Skill工具)"

        # 默认意图分类提示词（六种意图类型）
        default_prompt = f"""你是一个智能意图分类助手，负责将用户问题归类为以下六种类型之一。

## 当前可用工具（参考工具管理中的配置）

### MCP工具（通过MCP协议调用的外部服务）
{mcp_tools_desc}

### Skill工具（本地技能脚本）
{skill_tools_desc}

## 分类规则（按优先级排序）

### 1. chat（闲聊对话）
当用户问题是简单问候、自我介绍、感谢等，不需要检索知识库时，归类为chat：
- 问候语：你好、您好、hello、hi、嗨
- 自我介绍：介绍下自己、你是谁、你能做什么
- 感谢/告别：谢谢、感谢、再见、拜拜
- 通用对话：简短的寒暄、闲聊
- **重要**：chat类问题直接用LLM回答，不需要检索知识库

### 2. mcp（MCP工具调用）
当用户问题需要调用上述MCP工具来获取实时信息或执行特定操作时，归类为mcp：
- 地理位置相关：地点查询、路线规划、导航、距离计算、地址解析
- 实时信息：天气查询、新闻、股票价格、汇率、实时数据
- 外部服务：地图服务、搜索服务、翻译服务、计算服务
- 关键词特征：地图、路线、天气、位置、地点、查询位置、怎么走、在哪里、导航、定位
- **重要**：如果用户问题与上述MCP工具的名称或描述在语义上匹配，应归类为mcp

### 3. skill（Skill工具调用）
**仅当用户明确要求执行技能时**，归类为skill：
- 用户明确说"高炉炉况诊断"、"执行高炉炉况诊断"、"执行炉况诊断技能"
- 用户明确说"使用技能"、"调用技能"、"运行技能"
- **重要**：普通的炉况相关问题（如"风压波动怎么回事"、"铁水硅高了"、"炉况不顺"等）
  **不归类为skill**，应归类为knowledge（知识问答），因为这些是知识咨询而非技能调用
- 只有用户明确表达"执行技能"意图时才归类为skill

### 4. data（数据查询）
当用户需要查询数据库中的业务数据时，归类为data：
- 生产数据：产量、合格率、能耗、设备状态、工艺参数
- 统计分析：报表、趋势、对比、排名、汇总
- 关键词特征：展示、查询、统计、多少、次数、数量、产量、合格率、能耗、报表、图表、趋势

### 5. hybrid（混合意图）
当用户问题同时包含知识问答和数据查询两种意图时，归类为hybrid：
- 注意：混合意图仅包含知识问答+数据查询的组合
- 不包含MCP/Skill与其他意图的组合（此类情况应优先判定为mcp或skill）
- 用"并且"、"同时"、"另外"、"以及"等连接词连接不同类型的问题

### 6. knowledge（知识问答）
当用户问题涉及工艺知识、技术规范等，需要从知识库检索信息时，归类为knowledge：
- 工艺知识：炼铁原理、炼钢工艺、轧钢流程
- 技术规范：操作规程、安全规范、技术标准
- 概念解释：什么是、如何理解、解释一下
- **注意**：简单问候语、自我介绍等不属于knowledge，应归类为chat

## 判断要点（重要）
1. 优先判断chat：简单问候、自我介绍、感谢等属于chat，直接用LLM回答
2. 优先判断mcp/skill：如果问题涉及外部工具调用或技能执行，优先归类为mcp或skill
3. **工具语义匹配**：仔细比对用户问题与可用工具列表中的名称和描述，
   如果问题语义与某个工具的描述场景匹配，应归类为对应的mcp或skill
4. 数据查询中的"查询"指的是查询内部数据库数据，不是外部服务
5. 混合意图仅限知识问答+数据查询的组合

## 示例
- "你好"、"hello"、"hi" → chat
- "介绍下自己"、"你是谁"、"你能做什么" → chat
- "谢谢"、"再见" → chat
- "高炉炼铁的还原过程是什么" → knowledge
- "高炉炉缸堆积有哪些表现" → knowledge
- "展示2023年8月的每日吹炼次数" → data
- "查询上个月的合格率" → data
- "查询武汉市的天气" → mcp
- "从北京到上海怎么走" → mcp
- "深圳南山区的位置在哪里" → mcp
- "帮我导航到最近的加油站" → mcp
- "执行Python脚本计算平均值" → skill
- "高炉炉况诊断" → skill
- "执行高炉炉况诊断技能" → skill
- "使用技能分析炉况" → skill
- "诊断炉况"、"炉况分析"、"分析高炉数据" → knowledge
- "炉子是不是不顺"、"风压波动怎么回事" → knowledge
- "铁水硅高了"、"要不要调风"、"料速慢了" → knowledge
- "展示2023年8月的每日吹炼次数，并且解释什么是高炉炼铁" → hybrid
- "当前压差不稳应该如何调整？同时展示近期产量数据" → hybrid

请直接返回分类结果（knowledge/data/mcp/skill/hybrid/chat），不要返回任何解释或额外内容。"""

        # 调用LLM进行分类
        result = await self.chat(
            prompt=question,
            system_prompt=system_prompt or default_prompt,
        )

        # 清理并验证分类结果
        intent = result.strip().lower()
        valid_intents = ["knowledge", "data", "mcp", "skill", "hybrid", "chat"]
        if intent not in valid_intents:
            logger.warning(f"意图分类结果异常: {result}，使用默认值 hybrid")
            intent = "hybrid"

        logger.info(f"意图分类完成: 问题={question[:50]}..., 结果={intent}")
        return intent


# 服务实例
llm_service = LLMService()
logger.info("LLM服务实例已创建，等待请求")