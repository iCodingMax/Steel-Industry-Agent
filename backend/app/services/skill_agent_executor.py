"""
Skill Agent 执行器（LangGraph ReAct Agent）

基于 LangGraph StateGraph 构建的 Agent 执行引擎，
支持 Skill 通过 SKILL.md frontmatter 声明 MCP 工具调用能力。

=============================================================================
架构设计：
=============================================================================

LangGraph StateGraph 拓扑：

    skill_runtime (初始化)
        │
        ▼
    agent_think (LLM 决策) ──有 tool_calls──▶ tool_exec (工具执行)
        │ 无 tool_calls                       │
        ▼                                     │
    agent_finalize ◀──────────────────────────┘
        │
        ▼
       END

State 结构（TypedDict）：
    messages          List[Dict]    # OpenAI 标准消息列表
    skill_context     str          # SKILL.md + 参考文档 + 数据的上下文
    iteration         int          # 当前迭代次数
    max_iterations    int          # 最大迭代次数
    tools             List[Dict]    # OpenAI function-calling 工具定义
    tool_registry     Dict[str,Dict]  # 工具名 → 完整 tool_info 的映射
    trace             List[Dict]    # 执行轨迹（用于前端展示调试）
    final_answer      str          # 最终聚合后的答案
    done              bool         # 是否结束

工具注册逻辑：
    1. 通过 ToolRegistry.load_mcp_tools_cached 加载应用配置的 MCP 工具
       （带 TTL 类级缓存，与主对话工具注册共享同一份缓存）
    2. 根据 SKILL.md frontmatter 声明的 mcp_tools 名称匹配筛选
    3. 匹配成功的工具 → 转成 OpenAI tools 格式
    4. 匹配失败但 frontmatter 有声明 → 记录警告（工具名可能不一致）
    5. frontmatter 没声明 → 不暴露任何 MCP 工具给 LLM（安全默认）

MCP 工具执行：
    在 tool_exec 节点中遍历 LLM 返回的 tool_calls，
    从 tool_registry 查 tool_info，调用 MCPClientService.call_tool()，
    将结果格式化为 role="tool" 的消息追加到 messages。
=============================================================================
"""
import json
import asyncio
from typing import List, Dict, Any, Optional, TypedDict
from loguru import logger

# LangGraph 可选导入（Agent 模式依赖）
try:
    from langgraph.graph import StateGraph, END
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    logger.warning("langgraph 未安装，Skill Agent 模式将不可用。请执行: pip install langgraph")


# ============================================================
# State Schema（LangGraph TypedDict）
# ============================================================

class AgentState(TypedDict, total=False):
    """
    LangGraph Agent 执行状态

    total=False 表示所有字段可选（LangGraph StateGraph 初始化时可以只传部分字段）
    """
    messages: List[Dict[str, Any]]              # OpenAI 标准消息列表
    skill_context: str                          # SKILL.md + 参考文档清单 + 数据的上下文
    references_full: Dict[str, str]             # 参考文档全文（文件名 → 内容，read_reference 按需读取）
    iteration: int                              # 当前迭代次数
    max_iterations: int                        # 最大迭代次数
    tools: List[Dict[str, Any]]                 # OpenAI function-calling 工具定义
    tool_registry: Dict[str, Dict[str, Any]]   # 工具名 → 完整 tool_info 的映射
    trace: List[Dict[str, Any]]                 # 执行轨迹
    final_answer: str                           # 最终答案
    done: bool                                  # 是否结束
    mcp_connection_failure: bool                # MCP 连接失败硬停止标志（execute 据此返回 success=False）


# 内置参考文档读取工具名（不走 MCP，从 state.references_full 读取）
TOOL_READ_REFERENCE = "read_reference"

# MCP 连接类失败的特征文本（出现即判定 MCP Server 不可达，
# Agent 硬停止并直接返回失败说明，避免 LLM 在无数据时编造报告）
_MCP_CONNECTION_FAILURE_PATTERNS = (
    "无法连接到MCP Server",
    "MCP会话初始化失败",
    "ConnectError",
    "Connection refused",
    "connect timeout",
    "请求超时",
)

# read_reference 工具的 OpenAI function-calling 定义（L3 渐进披露：按需读取参考文档全文）
_READ_REFERENCE_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": TOOL_READ_REFERENCE,
        "description": (
            "读取本 Skill 参考文档的完整内容。当需要查阅参考文档中的规则、标准、"
            "阈值等细节时调用本工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "参考文档文件名（不含扩展名），从参考文档清单中选择",
                },
            },
            "required": ["file_name"],
        },
    },
}


# ============================================================
# SkillAgentExecutor 主类
# ============================================================

class SkillAgentExecutor:
    """
    Skill Agent 执行器

    使用 LangGraph StateGraph 实现 ReAct 循环，
    让 Skill 能够通过 function-calling 调用 MCP 工具。

    使用方式（由 execute_skill 内部调用）：
        executor = SkillAgentExecutor()
        result = await executor.execute(...)
    """

    # ---------- 上下文预算类常量 ----------
    HISTORY_MAX_MESSAGES = 4       # 透传主对话历史的最大条数
    HISTORY_MAX_CHARS = 4000       # 透传历史的总字符上限（超过从最旧开始丢弃）
    REFERENCE_MAX_CHARS = 16000     # read_reference 单篇文档最大返回字符数

    # Skill Agent 专用系统指令（注入到 system message）
    _AGENT_SYSTEM_PROMPT_TEMPLATE = """# Skill Agent 执行指令

你是一个 Skill Agent，正在执行 Skill: **{skill_name}**

## 当前时间
{current_time}
（构造查询参数（如时间范围）时必须以此为准，禁止凭空编造时间。若需"最近/当前"类时间，从当前时间往回推算）

## Skill 定义（必须严格遵守其中的流程、默认值和输出格式）
{skill_context}

## 可用工具
{tools_desc}

## 重要规则（必须遵守）
1. 如果需要外部数据（如实时传感器数据、天气数据等），必须先调用工具获取，再进行分析
2. 工具调用后，请整合工具返回的数据，按照 SKILL.md 定义的格式输出最终结果
3. **数据完整性强制要求**：诊断/分析结论必须完全基于工具返回的真实数据。若数据获取失败
   或未获取到有效数据，必须明确告知用户"数据不可用，无法完成诊断"，说明失败原因，
   绝对禁止基于想象、猜测或"典型值"编造数据、指标数值或诊断结论
4. 直接输出最终结果，不要输出无关的思考过程
5. 如果 SKILL.md 中定义了输出格式（章节结构），必须完整遵守
6. 不要在回答中输出 JSON 格式的工具调用参数，那是内部实现细节
7. **工具返回数据处理**：工具返回的 JSON 中若 "data" 为空对象 {{}}、空数组 [] 或 value 为 null，
   表示该查询未获取到有效数据。此时：
   - 不要把工具返回的原始 JSON 直接作为答案输出
   - 可以尝试调整查询参数（如更换时间范围）再调用一次工具
   - 若仍无数据，必须在回答中明确告知用户"未查询到有效数据"，说明尝试过的查询条件，
     并给出排查建议（如数据源是否可用、时间范围是否正确），而不是编造数据或输出空结果

## 用户问题
{question}
"""

    async def execute(
        self,
        skill_name: str,
        skill_description: str,
        skill_md_body: str,
        references: List[Dict[str, str]],
        question: str,
        history: Optional[List[Dict[str, str]]] = None,
        llm_config: Optional[Dict[str, Any]] = None,
        db=None,
        tool_config_ids: Optional[List[int]] = None,
        declared_mcp_tools: Optional[List[Dict[str, str]]] = None,
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        """
        执行 Skill Agent

        :param skill_name: Skill 名称
        :param skill_description: Skill 描述
        :param skill_md_body: SKILL.md 正文（已去除 frontmatter）
        :param references: 参考文档列表 [{name, content}]（references/ 与 assets/ 下的 .md）
        :param question: 用户问题
        :param history: 对话历史
        :param llm_config: LLM 配置
        :param db: 数据库会话（用于加载 MCP 工具）
        :param tool_config_ids: 应用配置的工具 ID 列表
        :param declared_mcp_tools: frontmatter 声明的 MCP 工具 [{name, purpose}]
        :param max_iterations: Agent 最大迭代次数
        :return: {answer, success, trace}
        """
        # 0. 前置检查
        if not _LANGGRAPH_AVAILABLE:
            return {
                "answer": "Skill Agent 模式不可用：langgraph 未安装。请先 `pip install langgraph langchain-core`。",
                "success": False,
                "trace": [],
            }

        if db is None:
            return {
                "answer": "Skill Agent 模式需要数据库会话来加载 MCP 工具。",
                "success": False,
                "trace": [],
            }

        logger.info(
            f"SkillAgentExecutor 开始执行: skill={skill_name}, "
            f"declared_tools={declared_mcp_tools}, max_iter={max_iterations}"
        )

        # 1. 加载并筛选 MCP 工具
        tools, tool_registry = await self._load_and_filter_mcp_tools(
            db=db,
            tool_config_ids=tool_config_ids or [],
            declared_mcp_tools=declared_mcp_tools or [],
        )

        # 1.2 注入内置 read_reference 工具（L3 渐进披露：有参考文档才注入）
        #     该工具不走 MCP，由 _node_tool_exec 直接从 references_full 读取
        references_full: Dict[str, str] = {
            ref.get("name", ""): ref.get("content", "") for ref in (references or [])
        }
        references_full = {k: v for k, v in references_full.items() if k and v}
        if references_full:
            tools = tools + [_READ_REFERENCE_TOOL_SCHEMA]
            logger.info(
                f"[Skill Agent] 注入内置工具 read_reference: 参考文档={list(references_full.keys())}"
            )

        # 1.5 安全检查：SKILL 声明了 mcp_tools 但实际匹配到 0 个 → 直接返回错误
        # 避免无工具时 LLM 编造数据生成虚假诊断报告
        if declared_mcp_tools and len(tools) == 0:
            declared_names = [t["name"] for t in declared_mcp_tools]
            error_msg = (
                f"Skill「{skill_name}」声明了 MCP 工具 {declared_names}，"
                f"但所有 MCP Server 均不可用或未匹配到工具，无法获取数据执行诊断。\n\n"
                f"请检查以下内容：\n"
                f"1. MCP Server 是否已启动（如高炉炉况数据 MCP 是否在运行）\n"
                f"2. MCP Server URL 是否正确、网络是否可达\n"
                f"3. SKILL.md 中声明的 mcp_tools 名称是否与 MCP Server 实际暴露的工具名一致"
            )
            logger.warning(
                f"[Skill Agent] MCP工具不可用: skill={skill_name}, "
                f"declared={declared_names}, matched=0, 直接返回错误"
            )
            return {
                "answer": error_msg,
                "success": False,
                "trace": [],
            }

        # 2. 组装 skill_context（SKILL.md 正文 + 参考文档清单）
        skill_context = self._build_skill_context(
            skill_name=skill_name,
            skill_description=skill_description,
            skill_md_body=skill_md_body,
            references=references,
        )

        # 3. 构建 Agent 图
        graph = self._build_graph()

        # 4. 构建初始 state
        initial_state: AgentState = {
            "messages": [],
            "skill_context": skill_context,
            "references_full": references_full,
            "iteration": 0,
            "max_iterations": max(3, min(max_iterations, 30)),
            "tools": tools,
            "tool_registry": tool_registry,
            "trace": [],
            "final_answer": "",
            "done": False,
        }

        # 5. 添加 system prompt 和 user question 到 messages
        # 注意：system prompt 动态注入当前时间、skill_context（SKILL.md 正文+参考文档清单）、可用工具描述
        from datetime import datetime
        tools_desc = self._format_tools_desc(tools)
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = self._AGENT_SYSTEM_PROMPT_TEMPLATE.format(
            skill_name=skill_name,
            current_time=current_time,
            skill_context=skill_context,
            tools_desc=tools_desc if tools_desc else "（当前 Skill 未声明可用的 MCP 工具）",
            question=question,
        )
        logger.info(
            f"[Agent prompt] system prompt 构建完成: 总长度={len(system_prompt)}, "
            f"skill_context长度={len(skill_context)}, 当前时间={current_time}"
        )
        initial_state["messages"] = [{"role": "system", "content": system_prompt}]

        # 5.2 主对话历史透传（修复子智能体上下文断裂）
        #     注入最近 4 条历史（user/assistant），总量超限截断，让 Skill 感知用户此前
        #     提过的约束条件（如"只看2号高炉"）
        initial_state["messages"].extend(self._build_history_messages(history or []))

        initial_state["messages"].append({"role": "user", "content": question})

        # 6. 运行 LangGraph
        try:
            final_state = await graph.ainvoke(initial_state)
            mcp_failure = bool(final_state.get("mcp_connection_failure", False))
            logger.info(
                f"SkillAgentExecutor 执行完成: skill={skill_name}, "
                f"final_answer长度={len(final_state.get('final_answer', ''))}, "
                f"实际迭代次数={len(final_state.get('trace', []))}, "
                f"mcp连接失败={mcp_failure}"
            )
            return {
                "answer": final_state.get("final_answer", ""),
                # MCP 连接失败硬停止时返回失败，上层 ToolRegistry/MasterAgent
                # 据此走失败分支，不再把失败说明当作 Skill 成功输出转述
                "success": not mcp_failure,
                "trace": final_state.get("trace", []),
            }
        except Exception as e:
            logger.error(
                f"SkillAgentExecutor LangGraph 执行异常: {type(e).__name__}: {e}",
                exc_info=True
            )
            return {
                "answer": f"Skill Agent 执行过程中出现错误：{type(e).__name__}: {str(e)}",
                "success": False,
                "trace": [],
            }

    # ========================================================
    # LangGraph 节点实现
    # ========================================================

    async def _node_agent_think(self, state: AgentState) -> AgentState:
        """
        Agent 思考节点 — 调用 LLM 决定下一步行为

        LLM 可能返回：
        - 纯文本 content（表示任务完成，不需要工具）
        - tool_calls（表示需要调用工具）
        - 两者都有（少见，按 tool_calls 优先处理）
        """
        from app.services.llm_service import llm_service

        iteration = state["iteration"] + 1
        logger.info(f"[Agent think] 第 {iteration} 次迭代")

        state["iteration"] = iteration

        # 记录 trace
        state["trace"].append({
            "step": "agent_think",
            "iteration": iteration,
            "tool_count": len(state.get("tools", [])),
        })

        # 调用带工具的 LLM
        llm_config = self._get_llm_config(state)
        result = await llm_service.chat_with_tools(
            messages=state["messages"],
            tools=state.get("tools", []),
            config=llm_config,
            tool_choice="auto",
        )

        content = result.get("content", "") or ""
        tool_calls = result.get("tool_calls", []) or []
        finish_reason = result.get("finish_reason", "")

        logger.info(
            f"[Agent think] LLM 返回: content长度={len(content)}, "
            f"tool_calls={len(tool_calls)}, finish_reason={finish_reason}"
        )

        # 把 assistant 回复（含 tool_calls）追加到 messages
        assistant_msg: Dict[str, Any] = {"role": "assistant", "content": content}
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        state["messages"].append(assistant_msg)

        # 记录 LLM 决策到 trace
        state["trace"].append({
            "step": "llm_decision",
            "iteration": iteration,
            "content_preview": content[:200] if content else "(空)",
            "tool_calls": [
                {"id": tc.get("id", ""), "name": tc.get("function", {}).get("name", ""),
                 "arguments": tc.get("function", {}).get("arguments", "")[:100]}
                for tc in tool_calls
            ],
            "finish_reason": finish_reason,
        })

        # 判断是否结束
        if not tool_calls or finish_reason in ("stop", "end_turn", "complete"):
            # LLM 认为任务完成，检查是否还有迭代余量但选择停止
            state["final_answer"] = content if content else "(LLM 未生成文本内容)"
            state["done"] = True
            logger.info(f"[Agent think] LLM 决定结束，finish_reason={finish_reason}")

        elif iteration >= state["max_iterations"]:
            # 达到最大迭代次数，强制结束
            logger.warning(
                f"[Agent think] 达到最大迭代次数 {iteration}/{state['max_iterations']}，强制结束"
            )
            state["final_answer"] = (
                content + "\n\n---\n\n⚠️ **Agent 达到最大迭代次数**，以上为最后一次思考结果。"
            ) if content else "⚠️ **Agent 达到最大迭代次数**，未生成最终答案。"
            state["done"] = True
        # 否则继续 → tool_exec 节点

        return state

    async def _node_tool_exec(self, state: AgentState) -> AgentState:
        """
        工具执行节点 — 执行 LLM 要求的所有 tool_calls

        对每个 tool_call：
        1. 从 tool_registry 查找完整 tool_info
        2. 解析 arguments JSON（LLM 返回的 arguments 是 JSON 字符串）
        3. 调用 MCPClientService.call_tool(tool_info, arguments)
        4. 结果格式化为 role="tool" 的消息追加到 messages
        """
        from app.services.mcp_client_service import MCPClientService

        # 从 messages 最后一条 assistant 消息中提取 tool_calls
        last_msg = state["messages"][-1] if state["messages"] else None
        if not last_msg or last_msg.get("role") != "assistant":
            logger.warning("[Agent tool_exec] 最后一条消息不是 assistant，跳过工具执行")
            state["done"] = True
            return state

        tool_calls = last_msg.get("tool_calls", [])
        if not tool_calls:
            logger.info("[Agent tool_exec] 无 tool_calls，跳过")
            state["done"] = True
            return state

        logger.info(f"[Agent tool_exec] 执行 {len(tool_calls)} 个工具调用")
        tool_registry = state.get("tool_registry", {})

        for tc in tool_calls:
            tc_id = tc.get("id", "")
            tc_func = tc.get("function", {})
            tc_name = tc_func.get("name", "")
            tc_args_str = tc_func.get("arguments", "{}")

            logger.info(f"[Agent tool_exec] 调用工具 {tc_name}(id={tc_id}), args={tc_args_str[:200]}")

            # 解析 arguments JSON
            try:
                arguments = json.loads(tc_args_str) if tc_args_str else {}
            except (json.JSONDecodeError, TypeError):
                logger.warning(f"[Agent tool_exec] arguments JSON 解析失败: {tc_args_str[:100]}")
                arguments = {}

            # 内置工具 read_reference：不走 MCP，直接从 references_full 读取全文
            if tc_name == TOOL_READ_REFERENCE:
                tool_result_text, success = self._exec_read_reference(state, arguments)
            else:
                # 从 registry 查找 tool_info
                tool_info = tool_registry.get(tc_name)
                if not tool_info:
                    logger.warning(
                        f"[Agent tool_exec] 工具 {tc_name} 不在 registry 中，"
                        f"可用工具={list(tool_registry.keys())}"
                    )
                    tool_result_text = f"工具 '{tc_name}' 未注册，无法调用。"
                    success = False
                else:
                    # 实际调用 MCP 工具
                    try:
                        tool_result = await MCPClientService.call_tool(
                            tool_info=tool_info,
                            arguments=arguments,
                        )
                        success = tool_result.get("success", True)
                        tool_result_text = tool_result.get("result", "")
                        # 结果过长时截断（避免 prompt 爆炸）
                        if len(str(tool_result_text)) > 5000:
                            tool_result_text = str(tool_result_text)[:5000] + "\n...(结果已截断)"
                    except Exception as e:
                        logger.error(f"[Agent tool_exec] 工具 {tc_name} 调用异常: {type(e).__name__}: {e}")
                        success = False
                        tool_result_text = f"工具调用异常: {type(e).__name__}: {str(e)}"

                    # MCP 连接类失败检测：MCP Server 未启动/不可达时硬停止，
                    # 防止 LLM 拿不到数据却继续编造诊断报告
                    if not success and self._is_mcp_connection_failure(str(tool_result_text)):
                        logger.error(
                            f"[Agent tool_exec] 检测到 MCP Server 连接失败，Agent 硬停止: "
                            f"tool={tc_name}, 失败信息={str(tool_result_text)[:200]}"
                        )
                        state["final_answer"] = (
                            f"⚠️ 无法完成 Skill 执行：调用 MCP 工具「{tc_name}」失败"
                            f"（MCP Server 未启动或网络不可达）。\n\n"
                            f"失败详情：{str(tool_result_text)[:300]}\n\n"
                            f"请检查：\n"
                            f"1. MCP Server 是否已启动（对应数据服务是否在运行）\n"
                            f"2. MCP Server URL 配置是否正确、网络是否可达\n"
                            f"3. 服务恢复后重新发起请求"
                        )
                        state["done"] = True
                        # MCP 连接失败硬停止标志：execute 收尾时据此返回
                        # success=False，让上层 MasterAgent 命中硬停止条件，
                        # 避免失败说明被包装为"执行成功+报告转述"误导 LLM
                        state["mcp_connection_failure"] = True
                        # 追加 tool result 消息（保持消息序列完整，便于 trace 审计）
                        state["messages"].append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "content": str(tool_result_text),
                        })
                        state["trace"].append({
                            "step": "tool_exec",
                            "tool_name": tc_name,
                            "tool_call_id": tc_id,
                            "arguments": arguments,
                            "success": False,
                            "result_preview": str(tool_result_text)[:300] if tool_result_text else "(空)",
                            "hard_stop": "mcp_connection_failure",
                        })
                        return state

            # 追加 tool result 消息
            state["messages"].append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": str(tool_result_text),
            })

            # 记录 trace
            state["trace"].append({
                "step": "tool_exec",
                "tool_name": tc_name,
                "tool_call_id": tc_id,
                "arguments": arguments,
                "success": success,
                "result_preview": str(tool_result_text)[:300] if tool_result_text else "(空)",
            })

            logger.info(
                f"[Agent tool_exec] 工具 {tc_name} 调用完成: success={success}, "
                f"result长度={len(str(tool_result_text))}"
            )

        return state

    async def _node_finalize(self, state: AgentState) -> AgentState:
        """
        最终整理节点 — 如果 final_answer 为空（异常路径兜底），尝试从 messages 中提取

        正常流程中 final_answer 在 agent_think 节点已经设置。
        这里只做兜底：如果 final_answer 为空，尝试从 messages 最后一条 assistant 提取 content。
        """
        if not state.get("final_answer"):
            # 从 messages 最后一条 assistant 消息提取 content
            for msg in reversed(state.get("messages", [])):
                if msg.get("role") == "assistant" and msg.get("content"):
                    state["final_answer"] = msg["content"]
                    logger.info("[Agent finalize] 从 messages 兜底提取 final_answer")
                    break

        if not state.get("final_answer"):
            state["final_answer"] = "Agent 执行完成但未生成有效答案。"
            logger.warning("[Agent finalize] 兜底仍未找到 final_answer")

        state["done"] = True
        logger.info(
            f"[Agent finalize] 整理完成, answer长度={len(state['final_answer'])}, "
            f"总迭代次数={state['iteration']}"
        )
        return state

    # ========================================================
    # LangGraph 图构建
    # ========================================================

    def _build_graph(self) -> Any:
        """
        构建 LangGraph StateGraph

        拓扑：
            skill_runtime → agent_think → (条件) → tool_exec → agent_think
                                            → finalize → END

        :return: 编译后的 LangGraph（带 ainvoke 方法）
        """
        graph = StateGraph(AgentState)

        # 添加节点
        graph.add_node("skill_runtime", self._node_runtime_init)
        graph.add_node("agent_think", self._node_agent_think)
        graph.add_node("tool_exec", self._node_tool_exec)
        graph.add_node("agent_finalize", self._node_finalize)

        # 设置入口
        graph.set_entry_point("skill_runtime")

        # skill_runtime → agent_think（初始化完成后直接进入思考）
        graph.add_edge("skill_runtime", "agent_think")

        # agent_think → 条件路由
        graph.add_conditional_edges(
            "agent_think",
            self._route_after_think,
            {
                "tool_exec": "tool_exec",
                "finalize": "agent_finalize",
            },
        )

        # tool_exec → 条件路由（硬停止时直接 finalize，避免再调 LLM 编造内容）
        graph.add_conditional_edges(
            "tool_exec",
            self._route_after_tool_exec,
            {
                "agent_think": "agent_think",
                "finalize": "agent_finalize",
            },
        )

        # agent_finalize → END
        graph.add_edge("agent_finalize", END)

        return graph.compile()

    # 注意：skill_runtime 节点目前不做额外操作（初始 state 已在 execute() 中设置好）
    # 但保留作为扩展点（如未来需要加载 assets、解压文件等）
    async def _node_runtime_init(self, state: AgentState) -> AgentState:
        """
        运行时初始化节点（扩展点）

        目前 state 已在 execute() 中完整构建，这里直接透传。
        未来可用于：加载本地脚本执行结果、解压临时数据文件等。
        """
        logger.info(
            f"[Agent runtime] 初始化完成: tools={len(state.get('tools', []))}, "
            f"max_iter={state.get('max_iterations', 10)}"
        )
        state["trace"].append({
            "step": "runtime_init",
            "timestamp": "start",
        })
        return state

    def _route_after_think(self, state: AgentState) -> str:
        """
        agent_think 后的条件路由函数

        - 如果 done=True → finalize
        - 否则 → tool_exec（即使没有 tool_calls 也安全，tool_exec 会检测并跳过）

        :param state: 当前状态
        :return: "tool_exec" | "finalize"
        """
        if state.get("done", False):
            return "finalize"
        return "tool_exec"

    def _route_after_tool_exec(self, state: AgentState) -> str:
        """
        tool_exec 后的条件路由函数

        - tool_exec 内硬停止（如 MCP 连接失败）时 done=True → finalize
        - 否则 → agent_think 继续思考

        :param state: 当前状态
        :return: "agent_think" | "finalize"
        """
        if state.get("done", False):
            return "finalize"
        return "agent_think"

    @staticmethod
    def _is_mcp_connection_failure(result_text: str) -> bool:
        """
        判断工具失败结果是否为 MCP 连接类失败

        仅匹配"连不上/超时/会话初始化失败"等基础设施故障特征，
        不匹配业务性失败（如参数错误、查询无数据），后者仍由 LLM 兜底处理。

        :param result_text: 工具失败返回的文本
        :return: 是否连接类失败
        """
        if not result_text:
            return False
        return any(p in result_text for p in _MCP_CONNECTION_FAILURE_PATTERNS)

    # ========================================================
    # 工具加载与筛选
    # ========================================================

    async def _load_and_filter_mcp_tools(
        self,
        db,
        tool_config_ids: List[int],
        declared_mcp_tools: List[Dict[str, str]],
    ) -> tuple:
        """
        加载 MCP 工具并根据 frontmatter 声明筛选

        通过 ToolRegistry.load_mcp_tools_cached 加载（带 TTL 类级缓存，
        与主对话工具注册共享同一份缓存，避免重复握手）。

        :return: (tools_openai_format, tool_registry)
        """
        # 1. 从 ToolRegistry 加载应用配置的 MCP 工具（走缓存）
        from app.services.tool_registry import ToolRegistry

        logger.info(
            f"[MCP筛选] 开始加载: tool_config_ids={tool_config_ids}, "
            f"declared_mcp_tools={declared_mcp_tools}, db={'有' if db else '无'}"
        )

        all_mcp_tools = await ToolRegistry.load_mcp_tools_cached(db, tool_config_ids or [])
        logger.info(f"[MCP筛选] load_mcp_tools_cached(ids={tool_config_ids}) 返回 {len(all_mcp_tools)} 个工具")

        # 2. 如果 frontmatter 没有声明任何 mcp_tools → 不暴露工具（安全默认）
        if not declared_mcp_tools:
            logger.info("Skill frontmatter 未声明 mcp_tools，不暴露 MCP 工具给 Agent")
            return [], {}

        # 3. 根据声明的工具名匹配筛选
        declared_names = set(t["name"] for t in declared_mcp_tools)
        tool_registry: Dict[str, Dict[str, Any]] = {}
        tools_openai: List[Dict[str, Any]] = []

        for mcp_tool in all_mcp_tools:
            tool_name = mcp_tool.get("tool_name", "")
            service_name = mcp_tool.get("service_name", "")
            server_name = mcp_tool.get("server_name", "")  # DB 里 MCP 配置的显示名

            # 收集所有可匹配的名称维度
            all_names_to_check = [tool_name, service_name, server_name]
            full_name = f"{service_name}_{tool_name}" if service_name else tool_name
            all_names_to_check.append(full_name)
            # 去掉空值
            all_names_to_check = [n for n in all_names_to_check if n]

            logger.info(
                f"[MCP筛选] 检查工具: tool_name={tool_name!r}, service={service_name!r}, "
                f"server={server_name!r}, 可匹配名={all_names_to_check}"
            )

            # 尝试多种名称匹配方式
            matched = False
            match_name = None
            for dn in declared_names:
                # 1) 精确匹配（所有维度）
                for n in all_names_to_check:
                    if n == dn:
                        matched = True; match_name = dn; break
                if matched: break

                # 2) 子串包含（声明名在工具名里 或 工具名在声明名里）
                if len(dn) >= 2:
                    for n in all_names_to_check:
                        if dn in n or n in dn:
                            matched = True; match_name = dn; break
                if matched: break

            if not matched:
                continue

            # 构建 OpenAI function-calling 格式
            description = mcp_tool.get("description", "")
            # 附加 frontmatter 声明的 purpose 到 description
            declared_purpose = ""
            for dt in declared_mcp_tools:
                if dt["name"] == match_name:
                    declared_purpose = dt.get("purpose", "")
                    break
            if declared_purpose and declared_purpose not in description:
                description = f"{description}\n用途说明: {declared_purpose}"

            parameters = mcp_tool.get("parameters") or {
                "type": "object",
                "properties": {},
            }

            # 注册到 registry（key 使用声明名，LLM 更容易理解）
            registry_key = match_name or tool_name
            tool_registry[registry_key] = mcp_tool

            tools_openai.append({
                "type": "function",
                "function": {
                    "name": registry_key,
                    "description": description[:1000],  # 防止 description 过长
                    "parameters": parameters,
                },
            })

            logger.info(
                f"[MCP筛选] 匹配成功: 声明={match_name}, "
                f"实际tool_name={tool_name}, service={service_name}"
            )

        # 4. 警告未匹配的声明
        matched_names = set(tool_registry.keys())
        for dt in declared_mcp_tools:
            if dt["name"] not in matched_names:
                logger.warning(
                    f"[MCP筛选] 声明的工具 '{dt['name']}' 未在应用配置中找到。"
                    f"已配置的MCP工具: {[t.get('tool_name') for t in all_mcp_tools]}"
                )

        logger.info(
            f"[MCP筛选] 完成: 声明={len(declared_mcp_tools)}个, "
            f"匹配成功={len(tool_registry)}个, 全部MCP={len(all_mcp_tools)}个"
        )

        return tools_openai, tool_registry

    # ========================================================
    # 辅助方法
    # ========================================================

    def _build_skill_context(
        self,
        skill_name: str,
        skill_description: str,
        skill_md_body: str,
        references: List[Dict[str, str]],
    ) -> str:
        """
        组装 Skill 上下文（用于注入到 system prompt 或 skill_context 字段）
        """
        parts: List[str] = [
            f"## Skill: {skill_name}",
            f"描述: {skill_description}",
            "",
            "## SKILL.md 定义",
            skill_md_body or "(无)",
        ]

        if references:
            # L3 渐进披露：只注入参考文档清单（文件名+摘要），
            # 全文通过内置工具 read_reference 按需读取，降低每轮 prefill 成本
            parts.append("")
            parts.append("## 参考文档清单")
            parts.append(
                "以下是本 Skill 的专业知识参考文档。需要查阅其中规则、标准、阈值等细节时，"
                "必须先调用 read_reference 工具读取全文，再基于内容执行分析："
            )
            for ref in references:
                name = ref.get("name", "未命名")
                content = ref.get("content", "")
                # 摘要：前 200 字符 + 全文长度提示
                summary = content[:200].replace("\n", " ").strip()
                parts.append(
                    f"- **{name}**（全文约{len(content)}字符）：{summary}..."
                )

        return "\n".join(parts)

    def _build_history_messages(
        self, history: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        构建主对话历史消息（注入 Skill Agent 的 messages）

        仅取最近 HISTORY_MAX_MESSAGES 条 user/assistant 消息，
        超过 HISTORY_MAX_CHARS 时从最旧的开始截断，保证子智能体
        能感知主对话上下文（用户此前提过的约束条件）。

        :param history: 主对话历史列表 [{role, content}]
        :return: 可注入的消息列表
        """
        # 只保留 user/assistant 角色且内容非空的消息
        valid = [
            {"role": m.get("role", ""), "content": (m.get("content") or "").strip()}
            for m in (history or [])
        ]
        valid = [m for m in valid if m["role"] in ("user", "assistant") and m["content"]]

        # 取最近 N 条
        recent = valid[-self.HISTORY_MAX_MESSAGES:]
        if not recent:
            return []

        # 总量超限时从最旧的开始丢弃整条消息（避免截断单条导致语义破碎）
        while len(recent) > 1 and sum(len(m["content"]) for m in recent) > self.HISTORY_MAX_CHARS:
            recent.pop(0)

        # 兜底：仅剩一条仍超限 → 截断该条内容
        if recent and len(recent[0]["content"]) > self.HISTORY_MAX_CHARS:
            recent[0]["content"] = (
                recent[0]["content"][: self.HISTORY_MAX_CHARS] + "\n...(历史消息过长已截断)"
            )

        return recent

    def _exec_read_reference(
        self, state: AgentState, arguments: Dict[str, Any]
    ) -> tuple:
        """
        执行内置工具 read_reference（L3 渐进披露核心）

        从 state.references_full 读取指定参考文档全文，
        不经过 MCP，单篇超过上限时截断保护。

        :param state: 当前执行状态
        :param arguments: 工具参数 {file_name}
        :return: (工具结果文本, 是否成功)
        """
        references_full = state.get("references_full", {}) or {}
        file_name = str(arguments.get("file_name", "")).strip()

        if not file_name:
            available = ", ".join(references_full.keys())
            return f"参数错误：file_name 不能为空。可用参考文档：{available}", False

        # 精确匹配优先，其次包含匹配（容错 LLM 传入带扩展名/路径的形式）
        content = references_full.get(file_name)
        if content is None:
            for name, text in references_full.items():
                if file_name in name or name in file_name:
                    content = text
                    file_name = name
                    break

        if content is None:
            available = ", ".join(references_full.keys())
            return (
                f"未找到参考文档 '{file_name}'。可用参考文档：{available}",
                False,
            )

        # 单篇截断保护（避免超长文档撑爆上下文）
        if len(content) > self.REFERENCE_MAX_CHARS:
            content = content[: self.REFERENCE_MAX_CHARS] + "\n\n...(文档过长已截断，如需后半部分内容请说明)"
            logger.info(
                f"[Agent read_reference] 文档 {file_name} 超长截断: "
                f"{len(references_full[file_name])} -> {self.REFERENCE_MAX_CHARS} 字符"
            )

        logger.info(f"[Agent read_reference] 读取参考文档: {file_name}，长度={len(content)}")
        return content, True

    def _format_tools_desc(self, tools: List[Dict[str, Any]]) -> str:
        """
        将 OpenAI 格式的 tools 列表格式化为可读的描述文本
        用于注入到 system prompt 中让 LLM 知道有哪些工具可用
        """
        if not tools:
            return ""
        lines = []
        for t in tools:
            func = t.get("function", {})
            name = func.get("name", "")
            desc = func.get("description", "")[:300]
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)

    @staticmethod
    def _get_llm_config(state: AgentState) -> Optional[Dict[str, Any]]:
        """从 state 或环境获取 LLM 配置"""
        # Agent 模式复用全局 llm_service 的配置即可
        # 因为 execute() 中 state 不携带 llm_config，这里返回 None 让 llm_service 用默认值
        # 如果未来需要应用级配置，可在 state 中增加 llm_config 字段
        return None


# 服务实例
skill_agent_executor = SkillAgentExecutor()
logger.info("SkillAgentExecutor 实例已创建（LangGraph 可用: {}）".format(_LANGGRAPH_AVAILABLE))
