"""
大模型服务模块（LLM Service Layer）
统一封装LLM调用接口，支持通过Xinference部署的各类模型（OpenAI兼容协议）

=============================================================================
架构定位（面试重点）：
  本模块属于「业务服务层」，位于 API路由层(chat.py) 和 基础设施层(llm_client.py) 之间。
  职责是将「对话业务逻辑」与「LLM调用细节」解耦：
    - chat.py 路由层 只管 HTTP请求/响应 和 SSE协议
    - llm_service.py 服务层 管 意图分类、历史嵌入、错误处理等业务逻辑
    - llm_client.py 基础设施层 管 HTTP请求发送和SSE流解析

  设计模式：门面模式（Facade）—— 对外暴露简化的 chat/chat_stream/classify_intent 三个方法，
  内部封装了消息构建、配置覆盖、模型适配、异常分类等复杂逻辑。
=============================================================================

主要功能：
  1. chat()           —— 同步对话：一次性获取完整回复（用于意图分类、SQL生成等非实时场景）
  2. chat_stream()    —— 流式对话：逐字返回回复（用于知识问答、数据解读等需要实时显示的场景）
  3. classify_intent()—— 意图分类：将用户问题路由到 knowledge/data/mcp/skill/hybrid/chat 六大通道

配置依赖（从 .env 环境变量加载）：
  - XINFERENCE_BASE_URL: Xinference推理服务地址（自托管，OpenAI兼容API）
  - XINFERENCE_LLM_MODEL: 大模型名称（如 qwen3-32b）
  - LLM_MAX_TOKENS: 最大输出Token数（控制回复长度上限）
  - LLM_TEMPERATURE: 温度参数（0=确定性输出，1=创造性输出，知识问答建议0.3）
  - CHAT_HISTORY_LIMIT: 对话历史窗口大小（默认10条，控制多轮对话上下文长度）

面试考点：
  Q: 为什么不用 LangChain 的 LLMChain？
  A: LangChain 封装层级过深，对流式输出和错误处理的精细控制不足。
     本项目直接用 httpx 调用 OpenAI兼容API，可以精确控制超时、SSE解析、异常分类。
  Q: 为什么 chat_stream 要把历史嵌入 prompt 而不是用 messages 数组？
  A: 见 chat_stream 方法内的详细注释（LLM容易忽略 messages 中的历史，尤其当 system_prompt 角色定义过强时）。
"""
import httpx
import json
from typing import Optional, List, Dict
from loguru import logger

from app.core.config import settings


class LLMService:
    """
    大模型服务类（核心业务服务）
    封装与Xinference LLM服务的交互，提供统一的对话接口

    支持两种调用模式：
      1. 同步模式（chat）        —— 一次性获取完整回复，用于意图分类、SQL生成等不需要实时显示的场景
      2. 流式模式（chat_stream） —— 逐片段返回文本，用于知识问答、数据解读等需要逐字显示的场景

    应用级配置覆盖机制：
      每个应用可在「模型配置」页面自定义 LLM 的 base_url/api_key/model/max_tokens/temperature，
      通过 config 参数传入，覆盖默认的系统级配置。这实现了「多应用多模型」的灵活部署。
    """

    def __init__(self):
        """
        初始化大模型服务配置（系统级默认值）
        从全局配置 settings 中读取 Xinference 服务地址和模型参数。

        注意：这里的配置是系统级默认值，具体调用时可通过 config 参数覆盖（应用级配置）。
        配置优先级：应用级 config > 系统级 settings（依赖注入思想）
        """
        self.base_url = f"{settings.XINFERENCE_BASE_URL}/v1"
        self.api_key = "not-needed"  # Xinference 自托管服务，无需 API Key 鉴权
        self.model = settings.XINFERENCE_LLM_MODEL  # 默认对话模型（如 qwen3-32b）
        self.max_tokens = settings.LLM_MAX_TOKENS  # 最大输出Token数
        self.temperature = settings.LLM_TEMPERATURE  # 温度参数（0=确定性，1=创造性）
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
            # 配置优先级链路：前端传入的 llmConfigId → 应用配置的 model_name → 系统默认LLM配置
            # 注意：config 中值为 None 时需 fallback 到默认值，避免传 null 给LLM服务导致500
            # 这是因为前端可能只配置了部分参数（如只改了temperature），其余参数为null
            if config:
                base_url = config.get('base_url') or self.base_url
                api_key = config.get('api_key') or self.api_key
                model = config.get('model') or self.model
                max_tokens = config.get('max_tokens') or self.max_tokens
                temperature = config.get('temperature')
                if temperature is None:  # temperature=0 是合法值，必须用 is None 判断
                    temperature = self.temperature
            else:
                base_url = self.base_url
                api_key = self.api_key
                model = self.model
                max_tokens = self.max_tokens
                temperature = self.temperature

            # 2. 发起HTTP请求调用LLM
            # 对qwen3系列模型禁用thinking模式（面试考点）：
            #   qwen3 默认开启 thinking 模式，输出中会包含 reasoning_content 字段。
            #   Xinference 的 OpenAI兼容层在解析时尝试访问 delta.text 会触发 KeyError，
            #   因为 thinking 模式下增量内容放在 reasoning_content 而非 content 字段。
            #   解决方案：通过 chat_template_kwargs.enable_thinking=False 显式关闭。
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
                try:
                    data = json.loads(raw_data)
                except (json.JSONDecodeError, ValueError) as decode_err:
                    raw_preview = raw_data[:500].decode('utf-8', errors='replace') if isinstance(raw_data, (bytes, bytearray)) else str(raw_data)[:500]
                    logger.error(
                        f"LLM响应JSON解析失败: status_code={response.status_code}, "
                        f"content_type={response.headers.get('content-type')}, raw前500={raw_preview}"
                    )
                    raise Exception(
                        f"大模型响应格式错误（非JSON）: HTTP {response.status_code}, "
                        f"响应内容前500字符: {raw_preview}"
                    ) from decode_err

            # 3. 解析返回结果（多层防御策略，面试考点）
            # 按顺序执行三道检查，任何一道失败都会抛出带有诊断信息的异常：
            #
            # 3a. FastAPI错误响应检查 —— Xinference返回的JSON body可能不是标准OpenAI格式，
            #     而是FastAPI的错误结构 {"detail": "..."}（如模型不存在、参数错误等）。
            #     必须在 raise_for_status() 之前检查，因为 raise_for_status() 触发的
            #     HTTPStatusError 异常处理器中访问 data["choices"] 会触发二次 KeyError。
            #
            # 3b. HTTP状态码检查 —— 标准HTTP错误（如500/502/503），
            #     raise_for_status() 会在非2xx状态码时抛出 HTTPStatusError。
            #
            # 3c. 返回数据结构校验 —— 即使HTTP 200，也要检查 choices 数组是否完整，
            #     防止 Xinference 返回格式异常导致后续 KeyError。

            # 3a. 检查是否为FastAPI错误响应（如 {"detail": "Model not found"}）
            if isinstance(data, dict) and "detail" in data and "choices" not in data:
                error_detail = data["detail"]
                if isinstance(error_detail, list):  # FastAPI验证错误返回列表
                    error_detail = "; ".join(str(item) for item in error_detail)
                logger.error(f"LLM服务返回错误响应: detail={error_detail}, url={base_url}, model={model}")
                raise Exception(f"大模型服务返回错误: {error_detail} (base_url={base_url}, model={model})")

            # 3b. 检查HTTP状态码（非FastAPI错误的其他HTTP错误）
            response.raise_for_status()

            # 3c. 检查返回数据格式是否正确（防御性编程）
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

            # 检测 finish_reason，判断是否因 max_tokens 截断
            finish_reason = data["choices"][0].get("finish_reason", "")
            if finish_reason == "length":
                logger.warning(
                    f"LLM响应因max_tokens限制被截断! 模型={model}, "
                    f"max_tokens={max_tokens}, 输出长度={len(content)}"
                )
                content += "\n\n⚠️ **输出已截断**：本次回复因达到最大输出长度限制而不完整，请减少输入内容或增加max_tokens后重试。"

            logger.info(f"LLM调用完成: 模型={model}, 输入长度={len(prompt)}, 输出长度={len(content)}, finish_reason={finish_reason}")
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
            # 安全地获取 raw_data 预览（防止局部变量在某些异步分支中不可达）
            raw_data_preview = 'N/A'
            try:
                if 'raw_data' in locals() and raw_data is not None:
                    preview_bytes = raw_data[:500] if isinstance(raw_data, (bytes, bytearray)) else str(raw_data)[:500]
                    raw_data_preview = preview_bytes.decode('utf-8', errors='replace') if isinstance(preview_bytes, (bytes, bytearray)) else str(preview_bytes)
            except Exception:
                pass
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
            # 1. 构建消息列表
            messages = []

            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
                logger.debug(f"添加系统提示词，长度={len(system_prompt)}")

            # 关键修复：历史上下文嵌入策略（面试重点 —— 多轮对话上下文丢失问题）
            #
            # 问题背景：
            #   传统做法是把对话历史通过 messages 数组传递（[{role:user,content:...},{role:assistant,...}]），
            #   但实际测试发现 LLM 经常忽略 messages 中的历史内容。
            #   原因：当应用配置了自定义 system_prompt 且角色定义过强时，
            #         LLM 的注意力集中在 system_prompt 上，容易忽略 messages 中的历史。
            #
            # 解决方案：把历史直接嵌入到 user prompt 中（而非 messages 数组）
            #   1. 用 ===对话历史开始=== 和 ===对话历史结束=== 分隔符包裹历史内容
            #   2. 明确告知"必须参考对话历史"
            #   3. 消歧代词：明确指出"问题中的'我'指的是用户，不是助手"（代词消歧）
            #   4. 给出示例引导：历史中用户说'我叫小明'→问'我叫什么'→回答'小明'
            #
            # 三层保障机制（intent classification + history embedding + pronoun disambiguation）：
            #   第一层：意图分类确保"我叫小明"等自我介绍被路由到 chat 通道（不经过RAG/SQL分流）
            #   第二层：历史嵌入确保 LLM 能看到完整上下文（本段代码）
            #   第三层：代词消歧确保"我"被正确理解为用户而非助手
            effective_prompt = prompt
            if history and len(history) > 0:
                history_text = "\n".join([
                    f"{'用户' if m.get('role') == 'user' else '助手'}: {m.get('content', '')}"
                    for m in history
                ])
                effective_prompt = (
                    f"请先阅读以下对话历史，然后回答当前问题。\n\n"
                    f"===对话历史开始===\n{history_text}\n===对话历史结束===\n\n"
                    f"当前问题：{prompt}\n\n"
                    f"回答要求：\n"
                    f"1. 必须参考对话历史中的信息\n"
                    f"2. 问题中的'我'指的是用户，不是助手\n"
                    f"3. 如果用户在历史中提供过姓名等信息，必须用该信息回答\n"
                    f"例如：历史中用户说'我叫小明'，当用户问'我叫什么'时，回答'小明'"
                )
                logger.info(f"已将{len(history)}条历史嵌入prompt, 历史预览={history_text[:100]}")

            messages.append({"role": "user", "content": effective_prompt})

            # 详细日志：输出最终发送给LLM的messages列表，便于排查上下文丢失问题
            messages_preview = "; ".join([f"[{m['role']}] {m['content'][:80]}" for m in messages])
            logger.info(f"[chat_stream] 发送给LLM的messages: 总条数={len(messages)}, 内容=[{messages_preview}]")

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

                    # 3. 逐行解析 SSE 流式响应（Server-Sent Events 协议）
                    # SSE 协议格式：每行以 "data: " 前缀开头，后面跟 JSON 数据
                    # 终止标记："data: [DONE]" 表示流结束
                    #
                    # 每个 chunk 的 JSON 结构：
                    # {"choices": [{"delta": {"content": "增量文本块"}, "finish_reason": null}]}
                    # delta.content 是增量文本（非完整文本），前端拼接后得到完整回答
                    #
                    # 面试考点 —— SSE vs WebSocket：
                    #   SSE 是单向通信（服务器→客户端），基于HTTP，实现简单，适合LLM流式输出。
                    #   WebSocket 是双向通信，实现复杂，适合需要客户端实时交互的场景。
                    #   本项目选择 SSE 是因为 LLM 流式输出只需服务器→客户端的单向推送。
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data_str = line[6:]  # 去掉 "data: " 前缀
                            if data_str == "[DONE]":
                                logger.debug("接收到流式结束标记 [DONE]")
                                break
                            try:
                                data = json.loads(data_str)
                                # 防御性检查：确保 choices 数组存在且非空
                                if ("choices" in data
                                    and isinstance(data["choices"], list)
                                    and len(data["choices"]) > 0
                                    and isinstance(data["choices"][0], dict)):
                                    delta = data["choices"][0].get("delta", {})
                                    if isinstance(delta, dict):
                                        content = delta.get("content", "")
                                        if content:  # content 可能为空（如首帧只有 role 信息）
                                            yield content  # 逐块 yield 给上层路由
                            except json.JSONDecodeError:
                                # 跳过无法解析的行（如心跳包、空行、注释行）
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
        意图分类（Intent Classification —— 智能路由的核心）

        使用 LLM 对用户问题进行分类，决定路由到哪个处理通道。
        这是整个对话系统的「大脑」，决定了问题被送往哪个子系统处理。

        三级级联意图识别策略（面试重点）：
          第一级：关键词快速预判（chat.py 中的 STRONG_TOOL_KEYWORDS 等）
                  —— 对"高炉炉况诊断"、"执行技能"等明确表达做快速判断，不调LLM
          第二级：工具名称精确匹配（chat.py 中的工具匹配逻辑）
                  —— 与已注册的 MCP/Skill 工具名做语义匹配
          第三级：LLM 分类增强（本方法）
                  —— 对无法预判的问题，用LLM做语义级分类

        六大意图通道：
          chat      → 闲聊对话（问候、自我介绍、感谢）→ 直接LLM回答
          knowledge → 知识问答（工艺原理、技术规范）→ RAG检索
          data      → 数据查询（产量、合格率、报表）→ NL2SQL
          mcp       → MCP工具调用（地图、天气等外部服务）→ MCP协议
          skill     → Skill工具调用（本地技能脚本）→ Skill执行引擎
          hybrid    → 混合分析（知识问答+数据查询组合）→ 拆分后分别处理

        :param question: 用户输入的问题
        :param system_prompt: 自定义分类提示词，为空时使用内置默认提示词
        :param mcp_tools: 可用MCP工具列表 [{"name": ..., "description": ...}]，
                          参考工具管理中已配置的MCP名称与描述
        :param skill_tools: 可用Skill工具列表 [{"name": ..., "description": ..., "file_name": ...}]，
                            参考工具管理中已配置的Skills名称、描述与文件
        :return: 分类结果（knowledge/data/mcp/skill/hybrid/chat），异常时默认返回 hybrid
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

        # 调用 LLM 进行分类（使用同步 chat 方法，因为分类不需要流式输出）
        result = await self.chat(
            prompt=question,
            system_prompt=system_prompt or default_prompt,
        )

        # 清理并验证分类结果（防御性编程）
        # LLM 可能返回带额外文字的结果（如 "我认为应该归类为 knowledge"），需提取关键词
        intent = result.strip().lower()
        valid_intents = ["knowledge", "data", "mcp", "skill", "hybrid", "chat"]
        if intent not in valid_intents:
            # 尝试从结果中提取有效意图词（LLM 可能输出解释性文字）
            for valid_intent in valid_intents:
                if valid_intent in intent:
                    intent = valid_intent
                    break
            else:
                # 兜底策略：无法识别时默认 hybrid（走混合通道，最安全）
                logger.warning(f"意图分类结果异常: {result}，使用默认值 hybrid")
                intent = "hybrid"

        logger.info(f"意图分类完成: 问题={question[:50]}..., 结果={intent}")
        return intent


# 服务实例
llm_service = LLMService()
logger.info("LLM服务实例已创建，等待请求")