"""
AgentReflector 规则版反思器（二期 Reflector 的规则实现，无LLM参与）

功能：在 MasterAgent ReAct 主循环的每轮工具执行后，基于确定性规则对
执行结果进行"反思"并触发纠错动作，弥补纯 LLM 决策在异常场景下的不可控性。

三条核心规则：
    R1 失败重试   —— 工具执行失败（疑似瞬时异常）时同参数自动重试1次；
                     参数校验类/幻觉工具名类确定性失败不重试（重试必然同样失败）
    R2 空数据降级 —— data 工具执行成功但无数据行时（ChatBI 内部两级SQL兜底
                     仍无数据），自动调用 knowledge_search 兜底检索一次，
                     以 system 消息注入观察结果供 LLM 综合回答（U8）
    R3 循环熔断   —— 同一工具+同参数签名被 LLM 重复调用达到阈值时熔断终止
                     工具循环，防止 token 浪费与死循环空转

设计要点：
    1. 纯规则零LLM调用：决策确定性可单测，不增加额外延迟与成本
    2. 决策透明：所有触发的规则由主循环记录进轮次轨迹（AgentTurnTrace.
       reflections），供 SSE reflect 事件透传（四期前端步骤条展示）
    3. 本类只做"判定"不做"执行"：重试/兜底的具体工具调用由 MasterAgent
       主循环统一编排，保持反思器可独立单测
    4. 反思动作全部有界：重试每签名1次、知识兜底每次运行1次、熔断即终止，
       不会放大调用量

编码规范：入参校验、详细文档注释、分层异常、日志记录、类型标注
"""
import json
from typing import Any, Dict

from loguru import logger

from app.services.tool_registry import ToolExecutionResult, ToolRegistry


class AgentReflector:
    """
    规则版反思器（有状态实例，与一次 MasterAgent 运行绑定）

    职责：
        1. make_signature / record_signature —— R3 调用签名登记与重复计数
        2. should_retry / mark_retry          —— R1 失败重试判定与配额管理
        3. is_empty_data_result / can_knowledge_fallback —— R2 空数据降级判定
        4. build_fallback_message             —— R2 知识兜底观察的 system 消息构造
    """

    # R3 循环熔断阈值：同签名第 3 次出现即熔断（已含2次冗余调用）
    MAX_DUPLICATE_CALLS = 3
    # R1 同签名失败重试上限
    MAX_FAILURE_RETRIES = 1
    # R2 单次运行知识兜底最大触发次数
    MAX_KNOWLEDGE_FALLBACKS = 1
    # R1 确定性失败特征（observation 命中任一则跳过重试）
    NON_RETRYABLE_MARKERS = (
        "不能为空",            # 参数校验类（query/question为空等）
        "不存在或不可用",       # 幻觉工具名兜底
        "未注册",              # 工具未注册
        "不存在。",            # Skill名称不在enum清单内
        "配置缺失或已停用",     # Skill配置被删除/停用
    )

    def __init__(self) -> None:
        """初始化反思器状态（签名计数/重试配额/兜底配额）"""
        # R3: {签名: LLM累计调用次数}
        self._signature_counts: Dict[str, int] = {}
        # R1: {签名: 已重试次数}
        self._retry_counts: Dict[str, int] = {}
        # R2: 已触发的知识兜底次数
        self._knowledge_fallbacks: int = 0

    # -------------------- R3 循环熔断 --------------------

    @staticmethod
    def make_signature(tool_name: str, arguments: Any) -> str:
        """
        生成调用签名（工具名 + 参数规范化JSON）

        参数规范化：dict 排序序列化；JSON字符串先解析再序列化，
        消除 LLM 输出 JSON 键序/空白差异导致的签名误判

        :param tool_name: 工具名
        :param arguments: 原始参数（dict / JSON字符串 / 其他）
        :return: 规范化签名串（如 'knowledge_search::{"query":"高炉温度"}'）
        """
        args_dict = ToolRegistry._normalize_arguments(arguments)
        try:
            args_str = json.dumps(args_dict, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            args_str = str(arguments)
        return f"{tool_name}::{args_str}"

    def record_signature(self, signature: str) -> int:
        """
        登记一次 LLM 发起的工具调用（反思器内部重试不计入）

        :param signature: make_signature 生成的调用签名
        :return: 该签名累计调用次数（含本次）
        """
        self._signature_counts[signature] = (
            self._signature_counts.get(signature, 0) + 1
        )
        return self._signature_counts[signature]

    @classmethod
    def is_duplicate_break(cls, count: int) -> bool:
        """
        判断同签名调用次数是否达到熔断阈值

        :param count: 同签名累计调用次数
        :return: True=达到阈值应熔断
        """
        return count >= cls.MAX_DUPLICATE_CALLS

    # -------------------- R1 失败重试 --------------------

    def should_retry(self, result: ToolExecutionResult, signature: str) -> bool:
        """
        判断失败结果是否值得同参数自动重试

        不重试的确定性失败（重试必然同样失败，浪费调用）：
            - result.tool_type == "unknown"（幻觉工具名，注册表即报错）
            - observation 命中 NON_RETRYABLE_MARKERS（参数校验类错误）
            - 该签名重试配额已用尽

        :param result: 工具执行结果（须为失败结果，成功结果直接返回False）
        :param signature: 调用签名
        :return: True=应同参数自动重试
        """
        if result.success:
            return False
        if result.tool_type == "unknown":
            return False
        if any(marker in result.observation for marker in self.NON_RETRYABLE_MARKERS):
            return False
        return self._retry_counts.get(signature, 0) < self.MAX_FAILURE_RETRIES

    def mark_retry(self, signature: str) -> None:
        """
        消耗一次该签名的重试配额

        :param signature: 调用签名
        """
        self._retry_counts[signature] = self._retry_counts.get(signature, 0) + 1

    # -------------------- R2 空数据降级（U8） --------------------

    @staticmethod
    def is_empty_data_result(result: ToolExecutionResult) -> bool:
        """
        判断是否为"执行成功但无数据行"的 data 工具结果

        :param result: 工具执行结果
        :return: True=应触发知识检索兜底
        """
        return (
            result.success
            and result.tool_type == "data"
            and not (result.payload or {}).get("data_results")
        )

    def can_knowledge_fallback(self, registry: ToolRegistry) -> bool:
        """
        判断当前是否可执行知识兜底（配额未用尽 且 知识工具已注册）

        :param registry: 工具注册中心
        :return: True=可执行 knowledge_search 兜底
        """
        if self._knowledge_fallbacks >= self.MAX_KNOWLEDGE_FALLBACKS:
            return False
        try:
            return bool(registry.get_tool_type(ToolRegistry.TOOL_KNOWLEDGE))
        except Exception as e:
            logger.warning(f"[Reflector] 知识兜底可用性检查异常（跳过兜底）: {e}")
            return False

    def mark_knowledge_fallback(self) -> None:
        """消耗一次知识兜底配额"""
        self._knowledge_fallbacks += 1

    @staticmethod
    def build_fallback_message(question: str, observation: str) -> Dict[str, str]:
        """
        构造知识兜底观察的 system 消息（协议安全：无需对应 tool_call_id）

        :param question: 触发兜底的数据查询问题
        :param observation: 知识检索观察文本
        :return: OpenAI 消息格式的 system 消息
        """
        return {
            "role": "system",
            "content": (
                f"【反思器·空数据兜底】数据查询『{question}』未返回数据，"
                "系统已自动执行知识库兜底检索，结果如下。请综合判断如何回应用户："
                "若知识库内容能解答问题请基于其回答；若仍无相关内容，"
                f"请如实告知用户暂无相关数据。\n{observation}"
            ),
        }
