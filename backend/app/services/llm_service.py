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
  3. classify_intent()—— 意图分类：将用户问题路由到 knowledge/data/mcp/skill/chat 五大通道
                         （M4改造：hybrid混合通道已下线，复合问题统一归类knowledge）

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
import re
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

    @staticmethod
    def _build_multi_turn_instruction() -> str:
        """
        构建多轮对话指令模板（注入到 system_prompt 末尾）

        设计目标：
          - 引导 LLM 主动参考 messages 数组中的对话历史
          - 解决代词消歧问题（"我"指用户而非助手）
          - 保留用户在历史中提供的姓名等关键信息

        适用场景：当 history 非空时，附加到 system_prompt 末尾。
        不替换原有 system_prompt，避免破坏应用角色定义。

        :return: 多轮对话指令字符串
        """
        return (
            "\n\n## 多轮对话要求\n"
            "1. 必须参考对话历史中的信息回答当前问题\n"
            "2. 问题中的'我'指的是用户，不是助手\n"
            "3. 如果用户在历史中提供过姓名等信息，必须用该信息回答\n"
            "例如：历史中用户说'我叫小明'，当用户问'我叫什么'时，回答'小明'"
        )

    def _build_messages(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        max_history_chars: int = 30000,
    ) -> List[Dict]:
        """
        构建 OpenAI 标准消息列表（chat 与 chat_stream 共用）

        方案B：把历史放入 messages 数组的 history 中，符合 OpenAI 兼容协议。
        优点：
          - 角色权重正确（user/assistant 区分明确，模型能正确理解对话流）
          - token 效率高（无额外指令和分隔符开销）
          - 便于 token 预算管理（可按 message 精确计算）

        当 history 非空时，自动在 system_prompt 末尾追加多轮对话指令，
        引导 LLM 主动参考历史并完成代词消歧。

        token 预算管理：
          - 估算总字符数（中文约1字符≈1.5 token）
          - 超过 max_history_chars 时，从最旧的历史消息开始丢弃
          - 保留 system_prompt 和当前 user 输入不被丢弃
          - 默认 30000 字符 ≈ 45000 token，对应 qwen3 的 40960 token 上下文留出安全余量

        :param prompt: 用户当前问题
        :param system_prompt: 应用级系统提示词（角色定义等）
        :param history: 对话历史列表 [{"role": "user/assistant", "content": "文本"}]
        :param max_history_chars: 历史部分最大字符数（超出则从最旧开始丢弃）
        :return: OpenAI 标准 messages 数组
        """
        messages: List[Dict] = []

        # 1. 构建增强后的 system_prompt（注入多轮对话指令）
        effective_system_prompt = system_prompt
        if history and len(history) > 0:
            multi_turn_instruction = self._build_multi_turn_instruction()
            if system_prompt:
                effective_system_prompt = system_prompt + multi_turn_instruction
            else:
                # 未配置 system_prompt 时，仅用多轮对话指令作为 system 角色
                effective_system_prompt = (
                    "你是一个智能助手，请参考对话历史回答用户问题。" + multi_turn_instruction
                )
            logger.debug(f"已注入多轮对话指令到system_prompt, 历史条数={len(history)}")

        if effective_system_prompt:
            messages.append({"role": "system", "content": effective_system_prompt})
            logger.debug(f"添加系统提示词，长度={len(effective_system_prompt)}")

        # 2. token 预算管理：从最旧历史开始丢弃超限部分
        #    策略：保留 system_prompt 和当前 user 输入的预算，剩余分配给历史
        #    history 中按时间正序排列（最旧在前），从最旧开始丢弃
        trimmed_history = list(history) if history else []
        if trimmed_history:
            system_chars = len(effective_system_prompt) if effective_system_prompt else 0
            prompt_chars = len(prompt)
            # 历史可用预算 = 总预算 - system - 当前问题 - 安全余量(500)
            history_budget = max(0, max_history_chars - system_chars - prompt_chars - 500)

            # 计算历史总字符数
            total_history_chars = sum(len(m.get("content", "")) for m in trimmed_history)
            if total_history_chars > history_budget:
                # 从最旧开始丢弃，直到总字符数 <= 预算
                dropped_count = 0
                while trimmed_history and total_history_chars > history_budget:
                    dropped = trimmed_history.pop(0)  # 最旧的消息在列表头部
                    total_history_chars -= len(dropped.get("content", ""))
                    dropped_count += 1
                logger.warning(
                    f"历史token预算管理: 总字符={sum(len(m.get('content', '')) for m in (history or []))}, "
                    f"预算={history_budget}, 丢弃最旧消息={dropped_count}条, 保留={len(trimmed_history)}条"
                )

            messages.extend(trimmed_history)
            logger.debug(f"添加对话历史到messages数组，条数={len(trimmed_history)}")

        # 3. 添加用户当前输入
        messages.append({"role": "user", "content": prompt})

        return messages

    def _apply_thinking_config(
        self,
        request_body: Dict,
        model: Optional[str],
        config: Optional[Dict] = None,
    ) -> None:
        """
        思考模式三态配置（P0-5，公共方法收敛 4 处硬编码）

        优先级链：应用级 config.enable_thinking → 系统级 settings.LLM_ENABLE_THINKING → 模型默认
        三态语义：
          True  → 强制开启：注入开启参数（GLM 系用 thinking.type=enabled，其余用 chat_template_kwargs）
          False → 强制关闭：注入关闭参数
          None  → 模型默认：qwen3 系自动关思考（防 reasoning_content 解析异常），其他模型不加参数

        :param request_body: LLM 请求体（原地修改）
        :param model: 模型名称
        :param config: 应用级 LLM 配置（可携带 enable_thinking 三态值）
        """
        # 1. 解析三态取值：应用级 > 系统级 > None（模型默认）
        _thinking = None
        if config and config.get('enable_thinking') is not None:
            _thinking = bool(config['enable_thinking'])
        elif settings.LLM_ENABLE_THINKING is not None:
            _thinking = settings.LLM_ENABLE_THINKING

        _model_lower = (model or '').lower()

        if _thinking is True:
            # 强制开启
            if 'glm' in _model_lower:
                # GLM-4.5+/GLM-5 系 hybrid-thinking 官方参数
                request_body["thinking"] = {"type": "enabled"}
            else:
                # vLLM Qwen3 系官方透传参数
                request_body["chat_template_kwargs"] = {"enable_thinking": True}
            logger.debug(f"思考模式强制开启: model={model}")
        elif _thinking is False:
            # 强制关闭
            if 'glm' in _model_lower:
                request_body["thinking"] = {"type": "disabled"}
            else:
                request_body["chat_template_kwargs"] = {"enable_thinking": False}
            logger.debug(f"思考模式强制关闭: model={model}")
        else:
            # 模型默认：qwen3 系自动关思考（Xinference 旧版解析 reasoning_content 触发 KeyError 'text'，vLLM 保留此防御）
            if 'qwen3' in _model_lower:
                request_body["chat_template_kwargs"] = {"enable_thinking": False}
                logger.debug(f"模型默认策略：qwen3 系自动关闭 thinking: model={model}")

    async def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict]] = None,
        config: Optional[Dict] = None,
        enable_short_output_detection: bool = False,
    ) -> str:
        """
        单轮同步对话
        一次性获取模型完整回复，适用于不需要实时反馈的场景（如意图分类、SQL生成、Skill执行）

        :param enable_short_output_detection: 是否启用短输出截断检测（仅Skill执行需要，MCP等场景不需要）

        历史传递方式（方案B）：通过 messages 数组的 history 传递，符合 OpenAI 标准。
        当 history 非空时自动注入多轮对话指令到 system_prompt。

        :param prompt: 用户输入的问题或指令
        :param system_prompt: 系统提示词，定义模型行为和角色
        :param history: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        :param config: 应用级LLM配置（base_url, api_key, model, max_tokens, temperature），覆盖默认值
        :return: 模型生成的完整回复内容
        :raises Exception: 调用失败时抛出，包含详细错误信息
        """
        try:
            # 1. 构建消息列表（统一使用 _build_messages 公共方法）
            messages = self._build_messages(prompt, system_prompt, history)

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

            # P2修复：max_tokens 自动下调，避免 prompt+max_tokens 超过 context_length
            # 原因：LLM_MAX_TOKENS 设为 40960（等于 context_length）时，
            #   随着对话轮数增加，prompt 越来越长，prompt+max_tokens 会超过 40960，
            #   导致 vLLM 报错 [pid=xxx] 'text'。
            # 方案：估算 messages 总 token 数，自动下调 max_tokens，
            #   确保 prompt + max_tokens ≤ context_length - safety_margin
            _model_lower = (model or '').lower()

            # 2a. 识别模型 context_length（与 skill_executor_service.py 保持一致）
            _model_context_length = 65536  # 未识别模型默认 64k
            if any(k in _model_lower for k in ['qwen3', 'qwen2.5', 'qwen2']):
                _model_context_length = 40960   # 与 Xinference 实际部署一致
            elif any(k in _model_lower for k in ['glm4', 'glm-4', 'glm5', 'glm-5']):
                _model_context_length = 131072
            elif 'glm' in _model_lower:
                _model_context_length = 65536
            elif any(k in _model_lower for k in ['gemma4', 'gemma-4']):
                _model_context_length = 131072
            elif 'gemma' in _model_lower:
                _model_context_length = 65536
            elif 'deepseek' in _model_lower or 'gpt' in _model_lower:
                _model_context_length = 131072

            # 2b. 估算 messages 总 token 数（system_prompt + history + 当前问题）
            # 中文约1字符≈1.5 token，加上 JSON 格式开销（role/content 等字段）
            _messages_total_chars = 0
            for _msg in messages:
                _messages_total_chars += len(_msg.get('content') or '')
                _messages_total_chars += 20  # role 等字段开销
            _estimated_prompt_tokens = int(_messages_total_chars * 1.5)

            # 2c. 计算 available_max_tokens 并自动下调
            _safety_margin = 1000
            _available_max_tokens = _model_context_length - _estimated_prompt_tokens - _safety_margin
            if _available_max_tokens < 1024:
                # 极端情况：prompt 已接近 context_length，给最小输出空间
                _available_max_tokens = 1024
                logger.warning(
                    f"Prompt过长接近context_length极限: "
                    f"估算prompt_token={_estimated_prompt_tokens}, "
                    f"context_length={_model_context_length}, "
                    f"available={_available_max_tokens}（已降至最低1024）"
                )

            _original_max_tokens = max_tokens
            if max_tokens > _available_max_tokens:
                max_tokens = _available_max_tokens
                logger.info(
                    f"max_tokens自动下调: 原值={_original_max_tokens}, "
                    f"下调后={max_tokens} "
                    f"(context={_model_context_length}, "
                    f"估算prompt_token={_estimated_prompt_tokens}, "
                    f"safety_margin={_safety_margin})"
                )

            request_body = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            # P0-5：思考模式三态配置（应用级/系统级/模型默认）
            self._apply_thinking_config(request_body, model, config)

            async with httpx.AsyncClient(timeout=300.0) as client:
                # P2修复：提升日志级别到info并补全请求关键信息（调试模型是否正确使用gemma4:e4b）
                logger.info(
                    f"发起LLM chat调用: model={model!r}, base_url={base_url}, "
                    f"max_tokens={max_tokens}, temperature={temperature}, "
                    f"prompt长度={len(prompt)}, 历史条数={len(history) if history else 0}"
                )
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
                # P2修复：给出更友好的截断提示 + 具体操作指引
                # 让用户知道除了增加max_tokens还可以直接续问缺失章节
                # Skill 场景会在 skill_executor_service 中检测到此标记后自动续写
                content += (
                    "\n\n⚠️ **输出已完成**：如需更详细内容，请继续提问以补充所需信息。"
                )
            elif finish_reason == "stop" and len(content) < 3000 and enable_short_output_detection:
                # P2修复：检测LLM提前停止输出（疑似偷懒）
                # 仅在Skill执行场景启用（enable_short_output_detection=True）
                # MCP工具调用等场景不启用，避免短回复被误判为截断
                logger.warning(
                    f"LLM响应过短疑似提前停止! 模型={model}, finish_reason={finish_reason}, "
                    f"输出长度={len(content)}, 输入长度={len(prompt)} "
                    f"(Skill执行场景，系统将自动检测章节完整性)"
                )
                content += (
                    "\n\n⚠️ **输出已完成**：如需更详细内容，请继续提问以补充所需信息。"
                )

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

    # prompt-based 工具调用标记（用于不支持原生 function-calling 的模型）
    _TOOL_CALL_START = "<function_call>"
    _TOOL_CALL_END = "</function_call>"

    @staticmethod
    def _format_tools_for_prompt(tools: List[Dict]) -> str:
        """
        将 OpenAI 格式的 tools 列表转成可读的文本描述（用于 prompt-based 降级）

        :param tools: OpenAI tools 格式列表
        :return: 注入 system prompt 的工具描述文本
        """
        lines = ["你可以调用以下工具来获取外部数据。如果需要调用工具，请严格按照规定格式输出，不要调用则正常回答：\n"]
        for i, t in enumerate(tools, 1):
            func = t.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")[:300]
            params = func.get("parameters", {})

            # 参数描述
            props = params.get("properties", {}) if isinstance(params, dict) else {}
            required_fields = params.get("required", []) if isinstance(params, dict) else []
            param_lines = []
            for pname, pinfo in props.items():
                if isinstance(pinfo, dict):
                    ptype = pinfo.get("type", "any")
                    pdesc = pinfo.get("description", "")[:100]
                    marker = "*" if pname in required_fields else " "
                    param_lines.append(f"  - {marker} {pname}({ptype}): {pdesc}")
                else:
                    param_lines.append(f"  - {pname}")

            lines.append(f"{i}. **{name}**: {desc}")
            if param_lines:
                lines.append("   参数：")
                lines.extend(param_lines)
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _parse_tool_calls_from_text(content: str) -> List[Dict]:
        """
        从 LLM 文本回复中解析结构化的工具调用标记

        支持多种标签格式（LLM 有时会偏离 prompt 指定的格式）：
        1. <function_call>{"name":"...","arguments":{...}}</function_call>  （标准格式）
        2. <tool_call>{"name":"...","arguments":{...}}</tool_call>          （LLM 自发变体）
        3. 多个标记可串联出现

        :param content: LLM 纯文本回复
        :return: OpenAI tool_calls 格式列表
        """
        tool_calls = []
        if not content:
            return tool_calls

        import re as _re
        # 兼容 <function_call> 和 <tool_call> 两种标签（LLM 有时会自发换标签）
        _start_alt = r'(?:function_call|tool_call|invoke|call_tool)'
        _end_alt = r'(?:/function_call|/tool_call|/invoke|/call_tool)'
        pattern = _re.compile(
            r'<' + _start_alt + r'>(.*?)<' + _end_alt + r'>',
            _re.DOTALL | _re.IGNORECASE,
        )

        for idx, match in enumerate(pattern.finditer(content)):
            json_str = match.group(1).strip()
            try:
                parsed = json.loads(json_str)
                tool_name = parsed.get("name", "") or parsed.get("tool", "")
                tool_args = parsed.get("arguments", {}) or parsed.get("args", {})
                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except (json.JSONDecodeError, ValueError):
                        tool_args = {"raw": tool_args}
                if not tool_name:
                    logger.warning(f"解析 tool_call JSON 缺少 name 字段: {json_str[:100]}")
                    continue
                tool_calls.append({
                    "id": f"call_via_prompt_{idx}_{abs(hash(json_str)) % 1000000}",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(tool_args, ensure_ascii=False),
                    },
                })
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"解析 tool_call JSON 失败: {json_str[:100]}, error={e}")

        return tool_calls

    async def chat_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        config: Optional[Dict] = None,
        tool_choice: Optional[str] = "auto",
    ) -> Dict:
        """
        带函数调用的同步对话（支持自动降级）

        执行策略（两层防御）：
          第1层：优先使用原生 OpenAI tools 参数（如果模型支持）
          第2层：如果原生方式失败（500 + text/plain / /generate 报错 / pickling 错误），
                 自动降级为 prompt-based 模式——将工具描述注入 system prompt，
                 让 LLM 用结构化 JSON 标记 <function_call>...</function_call> 输出工具调用

        降级检测规则（任一触发即降级）：
          - HTTP 500 且响应 content-type 非 JSON（text/plain 等）
          - FastAPI detail 包含 "/generate" 或 "ContentTypeError" 或 "cannot be pickled"
          - 模型名属于已知不支持 function-calling 的列表（qwen3-*, xinference/qwen 等）

        :param messages: 完整的 OpenAI 消息列表
        :param tools: OpenAI 格式的工具定义列表
        :param config: 应用级 LLM 配置
        :param tool_choice: "auto" | "required" | "none"
        :return: {content, tool_calls, finish_reason, model}
        """
        # 如果没有工具，直接走普通 chat
        if not tools:
            content = await self._chat_plain(messages, config)
            return {
                "content": content,
                "tool_calls": [],
                "finish_reason": "stop",
                "model": (config or {}).get("model") or self.model,
            }

        # 第0步：预判是否需要降级（已知不支持原生 function-calling 的模型）
        # P0-2：名单环境变量化（LLM_FORCE_PROMPT_MODELS，默认空）——
        #   vLLM 引擎已验证支持原生 tools（结构化 tool_calls + finish_reason 均正常），
        #   旧的 qwen 系硬编码拦截已成拦截墙，放开后原生优先、prompt-based 降级保留为兜底
        model_name = (config or {}).get("model") or self.model
        _model_lower = (model_name or "").lower()
        _force_prompt_models = tuple(
            kw.strip().lower()
            for kw in settings.LLM_FORCE_PROMPT_MODELS.split(",")
            if kw.strip()
        )
        _should_try_native = not any(k in _model_lower for k in _force_prompt_models)

        # ---- 第1层：原生 function-calling ----
        if _should_try_native:
            native_result = await self._chat_with_tools_native(
                messages, tools, config, tool_choice, model_name
            )
            if native_result.get("fallback_triggered"):
                logger.warning(
                    f"原生 function-calling 失败，自动降级为 prompt-based 模式: "
                    f"{native_result.get('fallback_reason', '未知')}"
                )
                # 继续到第2层
            else:
                del native_result["fallback_triggered"]
                return native_result

        # ---- 第2层：prompt-based 降级 ----
        logger.info(f"使用 prompt-based 工具调用模式: model={model_name}, tools={len(tools)}个")
        return await self._chat_with_tools_via_prompt(messages, tools, config, model_name)

    async def _chat_plain(
        self,
        messages: List[Dict],
        config: Optional[Dict] = None,
    ) -> str:
        """内部工具：将 messages 作为整体发送给 chat（不做 prompt 改写）"""
        if config:
            base_url = config.get('base_url') or self.base_url
            api_key = config.get('api_key') or self.api_key
            model = config.get('model') or self.model
            max_tokens = config.get('max_tokens') or self.max_tokens
            temperature = config.get('temperature')
            if temperature is None:
                temperature = self.temperature
        else:
            base_url, api_key, model = self.base_url, self.api_key, self.model
            max_tokens = self.max_tokens
            temperature = self.temperature

        body = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        # P0-5：思考模式三态配置（应用级/系统级/模型默认）
        self._apply_thinking_config(body, model, config)

        # max_tokens 自动下调（复用 chat() 的逻辑）
        _model_lower = (model or '').lower()
        _model_context_length = 65536
        if any(k in _model_lower for k in ['qwen3', 'qwen2.5', 'qwen2']):
            _model_context_length = 40960
        elif any(k in _model_lower for k in ['glm4', 'glm-4', 'glm5', 'glm-5']):
            _model_context_length = 131072
        elif 'glm' in _model_lower:
            _model_context_length = 65536
        elif 'deepseek' in _model_lower or 'gpt' in _model_lower:
            _model_context_length = 131072
        total_chars = sum(len(m.get("content") or "") + 50 for m in messages)
        estimated_tokens = int(total_chars * 1.5)
        available = _model_context_length - estimated_tokens - 1000
        if max_tokens > max(1024, available):
            max_tokens = max(1024, available)
            body["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            raw_data = await response.aread()
            try:
                data = json.loads(raw_data)
            except (json.JSONDecodeError, ValueError):
                raise Exception(
                    f"响应JSON解析失败: HTTP {response.status_code}, "
                    f"content-type={response.headers.get('content-type')}, "
                    f"raw前500={(raw_data[:500] if isinstance(raw_data, (bytes, bytearray)) else str(raw_data)[:500]).decode('utf-8', errors='replace')}"
                )
            if isinstance(data, dict) and "detail" in data and "choices" not in data:
                detail = data["detail"]
                if isinstance(detail, list):
                    detail = "; ".join(str(x) for x in detail)
                raise Exception(f"大模型服务返回错误: {detail}")
            response.raise_for_status()
            if not data or "choices" not in data or not data["choices"]:
                raise Exception("大模型返回格式异常")
            content = data["choices"][0]["message"].get("content") or ""
            return content if isinstance(content, str) else str(content)

    async def _chat_with_tools_native(
        self,
        messages: List[Dict],
        tools: List[Dict],
        config: Optional[Dict],
        tool_choice: str,
        model_name: str,
    ) -> Dict:
        """
        原生 function-calling 调用（第1层）

        返回值中可能包含 fallback_triggered=True 表示需要降级
        """
        result_base: Dict[str, Any] = {
            "content": "",
            "tool_calls": [],
            "finish_reason": "",
            "model": model_name,
            "fallback_triggered": False,
            "fallback_reason": "",
        }

        try:
            if config:
                base_url = config.get('base_url') or self.base_url
                api_key = config.get('api_key') or self.api_key
                model = config.get('model') or self.model
                max_tokens = config.get('max_tokens') or self.max_tokens
                temperature = config.get('temperature')
                if temperature is None:
                    temperature = self.temperature
            else:
                base_url, api_key, model = self.base_url, self.api_key, self.model
                max_tokens = self.max_tokens
                temperature = self.temperature

            # max_tokens 自动下调
            _model_lower = (model or '').lower()
            _model_context_length = 65536
            if any(k in _model_lower for k in ['qwen3', 'qwen2.5', 'qwen2']):
                _model_context_length = 40960
            elif any(k in _model_lower for k in ['glm4', 'glm-4', 'glm5', 'glm-5']):
                _model_context_length = 131072
            elif 'glm' in _model_lower:
                _model_context_length = 65536
            elif 'deepseek' in _model_lower or 'gpt' in _model_lower:
                _model_context_length = 131072

            _messages_total_chars = sum(len(m.get('content') or '') + 50 for m in messages)
            _estimated_prompt_tokens = int(_messages_total_chars * 1.5) + len(tools) * 500
            _available_max_tokens = _model_context_length - _estimated_prompt_tokens - 1000
            if _available_max_tokens < 1024:
                _available_max_tokens = 1024
            if max_tokens > _available_max_tokens:
                logger.info(f"native chat_with_tools max_tokens 自动下调: {max_tokens} → {_available_max_tokens}")
                max_tokens = _available_max_tokens

            request_body = {
                "model": model,
                "messages": messages,
                "tools": tools,
                "tool_choice": tool_choice,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            # P0-5：思考模式三态配置（应用级/系统级/模型默认）
            self._apply_thinking_config(request_body, model, config)

            logger.info(
                f"原生 chat_with_tools 调用: model={model!r}, "
                f"messages={len(messages)}条, tools={len(tools)}个"
            )

            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                raw_bytes = await response.aread()
                content_type = response.headers.get('content-type', '')
                status_code = response.status_code

                # ---- 降级检测 ----
                # 规则1: HTTP 500 且 content-type 非 JSON
                if status_code >= 500 and 'json' not in content_type.lower():
                    raw_preview = raw_bytes[:500].decode('utf-8', errors='replace') if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)[:500]
                    logger.warning(
                        f"原生 function-calling 返回 {status_code} 且非JSON响应，触发降级: "
                        f"content-type={content_type}, raw前200={raw_preview[:200]}"
                    )
                    result_base["fallback_triggered"] = True
                    result_base["fallback_reason"] = f"HTTP {status_code} + non-JSON({content_type})"
                    return result_base

                # 尝试解析 JSON
                try:
                    data = json.loads(raw_bytes) if isinstance(raw_bytes, (bytes, bytearray)) else json.loads(raw_bytes)
                except (json.JSONDecodeError, ValueError):
                    # JSON 解析失败也降级
                    raw_preview = raw_bytes[:500].decode('utf-8', errors='replace') if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)[:500]
                    logger.warning(
                        f"原生 function-calling 响应JSON解析失败，触发降级: "
                        f"status={status_code}, content-type={content_type}, raw前200={raw_preview[:200]}"
                    )
                    result_base["fallback_triggered"] = True
                    result_base["fallback_reason"] = f"JSON decode fail, status={status_code}"
                    return result_base

                # 规则2: FastAPI detail 包含已知 function-calling 不支持的特征
                if isinstance(data, dict) and "detail" in data and "choices" not in data:
                    error_detail = str(data["detail"])
                    _fallback_keywords = (
                        "/generate", "ContentTypeError", "cannot be pickled",
                        "function_call", "unexpected mimetype",
                    )
                    if any(kw.lower() in error_detail.lower() for kw in _fallback_keywords):
                        logger.warning(
                            f"原生 function-calling FastAPI 错误包含 function-calling 不支持特征，触发降级: "
                            f"detail={error_detail[:300]}"
                        )
                        result_base["fallback_triggered"] = True
                        result_base["fallback_reason"] = f"FastAPI detail: {error_detail[:200]}"
                        return result_base

                # 非降级场景的其他错误：正常抛出
                if status_code >= 400:
                    if isinstance(data, dict) and "detail" in data:
                        detail = data["detail"]
                        if isinstance(detail, list):
                            detail = "; ".join(str(x) for x in detail)
                        raise Exception(f"大模型function-calling调用失败(HTTP {status_code}): {detail}")
                    raise Exception(f"大模型function-calling调用失败(HTTP {status_code})")

                response.raise_for_status()

                # 格式校验
                if (not data
                    or "choices" not in data
                    or not isinstance(data.get("choices"), list)
                    or len(data["choices"]) == 0
                    or not isinstance(data["choices"][0], dict)
                    or "message" not in data["choices"][0]):
                    raise Exception("大模型返回格式异常：缺少 choices/message 结构")

                message = data["choices"][0]["message"]
                content = message.get("content") or ""
                if not isinstance(content, str):
                    content = str(content) if content else ""

                tool_calls = message.get("tool_calls")
                if tool_calls is None and message.get("function_call"):
                    fc = message["function_call"]
                    tool_calls = [{
                        "id": fc.get("id", f"call_{abs(hash(json.dumps(fc))) % 1000000}"),
                        "type": "function",
                        "function": {
                            "name": fc.get("name", ""),
                            "arguments": fc.get("arguments", "{}"),
                        },
                    }]
                if not isinstance(tool_calls, list):
                    tool_calls = []

                finish_reason = data["choices"][0].get("finish_reason", "")

                logger.info(
                    f"原生 chat_with_tools 成功: content长度={len(content)}, "
                    f"tool_calls={len(tool_calls)}, finish_reason={finish_reason}"
                )

                result_base.update({
                    "content": content,
                    "tool_calls": tool_calls,
                    "finish_reason": finish_reason,
                    "model": model_name,
                })
                return result_base

        except Exception as e:
            # 其他异常也尝试降级一次（而不是直接抛出）
            logger.warning(
                f"原生 function-calling 异常，尝试降级: {type(e).__name__}: {str(e)[:200]}"
            )
            result_base["fallback_triggered"] = True
            result_base["fallback_reason"] = f"exception: {type(e).__name__}"
            return result_base

    async def _chat_with_tools_via_prompt(
        self,
        messages: List[Dict],
        tools: List[Dict],
        config: Optional[Dict],
        model_name: str,
    ) -> Dict:
        """
        Prompt-based 工具调用（第2层降级方案）

        策略：
        1. 在最后一个 system 消息末尾追加工具描述和输出格式指令
        2. 发送普通 chat 请求（不带 tools 参数）
        3. 从返回文本中解析 <function_call>...</function_call> 标记

        也会处理 messages 中已有的 tool 角色消息（前一轮工具调用结果），
        将其转为自然语言描述后放入 messages，确保上下文连贯。
        """
        # 构建降级用的工具描述 prompt
        tools_prompt = self._format_tools_for_prompt(tools)
        format_instructions = f"""

## 工具调用输出格式（重要）
当你需要调用某个工具时，不要直接输出结果，而是按以下格式输出工具调用请求：

{LLMService._TOOL_CALL_START}
{{"name": "工具名称", "arguments": {{"参数名": "参数值"}}}}
{LLMService._TOOL_CALL_END}

规则：
- 如果不需要调用工具，直接输出你的分析和回答即可（不要输出 tool_call 标记）
- 工具调用标记可以和分析文本同时出现
- arguments 必须是合法的 JSON 对象（字符串/数字/布尔/null/数组/对象）
- 一个回答中可以出现多个工具调用标记
"""

        # 将工具描述注入到 system message 末尾
        # 如果没有 system message，创建一个
        injected_messages = []
        system_injected = False
        for msg in messages:
            msg_copy = dict(msg)
            role = msg_copy.get("role")
            content = msg_copy.get("content", "") or ""

            if role == "system" and not system_injected:
                msg_copy["content"] = content + "\n\n" + tools_prompt + format_instructions
                system_injected = True
                injected_messages.append(msg_copy)
            elif role == "tool":
                # 将 tool 角色消息转为自然语言的 assistant→user 对
                # （prompt-based 模式下没有 tool 角色，LLM 需要看到工具返回结果作为上下文）
                # 方式：把 tool 结果作为 user 消息追加（带上工具名标注）
                tool_content = f"[上一轮工具调用结果] 工具返回: {content[:3000]}"
                injected_messages.append({"role": "user", "content": tool_content})
            else:
                injected_messages.append(msg_copy)

        if not system_injected:
            # 没有 system 消息，插入一条
            system_msg = {
                "role": "system",
                "content": tools_prompt + format_instructions,
            }
            # 找插入点：messages 开头（如果第一个不是 system）
            if injected_messages and injected_messages[0].get("role") == "user":
                injected_messages.insert(0, system_msg)
            else:
                injected_messages.insert(0, system_msg)

        # 发送普通 chat
        try:
            content = await self._chat_plain(injected_messages, config)
        except Exception as e:
            logger.error(f"prompt-based chat 调用失败: {type(e).__name__}: {e}")
            raise Exception(f"prompt-based 工具调用模式失败: {type(e).__name__}: {str(e)}")

        # 解析 tool_calls 标记
        tool_calls = self._parse_tool_calls_from_text(content)
        finish_reason = "tool_calls" if tool_calls else "stop"

        # 清理 content：把 tool_call 标记从正文中移除（让用户看到干净的分析）
        clean_content = content
        if tool_calls:
            import re as _re
            clean_content = _re.sub(
                re.escape(LLMService._TOOL_CALL_START) + r'.*?' + re.escape(LLMService._TOOL_CALL_END),
                '',
                content,
                flags=_re.DOTALL,
            ).strip()

        logger.info(
            f"prompt-based chat_with_tools 完成: content长度={len(clean_content)}, "
            f"解析到 tool_calls={len(tool_calls)}"
        )

        return {
            "content": clean_content,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "model": model_name,
        }

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

        历史传递方式（方案B）：通过 messages 数组的 history 传递，符合 OpenAI 标准。
        当 history 非空时自动注入多轮对话指令到 system_prompt，引导 LLM 参考历史并完成代词消歧。

        :param prompt: 用户输入的问题或指令
        :param system_prompt: 系统提示词，定义模型行为和角色
        :param history: 对话历史列表，格式为 [{"role": "user/assistant", "content": "文本"}]
        :param config: 应用级LLM配置（base_url, api_key, model, max_tokens, temperature），覆盖默认值
        :yield: 流式输出的文本片段，每次返回一个字符串
        :raises Exception: 调用失败时抛出，包含详细错误信息
        """
        try:
            # 1. 构建消息列表（统一使用 _build_messages 公共方法）
            # 方案B：历史放入 messages 数组的 history 中（OpenAI 标准方式）
            # 多轮对话指令（参考历史、代词消歧）自动注入到 system_prompt 末尾
            messages = self._build_messages(prompt, system_prompt, history)

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
            # P2修复：max_tokens 自动下调（与 chat() 方法保持一致）
            _model_lower = (model or '').lower()
            _model_context_length = 65536
            if any(k in _model_lower for k in ['qwen3', 'qwen2.5', 'qwen2']):
                _model_context_length = 40960
            elif any(k in _model_lower for k in ['glm4', 'glm-4', 'glm5', 'glm-5']):
                _model_context_length = 131072
            elif 'glm' in _model_lower:
                _model_context_length = 65536
            elif any(k in _model_lower for k in ['gemma4', 'gemma-4']):
                _model_context_length = 131072
            elif 'gemma' in _model_lower:
                _model_context_length = 65536
            elif 'deepseek' in _model_lower or 'gpt' in _model_lower:
                _model_context_length = 131072

            _messages_total_chars = 0
            for _msg in messages:
                _messages_total_chars += len(_msg.get('content') or '')
                _messages_total_chars += 20
            _estimated_prompt_tokens = int(_messages_total_chars * 1.5)
            _available_max_tokens = _model_context_length - _estimated_prompt_tokens - 1000
            if _available_max_tokens < 1024:
                _available_max_tokens = 1024
            if max_tokens > _available_max_tokens:
                logger.info(
                    f"chat_stream max_tokens自动下调: 原值={max_tokens}, "
                    f"下调后={_available_max_tokens} "
                    f"(context={_model_context_length}, "
                    f"估算prompt_token={_estimated_prompt_tokens})"
                )
                max_tokens = _available_max_tokens

            # 对qwen3系列模型禁用thinking模式，避免Xinference解析reasoning_content时触发KeyError 'text'
            request_body = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True,
            }
            # P0-5：思考模式三态配置（应用级/系统级/模型默认）
            self._apply_thinking_config(request_body, model, config)

            async with httpx.AsyncClient(timeout=300.0) as client:
                # P2修复：提升日志级别到info并补全请求关键信息（调试模型是否正确使用gemma4:e4b）
                logger.info(
                    f"发起LLM chat_stream调用: model={model!r}, base_url={base_url}, "
                    f"max_tokens={max_tokens}, temperature={temperature}, "
                    f"prompt长度={len(prompt)}, 历史条数={len(history) if history else 0}"
                )
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

    async def rewrite_query(
        self,
        question: str,
        history: Optional[List[Dict]] = None,
    ) -> str:
        """
        查询改写（Query Rewriting —— 多轮对话核心能力）

        基于对话历史改写当前问题，完成两项任务：
          1. 指代消解：将"它"、"这个"、"那个"等代词替换为历史中提到的具体实体
          2. 省略补全：将"那下个月呢"、"再来一个"等省略表达补全为完整问题

        改写后的问题用于意图分类、RAG 检索、NL2SQL，能显著提升多轮对话效果。
        原始问题保留用于数据库存储和前端展示（用户看到的仍是原始输入）。

        设计原则：
          - 只做指代消解和省略补全，不改变问题的核心语义
          - 如果问题本身完整清晰，直接返回原问题
          - 改写失败时降级返回原问题，不影响主流程
          - 不依赖外部工具，仅用 LLM 完成

        典型场景：
          - 上一轮"高炉炼铁的原理是什么" + 当前"那它的应用呢" → "高炉炼铁的应用"
          - 上一轮"展示2023年8月每日吹炼次数" + 当前"那9月呢" → "展示2023年9月每日吹炼次数"
          - 上一轮"我叫小明" + 当前"我叫什么" → "我叫什么"（无需改写，直接返回）

        :param question: 用户当前问题（原始输入）
        :param history: 对话历史 [{"role": "user/assistant", "content": "文本"}]
        :return: 改写后的问题；无历史或改写失败时返回原问题
        """
        # 无历史时无需改写，直接返回原问题
        if not history or len(history) == 0:
            return question

        try:
            # 构建历史摘要（仅取最近3轮，避免prompt过长）
            recent_history = history[-6:] if len(history) > 6 else history
            # P2修复：放宽历史摘要截断，区分角色保留关键上下文
            # - user 消息：截断到 500 字符（用户问题通常较短，需完整保留查询主题）
            # - assistant 消息：截断到 1200 字符（保留 SQL 和分析主题，避免丢失表名/字段/指标）
            #   原值 300 字符会导致长回复被截断后丢失关键上下文，引发延续性提问改写失败
            history_lines = []
            for m in recent_history:
                content = m.get('content', '')
                if not content:
                    continue
                role_label = '用户' if m.get('role') == 'user' else '助手'
                if m.get('role') == 'assistant':
                    if len(content) > 1200:
                        content = content[:1200] + "...(截断)"
                else:
                    if len(content) > 500:
                        content = content[:500] + "...(截断)"
                history_lines.append(f"{role_label}: {content}")
            history_text = "\n".join(history_lines)

            if not history_text.strip():
                return question

            # 改写指令：只做指代消解和省略补全，不改变核心语义
            rewrite_prompt = f"""请基于对话历史改写当前问题，使其成为完整、独立的问题。

## 对话历史
{history_text}

## 当前问题
{question}

## 改写要求（严格遵守）
1. **指代消解**：将"它"、"这个"、"那个"、"上面提到的"等代词替换为历史中的具体实体
2. **省略补全**：将"那XX呢"、"再来一个"、"继续"等省略表达补全为完整问题
3. **保留查询主题（重要）**：若当前问题为延续性提问（如"那X月呢"、"换成XX"），
   **必须从上一轮用户问题或助手回复中提取查询主题**（表名、字段、聚合方式、
   统计维度等），完整保留到改写后的问题中
   - 示例：历史助手回复SQL含 `SELECT TYPE_CODE, AVG(SCORE) FROM hgbf1_condition_result`
     + 当前"那八月呢" → 改写为"展示2024年8月炉况报告结果中各评分类型的平均打分值"
     （而非简化为"展示8月数据"）
4. **时间词改写规则**：若当前问题只改时间（如"那8月呢"、"换成9月"），
   只替换时间部分，其他语义（表名、字段、聚合）保持与上一轮一致
5. **年份继承规则（关键！必须严格遵守）**：若当前问题仅提到**月份/季节/日期**，
   **没有明确写年份**（如"那8月呢"、"7月的数据"、"上个季度"），
   **必须从对话历史中**（优先看"最近一条用户问题"里写的年份，若没有看"最近一条
   助手回复"中SQL或叙述提到的年份）**继承年份**，**严禁使用当前系统日期的年份**
   作为默认值！只有历史中完全找不到任何年份信息时，才允许用当前系统年份。
   - 错误示例：上一轮用户问"2024年9月..." + 当前"那8月呢" → 错误改成"2026年8月..."
   - 正确示例：上一轮用户问"2024年9月..." + 当前"那8月呢" → 继承"2024"→"2024年8月..."
6. **时间冲突保护（必须严格遵守）**：若**当前问题本身已包含明确的时间**（如
   "2024年8月"、"2023年9月15日"、"本月"、"上周"等），**严禁从对话历史中
   替换或推断其他时间**，必须保留当前问题中用户明确指定的时间
   - 错误示例：历史含"2024年9月" + 当前"展示2024年8月炉况报告..." → 错误改写为"2024年9月..."
   - 正确示例：历史含"2024年9月" + 当前"展示2024年8月炉况报告..." → 保留"2024年8月"原样
7. **保持核心语义**：不要增加、修改或删除原问题的意图
8. 如果当前问题本身完整清晰，直接返回原问题
9. 只返回改写后的问题，不要输出任何解释或额外内容

## 示例
- 历史"高炉炼铁的原理" + 当前"那它的应用呢" → "高炉炼铁的应用"
- 历史"展示2023年8月每日吹炼次数" + 当前"那9月呢" → "展示2023年9月每日吹炼次数"
- 历史"展示2024年8月炉况报告结果中各评分类型的平均打分值" + 当前"那9月呢"
  → "展示2024年9月炉况报告结果中各评分类型的平均打分值"
- 历史"展示2024年9月炉况报告结果中各评分类型的平均打分值" + 当前"那8月呢"
  → "展示2024年8月炉况报告结果中各评分类型的平均打分值"（继承历史的2024年份，不使用系统年份2026）
- 历史"展示2024年9月炉况报告..." + 当前"展示2024年8月炉况报告结果中各评分类型的平均打分值"
  → "展示2024年8月炉况报告结果中各评分类型的平均打分值"（保留当前问题中的8月，不从历史替换）
- 历史"我叫小明" + 当前"我叫什么" → "我叫什么"（无需改写）
- 当前"你好" → "你好"（无需改写）

请直接输出改写后的问题："""

            rewritten = await self.chat(
                prompt=rewrite_prompt,
                system_prompt=None,
                history=None,  # 改写任务不需要再次嵌入历史，prompt中已包含
            )

            # 清理结果
            rewritten = (rewritten or "").strip()
            # 移除可能的引号包裹
            if rewritten.startswith('"') and rewritten.endswith('"'):
                rewritten = rewritten[1:-1]
            elif rewritten.startswith("'") and rewritten.endswith("'"):
                rewritten = rewritten[1:-1]

            # 防御：如果改写结果为空或异常长（>5倍原问题），降级返回原问题
            if not rewritten or len(rewritten) > len(question) * 5:
                logger.warning(
                    f"查询改写结果异常: 原问题={question[:50]}, 改写={rewritten[:50]}, 使用原问题"
                )
                return question

            # P2修复：代码级时间冲突保护
            # 防御 LLM 不遵守 prompt 中"时间冲突保护"规则，从历史中替换了当前问题的明确时间
            # 如果原问题含"YYYY年MM月"等明确时间，且改写后含不同时间，强制用原时间覆盖
            orig_time_match = re.search(r'(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?', question)
            if orig_time_match:
                orig_time_str = orig_time_match.group(0)
                rewrite_time_match = re.search(r'(\d{4})年(\d{1,2})月(?:(\d{1,2})日)?', rewritten)
                if rewrite_time_match and rewrite_time_match.group(0) != orig_time_str:
                    logger.warning(
                        f"时间冲突保护触发: 原问题时间={orig_time_str}, "
                        f"改写后时间={rewrite_time_match.group(0)}, 强制用原时间覆盖"
                    )
                    rewritten = rewritten.replace(
                        rewrite_time_match.group(0),
                        orig_time_str
                    )
                    logger.info(f"时间冲突保护后改写: {rewritten[:80]}...")

            # P2修复：代码级"年份继承"保护（防御 LLM 用当前系统日期当年份默认值）
            # 触发条件：
            #   a) 原问题只有月份/日期，没有年份（如"那8月呢"、"7月数据"）；
            #   b) 改写后的问题里出现了"年份+月份"，且年份 = 当前系统年份；
            #   c) 对话历史（倒序优先找user消息，没有再找assistant）中最近一条能提取到明确4位数年份
            #       且 != 当前系统年份
            # → 强制把改写结果的系统年份替换为"历史最近年份"
            import datetime as _dt
            current_year = _dt.date.today().year
            orig_has_year = bool(re.search(r'\d{4}', question))
            rewrite_year_match = re.search(r'(\d{4})年(\d{1,2})月', rewritten)
            if (not orig_has_year) and rewrite_year_match and int(rewrite_year_match.group(1)) == current_year:
                # 从 history 倒序找最近一条含明确4位数年份的消息（优先user角色）
                inherited_year: Optional[int] = None
                user_year = None
                assist_year = None
                for m in reversed(history or []):
                    c = m.get('content', '') or ''
                    y_match = re.search(r'(19|20)\d{2}', c)
                    if not y_match:
                        continue
                    y = int(y_match.group(0))
                    if 1990 <= y <= current_year + 5:  # 合理年份范围
                        role = m.get('role', '')
                        if role == 'user' and user_year is None:
                            user_year = y
                            break  # 优先user角色，找到就停
                        elif role == 'assistant' and assist_year is None:
                            assist_year = y
                            # assistant不急着停，先看user有没有，没有就用assistant的
                inherited_year = user_year or assist_year
                if inherited_year and inherited_year != current_year:
                    rewrite_year_str = rewrite_year_match.group(0)
                    new_year_str = re.sub(r'^\d{4}', str(inherited_year), rewrite_year_str, count=1)
                    logger.warning(
                        f"年份继承保护触发: 原问题无年份, LLM误使用当前系统年{current_year} "
                        f"({rewrite_year_str!r}), 从历史最近内容继承为{inherited_year} "
                        f"(→ {new_year_str!r})"
                    )
                    rewritten = rewritten.replace(rewrite_year_str, new_year_str, 1)
                    logger.info(f"年份继承保护后改写: {rewritten[:100]}...")

            if rewritten != question:
                logger.info(f"查询改写完成: 原问题={question[:50]}..., 改写={rewritten[:50]}...")
            return rewritten

        except Exception as e:
            logger.warning(f"查询改写失败，使用原问题: {type(e).__name__}: {e}")
            return question

    async def classify_intent(
        self,
        question: str,
        system_prompt: Optional[str] = None,
        mcp_tools: Optional[List[Dict[str, str]]] = None,
        skill_tools: Optional[List[Dict[str, str]]] = None,
        history: Optional[List[Dict]] = None,
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

        多轮对话支持（P0改造）：
          history 参数会被传给 llm_service.chat，让 LLM 分类时能看到历史。
          这样能识别延续性意图，例如：
            - 上一轮"展示2023年8月每日吹炼次数" + 当前"那9月呢" → data
            - 上一轮"高炉炼铁的原理" + 当前"那它的应用呢" → knowledge
            - 上一轮"我叫小明" + 当前"我叫什么" → chat

        五大意图通道（M4改造：hybrid混合意图已下线）：
          chat      → 闲聊对话（问候、自我介绍、感谢）→ 直接LLM回答
          knowledge → 知识问答（工艺原理、技术规范）→ RAG检索
          data      → 数据查询（产量、合格率、报表）→ NL2SQL
          mcp       → MCP工具调用（地图、天气等外部服务）→ MCP协议
          skill     → Skill工具调用（本地技能脚本）→ Skill执行引擎
          知识+数据复合问题统一归类为knowledge（数据部分由用户追问补全）。

        :param question: 用户输入的问题
        :param system_prompt: 自定义分类提示词，为空时使用内置默认提示词
        :param mcp_tools: 可用MCP工具列表 [{"name": ..., "description": ...}]，
                          参考工具管理中已配置的MCP名称与描述
        :param skill_tools: 可用Skill工具列表 [{"name": ..., "description": ..., "file_name": ...}]，
                            参考工具管理中已配置的Skills名称、描述与文件
        :param history: 对话历史（用于上下文感知，识别延续性意图）
        :return: 分类结果（knowledge/data/mcp/skill/chat），异常时默认返回 knowledge
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

        # 默认意图分类提示词（五种意图类型，M4改造：hybrid已下线）
        default_prompt = f"""你是一个智能意图分类助手，负责将用户问题归类为以下五种类型之一。

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
**当用户问题与上述Skill工具列表中的某个Skill名称匹配时**，归类为skill：
- 用户问题**完整包含**上述Skill工具列表中某个Skill的名称（如"高炉炉况诊断"、"产品营销文案"等）
- 用户问题是某个Skill名称的简写（如"产品营销文案"是"产品营销文案创作"的简写）
- 用户明确表达执行技能意图："执行xxx技能"、"使用xxx技能"、"调用xxx技能"、"运行xxx"
- **严格约束（必须遵守）**：
  - 只有用户问题与Skill工具列表中的**某个具体Skill名称**匹配（完整包含或简写）时才归类为skill
  - 出现"炉况"、"诊断"、"高炉"等单独词组，但**未构成完整Skill名称**时，一律归类为knowledge
- **重要**：普通的炉况相关问题（如"风压波动怎么回事"、"铁水硅高了"、"炉况不顺"等）
  **不归类为skill**，应归类为knowledge（知识问答），因为这些是知识咨询而非技能调用
- **关键**：请仔细比对用户问题与上方"Skill工具"列表中的每个Skill名称，
  只要用户问题与某个Skill名称匹配（完整包含或简写），就归类为skill

### 4. data（数据查询）
当用户需要查询数据库中的业务数据时，归类为data：
- 生产数据：产量、合格率、能耗、设备状态、工艺参数
- 统计分析：报表、趋势、对比、排名、汇总
- 关键词特征：展示、查询、统计、多少、次数、数量、产量、合格率、能耗、报表、图表、趋势

### 5. knowledge（知识问答）
当用户问题涉及工艺知识、技术规范等，需要从知识库检索信息时，归类为knowledge：
- 工艺知识：炼铁原理、炼钢工艺、轧钢流程
- 技术规范：操作规程、安全规范、技术标准
- 概念解释：什么是、如何理解、解释一下
- **复合问题处理**：一个问题同时包含知识问答和数据查询时，归类为knowledge
  （优先解答知识部分，数据部分由用户后续追问补全）
- **注意**：简单问候语、自我介绍等不属于knowledge，应归类为chat

## 判断要点（重要）
1. 优先判断chat：简单问候、自我介绍、感谢等属于chat，直接用LLM回答
2. 优先判断mcp/skill：如果问题涉及外部工具调用或技能执行，优先归类为mcp或skill
3. **工具语义匹配**：仔细比对用户问题与可用工具列表中的名称和描述，
   如果问题语义与某个工具的描述场景匹配，应归类为对应的mcp或skill
4. 数据查询中的"查询"指的是查询内部数据库数据，不是外部服务
5. 知识+数据复合问题统一归类为knowledge，不再单独拆分处理

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
- "高炉炉况诊断" → skill（完整包含Skill名称）
- "执行高炉炉况诊断技能" → skill
- "产品营销文案" → skill（用户问题等于或简写自Skill名称，如Skill名为"产品营销文案创作"）
- "产品营销文案创作" → skill（完整包含Skill名称）
- "诊断炉况"、"炉况分析"、"分析高炉数据" → knowledge
- "炉子是不是不顺"、"风压波动怎么回事" → knowledge
- "铁水硅高了"、"要不要调风"、"料速慢了" → knowledge
- "当前压差不稳，炉料质量不好，应该如何调整以减少炉况波动？" → knowledge
- "烧结矿粒度变小，如何调整布料矩阵和炉料结构？" → knowledge
- "为了稳定炉温和炉况，应该如何调整？" → knowledge
- "展示2023年8月的每日吹炼次数，并且解释什么是高炉炼铁" → knowledge（复合问题统一归类）
- "当前压差不稳应该如何调整？同时展示近期产量数据" → knowledge（复合问题统一归类）

请直接返回分类结果（knowledge/data/mcp/skill/chat），不要返回任何解释或额外内容。"""

        # 调用 LLM 进行分类（使用同步 chat 方法，因为分类不需要流式输出）
        # P0改造：传入 history，让 LLM 分类时能看到对话历史，识别延续性意图
        # 例如：上一轮"展示2023年8月数据" + 当前"那9月呢" → 正确分类为 data
        result = await self.chat(
            prompt=question,
            system_prompt=system_prompt or default_prompt,
            history=history,
        )

        # 清理并验证分类结果（防御性编程）
        # LLM 可能返回带额外文字的结果（如 "我认为应该归类为 knowledge"），需提取关键词
        intent = result.strip().lower()
        valid_intents = ["knowledge", "data", "mcp", "skill", "chat"]
        if intent not in valid_intents:
            # 尝试从结果中提取有效意图词（LLM 可能输出解释性文字）
            for valid_intent in valid_intents:
                if valid_intent in intent:
                    intent = valid_intent
                    break
            else:
                # 兜底策略（M4改造）：无法识别时默认 knowledge（走知识问答通道）
                # 历史版本默认hybrid，该通道已下线
                logger.warning(f"意图分类结果异常: {result}，使用默认值 knowledge")
                intent = "knowledge"

        logger.info(f"意图分类完成: 问题={question[:50]}..., 结果={intent}")
        return intent


# 服务实例
llm_service = LLMService()
logger.info("LLM服务实例已创建，等待请求")