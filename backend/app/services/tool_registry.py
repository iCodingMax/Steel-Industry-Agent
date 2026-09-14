"""
M1 统一工具注册中心（ToolRegistry）

功能：
    将平台四类能力（知识检索RAG / 智能问数ChatBI / Skill技能 / MCP工具）统一封装为
    OpenAI function-calling 格式的工具集，供 MasterAgent（LangGraph 智能体主循环）
    进行动态工具选择与调用。

核心能力：
    1. 应用级工具集解析：根据 Application 绑定的知识库/数据源/工具配置(JSONB)，
       构建该应用专属的工具清单（不同应用可见工具不同，实现权限隔离）
    2. 统一工具签名：输出 OpenAI tools 格式，直接对接 llm_service.chat_with_tools
    3. 统一执行入口：execute(tool_name, arguments, context) 返回标准化
       ToolExecutionResult（给LLM的观察文本 + 给前端的结构化数据）
    4. MCP 工具清单缓存：带 TTL 的类级缓存，避免每轮对话重复执行
       initialize + tools/list 握手（一期轻量缓存，二期 S2 升级为连接池）

工具清单（四类）：
    - knowledge_search : 知识检索（检索应用绑定的所有知识库，多库合并排序）
    - data_query       : 智能问数（NL2Metrics优先 → NL2SQL兜底）
    - execute_skill    : Skill技能调用（深度限1层：Skill内部由子智能体自治，不再嵌套）
    - mcp__{tool_name} : MCP工具（应用绑定的MCP配置展开为独立工具）

编码规范：入参校验、详细文档注释、分层异常、日志记录、类型标注
"""
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.datasource import DataSource
from app.models.knowledge import KnowledgeBase
from app.models.tool_config import ToolConfig

# ===================== 自定义业务异常 =====================


class ToolRegistryError(Exception):
    """工具注册中心统一业务异常基类"""
    pass


class ToolNotRegisteredError(ToolRegistryError):
    """工具未注册异常（调用了不存在的工具名）"""
    pass


class ToolBuildError(ToolRegistryError):
    """应用级工具集构建失败异常"""
    pass


# ===================== 数据结构定义 =====================


@dataclass
class ToolExecutionContext:
    """
    工具执行上下文

    由 MasterAgent 在每次工具调用时构建并传入，
    携带本轮对话所需的会话级信息，避免工具实现层重复查询。

    :param db: 数据库异步会话（业务库 steel_agent）
    :param session_id: 会话ID（用于Skill多轮交互、记忆关联）
    :param application_id: 应用ID（用于Skill执行时回查应用配置）
    :param history: 对话历史 [{"role": "user/assistant", "content": "..."}]
    :param llm_config: 应用级LLM配置（base_url/api_key/model等，Skill执行时使用）
    :param tool_config_ids: 应用绑定的工具配置ID列表（Skill内部MCP加载范围）
    :param user_question: 用户原始问题（区别于LLM改写后的工具参数question，
                          用于图表类型推荐时保留"表格/折线"等展示关键词）
    """
    db: AsyncSession
    session_id: Optional[int] = None
    application_id: Optional[int] = None
    history: Optional[List[Dict[str, str]]] = None
    llm_config: Optional[Dict[str, Any]] = None
    tool_config_ids: Optional[List[int]] = None
    user_question: Optional[str] = None


@dataclass
class ToolExecutionResult:
    """
    工具执行结果（标准化返回结构）

    双通道输出设计：
    - observation: 给LLM的观察文本（ReAct循环的Observation，纯文本+紧凑JSON，
                   带截断保护避免撑爆上下文）
    - payload: 给前端/上层的结构化数据（references/sql_traces/data_result等，
               由最终响应组装层透传，不进入LLM上下文）
    - success: 执行是否成功（失败时 observation 为错误说明，LLM可据此重试或换工具）

    :param observation: 给LLM的观察文本
    :param payload: 结构化数据载荷（可选）
    :param success: 执行状态
    :param tool_type: 工具类型（knowledge/data/skill/mcp）
    :param execution_time: 执行耗时（秒）
    """
    observation: str
    payload: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    tool_type: str = "unknown"
    execution_time: float = 0.0

    def to_observation_message(self, max_length: int = 6000) -> str:
        """
        转换为LLM观察消息（超长截断保护）

        :param max_length: 观察文本最大长度（超出部分截断并提示）
        :return: 截断保护后的观察文本
        """
        if len(self.observation) <= max_length:
            return self.observation
        return (
            self.observation[:max_length]
            + f"\n...(观察结果过长，已截断，原始长度{len(self.observation)}字符)"
        )


# ===================== 工具注册中心 =====================


class ToolRegistry:
    """
    统一工具注册中心

    职责：
        1. build_tools(db)      —— 解析应用资源绑定，构建应用级工具集
        2. get_openai_tools()   —— 输出 OpenAI function-calling 格式工具清单
        3. execute(name, args, ctx) —— 统一执行入口，返回 ToolExecutionResult

    设计说明：
        - 实例与"一次对话/一个应用"绑定（MasterAgent 每轮构建），
          MCP 工具清单缓存放在类级别（跨实例复用，TTL 过期自动刷新）
        - Skill 深度限1层：execute_skill 的 observation 只包含 Skill 最终回答，
          不暴露 Skill 内部工具调用链（Skill Agent 是独立子智能体，自治执行）
        - MCP 不可用时不注册幽灵工具（沿用 mcp_client_service 方案A原则），
          工具清单中不出现即 LLM 不会选择，避免编造结果
    """

    # 工具名称常量
    TOOL_KNOWLEDGE = "knowledge_search"
    TOOL_DATA = "data_query"
    TOOL_SKILL = "execute_skill"
    MCP_TOOL_PREFIX = "mcp__"

    # MCP 工具清单缓存：{(tool_config_id): (expire_at, tools_list)}
    _mcp_tools_cache: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
    # MCP 工具清单缓存TTL（秒）：MCP Server 工具列表变化频率低，5分钟足够
    MCP_TOOLS_CACHE_TTL = 300

    # 知识检索默认参数（可被调用参数覆盖）
    DEFAULT_TOP_K = 5
    DEFAULT_SCORE_THRESHOLD = 0.0

    # 观察文本截断长度（防止单个工具结果撑爆LLM上下文）
    MAX_OBSERVATION_LENGTH = 6000

    def __init__(self, application: Optional[Application] = None):
        """
        初始化工具注册中心

        :param application: 应用配置对象（可选，build_tools 前必须设置）
        :raises ValueError: application 类型非法时抛出
        """
        if application is not None and not isinstance(application, Application):
            raise ValueError("application 必须是 Application 模型实例或 None")

        self.application = application
        # 内部注册表: {tool_name: {"schema": {...}, "tool_type": str, ...元数据}}
        self._tools: Dict[str, Dict[str, Any]] = {}
        # 应用资源绑定快照（build_tools 时填充）
        self.knowledge_base_ids: List[int] = []
        self.datasource_ids: List[int] = []
        self.tool_config_ids: List[int] = []

    # -------------------- 工具集构建 --------------------

    async def build_tools(self, db: AsyncSession) -> "ToolRegistry":
        """
        构建应用级工具集

        根据 Application 的资源绑定（JSONB 字段）解析该应用可用的四类工具：
        1. knowledge_search：应用绑定了至少一个 active 知识库时注册
        2. data_query：应用绑定了至少一个 active 数据源时注册
        3. execute_skill：应用绑定了至少一个 active Skill 类型工具时注册
        4. mcp__*：应用绑定的 MCP 配置展开为独立工具（带TTL缓存）

        :param db: 数据库异步会话
        :return: self（支持链式调用）
        :raises ToolBuildError: 应用对象缺失时抛出
        """
        if self.application is None:
            raise ToolBuildError("构建应用级工具集失败：Application 未设置，请通过构造函数传入")

        start_time = time.time()
        # 重置内部状态（支持重复构建）
        self._tools.clear()
        self.knowledge_base_ids = []
        self.datasource_ids = []
        self.tool_config_ids = []

        app = self.application

        # 1. 解析应用资源绑定（JSONB 列表，容错处理 None/非法元素）
        self.knowledge_base_ids = self._parse_id_list(app.knowledge_base_ids)
        self.datasource_ids = self._parse_id_list(app.datasource_ids)
        self.tool_config_ids = self._parse_id_list(app.tool_config_ids)

        logger.info(
            f"[ToolRegistry] 开始构建应用工具集: 应用ID={app.id}, 名称={app.name!r}, "
            f"知识库={self.knowledge_base_ids}, 数据源={self.datasource_ids}, "
            f"工具配置={self.tool_config_ids}"
        )

        # 2. 并行解析三类资源的可用性（active状态过滤）
        kb_task = self._resolve_active_knowledge_bases(db, self.knowledge_base_ids)
        ds_task = self._resolve_active_datasources(db, self.datasource_ids)
        tools_task = self._resolve_active_tool_configs(db, self.tool_config_ids)
        active_kbs, active_ds_list, active_tool_cfgs = await asyncio.gather(
            kb_task, ds_task, tools_task
        )

        # 3. 注册 knowledge_search 工具（绑定了active知识库才注册）
        if active_kbs:
            self._register_knowledge_tool(active_kbs)

        # 4. 注册 data_query 工具（绑定了active数据源才注册）
        if active_ds_list:
            self._register_data_tool(active_ds_list)

        # 5. 拆分 Skill 与 MCP 工具配置
        skill_cfgs = [c for c in active_tool_cfgs if c.tool_type == "skill"]
        mcp_cfgs = [c for c in active_tool_cfgs if c.tool_type == "mcp"]

        # 6. 注册 execute_skill 工具（绑定了active Skill才注册）
        if skill_cfgs:
            self._register_skill_tool(skill_cfgs)

        # 7. 注册 mcp__* 工具（MCP配置展开，失败不阻塞其他工具注册）
        if mcp_cfgs:
            try:
                await self._register_mcp_tools(db, mcp_cfgs)
            except Exception as e:
                # MCP不可用只影响MCP工具，knowledge/data/skill照常可用
                logger.warning(f"[ToolRegistry] MCP工具注册失败（跳过，不影响其他工具）: {e}")

        elapsed = time.time() - start_time
        tool_names = list(self._tools.keys())
        logger.info(
            f"[ToolRegistry] 应用工具集构建完成: 应用ID={app.id}, "
            f"工具数={len(tool_names)}, 工具清单={tool_names}, 耗时={elapsed:.2f}s"
        )
        return self

    @staticmethod
    def _parse_id_list(raw: Any) -> List[int]:
        """
        解析 JSONB ID列表（容错：None/非列表/非整型元素）

        :param raw: JSONB 字段原始值（如 [1, 2, 3] 或 None）
        :return: 合法的整数ID列表（去重保序）
        """
        if not raw or not isinstance(raw, list):
            return []
        result: List[int] = []
        for item in raw:
            try:
                id_val = int(item)
                if id_val > 0 and id_val not in result:
                    result.append(id_val)
            except (TypeError, ValueError):
                continue
        return result

    @staticmethod
    async def _resolve_active_knowledge_bases(
        db: AsyncSession, kb_ids: List[int]
    ) -> List[KnowledgeBase]:
        """
        查询状态为 active 的知识库列表

        :param db: 数据库会话
        :param kb_ids: 知识库ID列表
        :return: active 状态的知识库对象列表
        """
        if not kb_ids:
            return []
        try:
            stmt = select(KnowledgeBase).where(
                KnowledgeBase.id.in_(kb_ids) & (KnowledgeBase.status == "active")
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.warning(f"[ToolRegistry] 查询知识库失败: {e}")
            return []

    @staticmethod
    async def _resolve_active_datasources(
        db: AsyncSession, ds_ids: List[int]
    ) -> List[DataSource]:
        """
        查询状态为 active 的数据源列表

        :param db: 数据库会话
        :param ds_ids: 数据源ID列表
        :return: active 状态的数据源对象列表
        """
        if not ds_ids:
            return []
        try:
            stmt = select(DataSource).where(
                DataSource.id.in_(ds_ids) & (DataSource.status == "active")
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.warning(f"[ToolRegistry] 查询数据源失败: {e}")
            return []

    @staticmethod
    async def _resolve_active_tool_configs(
        db: AsyncSession, tool_ids: List[int]
    ) -> List[ToolConfig]:
        """
        查询状态为 active 的工具配置列表（skill/mcp 混合）

        :param db: 数据库会话
        :param tool_ids: 工具配置ID列表
        :return: active 状态的工具配置对象列表
        """
        if not tool_ids:
            return []
        try:
            stmt = select(ToolConfig).where(
                ToolConfig.id.in_(tool_ids) & (ToolConfig.status == "active")
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            logger.warning(f"[ToolRegistry] 查询工具配置失败: {e}")
            return []

    # -------------------- 四类工具注册 --------------------

    def _register_knowledge_tool(self, kbs: List[KnowledgeBase]) -> None:
        """
        注册知识检索工具 knowledge_search

        多知识库设计：一次调用检索应用绑定的所有知识库，
        合并结果后按相似度排序取 topK。

        :param kbs: 应用绑定的 active 知识库对象列表
        """
        kb_names = [kb.name for kb in kbs]
        schema = {
            "type": "function",
            "function": {
                "name": self.TOOL_KNOWLEDGE,
                "description": (
                    "知识库检索工具。从应用绑定的钢铁行业知识库中检索工艺知识、技术规范、"
                    "操作规程、概念解释等文档内容。适用于『是什么/为什么/如何做/规范标准』"
                    "类知识问答。当前可用知识库: " + "、".join(kb_names)
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "检索问题（提取问题核心语义，去除口语化表达）",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": f"返回的文档片段数量，默认{self.DEFAULT_TOP_K}",
                        },
                    },
                    "required": ["query"],
                },
            },
        }
        self._tools[self.TOOL_KNOWLEDGE] = {
            "schema": schema,
            "tool_type": "knowledge",
            # 记录知识库ID列表（执行时重新查询KB对象，避免跨请求持有ORM对象）
            "kb_ids": [kb.id for kb in kbs],
        }

    def _register_data_tool(self, datasources: List[DataSource]) -> None:
        """
        注册智能问数工具 data_query

        :param datasources: 应用绑定的 active 数据源对象列表
        """
        ds_names = [ds.name for ds in datasources]
        schema = {
            "type": "function",
            "function": {
                "name": self.TOOL_DATA,
                "description": (
                    "智能问数工具（NL2SQL）。查询钢铁生产数据库中的生产数据、指标数值、"
                    "统计报表等结构化数据，支持自然语言描述查询需求并自动生成SQL。"
                    "适用于『展示/统计/多少/趋势/对比/排名』类数据查询。"
                    "当前可用数据源: " + "、".join(ds_names)
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "数据查询需求（完整描述查询对象、时间范围、统计维度）",
                        },
                    },
                    "required": ["question"],
                },
            },
        }
        self._tools[self.TOOL_DATA] = {
            "schema": schema,
            "tool_type": "data",
            # 首选数据源（应用绑定列表中的第一个active数据源）
            "preferred_datasource_id": datasources[0].id if datasources else None,
        }

    def _register_skill_tool(self, skill_cfgs: List[ToolConfig]) -> None:
        """
        注册 Skill 技能调用工具 execute_skill（深度限1层）

        设计约束：Skill 是独立子智能体（Skill Agent ReAct 自治执行），
        MasterAgent 只负责选择并转交，不感知 Skill 内部的工具调用链。
        observation 只返回 Skill 的最终回答。

        :param skill_cfgs: 应用绑定的 active Skill 工具配置列表
        """
        # 生成 Skill 清单描述（名称+描述摘要，供 LLM 选择）
        skill_lines = []
        for cfg in skill_cfgs:
            desc = (cfg.description or "").strip()
            # 描述截断（单个Skill描述限100字符，控制工具描述总长度）
            if len(desc) > 100:
                desc = desc[:100] + "..."
            skill_lines.append(f"- {cfg.name}: {desc}")

        schema = {
            "type": "function",
            "function": {
                "name": self.TOOL_SKILL,
                "description": (
                    "Skill技能执行工具。调用预置的领域专家技能（独立子智能体，"
                    "内部自主规划执行）。适用于复杂任务流程：诊断报告生成、文案创作等。"
                    "可用技能列表:\n" + "\n".join(skill_lines)
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "要执行的技能名称（必须从可用技能列表中选择）",
                            # OpenAI enum 约束可选技能范围，降低 LLM 选错概率
                            "enum": [cfg.name for cfg in skill_cfgs],
                        },
                        "question": {
                            "type": "string",
                            "description": "执行该技能的完整用户请求（含Skill所需的参数/数据输入）",
                        },
                    },
                    "required": ["skill_name", "question"],
                },
            },
        }
        # 记录技能名 → 工具配置ID 的映射（执行时按名称精确匹配）
        self._tools[self.TOOL_SKILL] = {
            "schema": schema,
            "tool_type": "skill",
            "skills_by_name": {cfg.name: cfg.id for cfg in skill_cfgs},
        }

    @classmethod
    async def _get_cached_mcp_tools(
        cls, db: AsyncSession, cfg: ToolConfig
    ) -> Optional[List[Dict[str, Any]]]:
        """
        获取指定 MCP 配置的工具清单（带 TTL 类级缓存）

        缓存命中直接复用；未命中/过期则调用 mcp_client_service 执行
        initialize + tools/list 握手拉取。与工具注册逻辑解耦，
        供 skill_agent_executor 等调用方复用同一份缓存。

        :param db: 数据库会话
        :param cfg: MCP 工具配置
        :return: 工具清单（该配置不可用时返回 None，不注册幽灵工具）
        """
        from app.services.mcp_client_service import mcp_client_service

        # 1. 查缓存（未过期直接复用）
        cached = cls._mcp_tools_cache.get(cfg.id)
        if cached and cached[0] > time.time():
            mcp_tools = cached[1]
            logger.debug(f"[ToolRegistry] MCP工具清单命中缓存: 配置ID={cfg.id}, 工具数={len(mcp_tools)}")
            return mcp_tools

        # 2. 缓存未命中/已过期：调用 mcp_client_service 拉取工具清单
        mcp_tools = await mcp_client_service.load_mcp_tools(db, [cfg.id])
        if not mcp_tools:
            # MCP 不可用：不注册幽灵工具（方案A原则），记录告警
            logger.warning(
                f"[ToolRegistry] MCP配置 [{cfg.name}] (ID={cfg.id}) 工具列表为空，"
                f"跳过该配置的工具注册（不注册幽灵工具）"
            )
            return None

        # 3. 写入缓存
        cls._mcp_tools_cache[cfg.id] = (
            time.time() + cls.MCP_TOOLS_CACHE_TTL,
            mcp_tools,
        )
        return mcp_tools

    async def _register_mcp_tools(
        self, db: AsyncSession, mcp_cfgs: List[ToolConfig]
    ) -> None:
        """
        注册 MCP 工具 mcp__{tool_name}

        将应用绑定的每个 MCP 配置展开为独立的 function-calling 工具。
        使用类级 TTL 缓存复用 tools/list 结果，避免每轮对话重复握手。

        工具命名规则：mcp__{tool_name}（与 LangChain MCP 适配器命名约定一致），
        若同名冲突则追加服务名前缀消歧。

        :param db: 数据库会话
        :param mcp_cfgs: 应用绑定的 active MCP 工具配置列表
        """
        for cfg in mcp_cfgs:
            # 1. 获取该配置的工具清单（带缓存；不可用时返回 None 跳过）
            mcp_tools = await self._get_cached_mcp_tools(db, cfg)
            if not mcp_tools:
                continue

            # 2. 展开为独立 function-calling 工具
            for tool_info in mcp_tools:
                raw_name = tool_info.get("tool_name") or f"mcp_tool_{cfg.id}"
                tool_name = f"{self.MCP_TOOL_PREFIX}{raw_name}"
                # 同名冲突消歧：追加服务名前缀
                if tool_name in self._tools:
                    service_name = tool_info.get("service_name") or str(cfg.id)
                    tool_name = f"{self.MCP_TOOL_PREFIX}{service_name}__{raw_name}"

                # 描述兜底（部分MCP Server工具描述为空）
                description = (tool_info.get("description") or "").strip()
                if not description:
                    description = f"MCP工具 {raw_name}（来自 {cfg.name}）"

                schema = {
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": description[:500],
                        "parameters": tool_info.get("parameters") or {"type": "object", "properties": {}},
                    },
                }
                self._tools[tool_name] = {
                    "schema": schema,
                    "tool_type": "mcp",
                    # 保留完整 tool_info（执行时透传给 mcp_client_service.call_tool）
                    "mcp_tool_info": tool_info,
                }

        mcp_registered = [n for n in self._tools if n.startswith(self.MCP_TOOL_PREFIX)]
        logger.info(f"[ToolRegistry] MCP工具注册完成: 数量={len(mcp_registered)}, 清单={mcp_registered}")

    @classmethod
    def clear_mcp_cache(cls, tool_config_id: Optional[int] = None) -> None:
        """
        清除 MCP 工具清单缓存

        供工具配置变更（新增/编辑/删除MCP配置）时主动失效缓存，
        避免工具清单与管理界面状态不一致。

        :param tool_config_id: 指定配置ID（None时清空全部缓存）
        """
        if tool_config_id is None:
            cls._mcp_tools_cache.clear()
            logger.info("[ToolRegistry] MCP工具清单缓存已全部清空")
        elif tool_config_id in cls._mcp_tools_cache:
            del cls._mcp_tools_cache[tool_config_id]
            logger.info(f"[ToolRegistry] MCP工具清单缓存已清除: 配置ID={tool_config_id}")

    @classmethod
    async def load_mcp_tools_cached(
        cls, db: AsyncSession, tool_config_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        按工具配置ID列表加载 MCP 工具清单（带 TTL 类级缓存）

        供 skill_agent_executor 等外部调用方复用注册中心的 MCP 缓存，
        与 build_tools 共享同一份缓存（同一 MCP 配置每 TTL 周期只握手一次）。

        与直接调用 mcp_client_service.load_mcp_tools 的差异：
        1. 走 TTL 缓存，避免 Skill 执行与主对话工具注册重复握手
        2. 自动过滤：仅加载 tool_type='mcp' 且 status='active' 的配置
           （传入的 tool_config_ids 通常混合 skill/mcp 两类，按 mcp 过滤）

        :param db: 数据库会话
        :param tool_config_ids: 工具配置ID列表（可混合 skill/mcp 类型）
        :return: MCP 工具清单（无可用的 MCP 配置时返回空列表）
        """
        if not tool_config_ids:
            return []

        # 查询 active 且 tool_type=mcp 的配置（过滤掉 skill 类型）
        try:
            stmt = select(ToolConfig).where(
                (ToolConfig.id.in_(tool_config_ids))
                & (ToolConfig.tool_type == "mcp")
                & (ToolConfig.status == "active")
            )
            result = await db.execute(stmt)
            mcp_cfgs = list(result.scalars().all())
        except Exception as e:
            logger.warning(f"[ToolRegistry] 查询MCP工具配置失败: {e}")
            return []

        if not mcp_cfgs:
            return []

        # 逐配置取缓存清单并合并（不可用配置跳过，不塞幽灵工具）
        all_tools: List[Dict[str, Any]] = []
        for cfg in mcp_cfgs:
            tools = await cls._get_cached_mcp_tools(db, cfg)
            if tools:
                all_tools.extend(tools)
        return all_tools

    # -------------------- 工具清单输出 --------------------

    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """
        输出 OpenAI function-calling 格式工具清单

        返回格式与 llm_service.chat_with_tools 的 tools 参数直接对接：
        [{"type": "function", "function": {...}}, ...]

        :return: 工具 schema 列表（未注册任何工具时返回空列表）
        """
        return [meta["schema"] for meta in self._tools.values()]

    def get_tool_names(self) -> List[str]:
        """
        输出已注册的工具名清单

        :return: 工具名列表（保持注册顺序）
        """
        return list(self._tools.keys())

    def has_tools(self) -> bool:
        """
        判断当前应用是否注册了任何工具

        :return: True=至少注册了一个工具
        """
        return bool(self._tools)

    def get_tool_type(self, tool_name: str) -> Optional[str]:
        """
        查询指定工具的类型

        :param tool_name: 工具名
        :return: 工具类型（knowledge/data/skill/mcp），未注册返回 None
        """
        meta = self._tools.get(tool_name)
        return meta["tool_type"] if meta else None

    # -------------------- 统一执行入口 --------------------

    @staticmethod
    def _normalize_arguments(arguments: Any) -> Dict[str, Any]:
        """
        归一化工具调用参数（容错处理）

        LLM 返回的 arguments 可能是 dict 或 JSON 字符串（不同模型行为不一致），
        统一转换为 dict；解析失败返回空 dict（由具体工具的必填校验兜底报错）。

        :param arguments: 原始参数（dict / JSON字符串 / 其他）
        :return: 归一化后的参数字典
        """
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str) and arguments.strip():
            try:
                parsed = json.loads(arguments)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                logger.warning(f"[ToolRegistry] 工具参数JSON解析失败，按空参数处理: {arguments[:200]}")
                return {}
        return {}

    async def execute(
        self,
        tool_name: str,
        arguments: Any,
        ctx: ToolExecutionContext,
    ) -> ToolExecutionResult:
        """
        统一工具执行入口

        根据工具类型路由到对应执行方法，统一异常兜底与耗时统计。
        失败时返回 success=False 的结果（observation 为错误说明，LLM 可据此
        决定重试、换工具或向用户致歉），不向上抛异常。

        :param tool_name: 工具名（必须在注册清单内）
        :param arguments: 工具参数（dict 或 JSON 字符串，自动归一化）
        :param ctx: 工具执行上下文（db会话、会话ID、历史、LLM配置等）
        :return: 标准化执行结果 ToolExecutionResult
        :raises ToolNotRegisteredError: 工具名不在注册清单时抛出（调用方bug）
        :raises ValueError: 执行上下文类型非法时抛出
        """
        # 1. 前置校验
        if tool_name not in self._tools:
            raise ToolNotRegisteredError(
                f"工具 {tool_name!r} 未注册，当前可用工具: {self.get_tool_names()}"
            )
        if not isinstance(ctx, ToolExecutionContext):
            raise ValueError("ctx 必须是 ToolExecutionContext 实例")

        # 2. 参数归一化 + 按类型路由
        normalized_args = self._normalize_arguments(arguments)
        tool_type = self._tools[tool_name]["tool_type"]
        start_time = time.time()

        logger.info(
            f"[ToolRegistry] 开始执行工具: name={tool_name}, type={tool_type}, "
            f"arguments={json.dumps(normalized_args, ensure_ascii=False)[:300]}"
        )

        try:
            if tool_type == "knowledge":
                result = await self._execute_knowledge_search(ctx.db, normalized_args)
            elif tool_type == "data":
                result = await self._execute_data_query(ctx.db, normalized_args, ctx)
            elif tool_type == "skill":
                result = await self._execute_skill(ctx.db, normalized_args, ctx)
            elif tool_type == "mcp":
                result = await self._execute_mcp_tool(tool_name, normalized_args)
            else:
                # 理论不可达（注册时类型受控），防御性兜底
                result = ToolExecutionResult(
                    observation=f"未知的工具类型: {tool_type}",
                    success=False,
                    tool_type=tool_type,
                )
        except Exception as e:
            # 统一异常兜底：工具内部异常转为失败结果，不中断 MasterAgent 主循环
            logger.error(
                f"[ToolRegistry] 工具执行异常: name={tool_name}, "
                f"异常={type(e).__name__}: {e}",
                exc_info=True,
            )
            result = ToolExecutionResult(
                observation=f"工具 {tool_name} 执行异常: {type(e).__name__}: {e}",
                success=False,
                tool_type=tool_type,
            )

        # 3. 统一回填类型与耗时
        result.tool_type = tool_type
        result.execution_time = time.time() - start_time

        logger.info(
            f"[ToolRegistry] 工具执行完成: name={tool_name}, success={result.success}, "
            f"耗时={result.execution_time:.2f}s, 观察文本长度={len(result.observation)}"
        )
        return result

    async def _execute_knowledge_search(
        self, db: AsyncSession, arguments: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        执行知识检索（多知识库并行检索，合并排序取 topK）

        :param db: 数据库会话
        :param arguments: 工具参数 {"query": str, "top_k"?: int}
        :return: observation 为拼接的检索片段文本，payload 含 references
        """
        from app.schemas.knowledge import KnowledgeQuery
        from app.services.vector_service import VectorIndexService

        # 1. 必填参数校验
        query_text = (arguments.get("query") or "").strip()
        if not query_text:
            return ToolExecutionResult(
                observation="知识检索失败：参数 query 不能为空，请提供检索问题",
                success=False, tool_type="knowledge",
            )

        # 2. top_k 限幅（1~20，与 KnowledgeQuery schema 约束一致）
        try:
            top_k = int(arguments.get("top_k") or self.DEFAULT_TOP_K)
        except (TypeError, ValueError):
            top_k = self.DEFAULT_TOP_K
        top_k = max(1, min(20, top_k))

        # 3. 重新查询 active 知识库（不跨请求持有过期 ORM 对象）
        kb_ids = self._tools[self.TOOL_KNOWLEDGE].get("kb_ids", [])
        kbs = await self._resolve_active_knowledge_bases(db, kb_ids)
        if not kbs:
            return ToolExecutionResult(
                observation="知识检索失败：应用未绑定可用的知识库，无法执行检索",
                success=False, tool_type="knowledge",
            )

        # 4. 多库并行检索
        search_tasks = []
        for kb in kbs:
            kq = KnowledgeQuery(
                knowledgeBaseId=kb.id,
                question=query_text,
                topK=top_k,
                scoreThreshold=self.DEFAULT_SCORE_THRESHOLD,
            )
            search_tasks.append(VectorIndexService.search(db, kq, kb))
        per_kb_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # 5. 合并结果（异常的库跳过），按相似度降序
        merged: List[Any] = []
        failed_kbs: List[str] = []
        for kb, res in zip(kbs, per_kb_results):
            if isinstance(res, Exception):
                failed_kbs.append(kb.name)
                logger.warning(f"[ToolRegistry] 知识库 {kb.name!r} 检索异常: {res}")
            else:
                merged.extend(res)
        merged.sort(key=lambda r: r.score, reverse=True)
        merged = merged[:top_k]

        # 6. 组装观察文本（给LLM）与 payload（给前端引用）
        if not merged:
            obs_lines = [f"知识库检索『{query_text}』未找到相关内容（检索了{len(kbs)}个知识库）。"]
            if failed_kbs:
                obs_lines.append(f"注意：知识库 {('、'.join(failed_kbs))} 检索失败被跳过。")
            obs_lines.append("建议：改写检索词重试，或改用其他工具回答。")
            return ToolExecutionResult(
                observation="\n".join(obs_lines),
                payload={"references": [], "query": query_text},
                tool_type="knowledge",
            )

        obs_lines = [f"知识库检索『{query_text}』命中 {len(merged)} 条相关内容：\n"]
        references = []
        for idx, r in enumerate(merged, 1):
            obs_lines.append(
                f"【片段{idx}】来源: {r.documentName} | 相似度: {r.score:.4f}\n{r.content}\n"
            )
            references.append(r.model_dump())

        warn_suffix = ""
        if failed_kbs:
            warn_suffix = f"\n（注意：知识库 {'、'.join(failed_kbs)} 检索失败被跳过）"

        return ToolExecutionResult(
            observation="\n".join(obs_lines) + warn_suffix,
            payload={"references": references, "query": query_text},
            tool_type="knowledge",
        )

    async def _execute_data_query(
        self, db: AsyncSession, arguments: Dict[str, Any], ctx: ToolExecutionContext
    ) -> ToolExecutionResult:
        """
        执行智能问数（ChatBI：NL2Metrics优先 → NL2SQL兜底）

        :param db: 数据库会话
        :param arguments: 工具参数 {"question": str}
        :param ctx: 执行上下文（history 用于多轮问数，如"上月呢？"的指代消解）
        :return: observation 为结果解释，payload 含 sql_traces/data/column_meta/chart_type
        """
        from app.services.chatbi_service import ChatBIService

        # 1. 必填参数校验
        question = (arguments.get("question") or "").strip()
        if not question:
            return ToolExecutionResult(
                observation="数据查询失败：参数 question 不能为空，请描述完整的数据查询需求",
                success=False, tool_type="data",
            )

        # 2. 首选数据源（注册时记录的应用绑定第一个active数据源）
        preferred_ds_id = self._tools[self.TOOL_DATA].get("preferred_datasource_id")

        # 3. 调用 ChatBI 完整流程（内部自动 NL2Metrics → NL2SQL 兜底）
        (
            result_explanation,
            data_results,
            sql_traces,
            query_time,
            _explanation_prompt,
            column_meta,
            chart_type,
        ) = await ChatBIService.query(
            db,
            question,
            datasource_id=preferred_ds_id,
            history=ctx.history,
        )

        # 3.1 图表类型修正：ChatBI 按改写后的 question 推荐图表类型，
        # LLM 改写可能丢失"表格/折线"等展示关键词（如"使用表格展示..."被改写成
        # "查询2025年不同班次的炉况报告结果"），此处用用户原始问题重新推荐，
        # 命中展示关键词时覆盖，保持 agent 模式与数据助手的展示行为一致
        if ctx.user_question:
            user_chart_type = ChatBIService.suggest_chart_type(ctx.user_question)
            if user_chart_type != chart_type:
                logger.info(
                    f"图表类型按用户原始问题修正: {chart_type} -> {user_chart_type} "
                    f"(用户问题={ctx.user_question[:50]})"
                )
                chart_type = user_chart_type

        # 4. 数据为空的处理（query成功但无结果行）
        if not data_results:
            observation = (
                f"数据查询『{question}』执行成功但未返回数据。\n"
                f"SQL溯源: {json.dumps(sql_traces, ensure_ascii=False)[:500]}\n"
                f"建议：检查查询条件（时间范围/统计维度）是否过窄，或改写查询需求。"
            )
            return ToolExecutionResult(
                observation=observation,
                payload={
                    "sql_traces": sql_traces,
                    "data_results": None,
                    "column_meta": column_meta,
                    "chart_type": chart_type,
                    "query_time": query_time,
                },
                tool_type="data",
            )

        # 5. 正常返回：observation 给解释文本 + 数据摘要，payload 给前端渲染
        # 数据摘要限制条数（防止数据行过多撑爆上下文，前端由 payload 完整渲染）
        preview_rows = data_results[:20]
        try:
            data_preview = json.dumps(preview_rows, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            data_preview = str(preview_rows)

        observation = (
            f"数据查询『{question}』成功，返回 {len(data_results)} 行数据"
            f"（观察文本仅展示前{len(preview_rows)}行，完整数据见结构化结果）。\n"
            f"结果解释: {result_explanation or '（无）'}\n"
            f"数据: {data_preview[:2000]}\n"
            f"【输出要求】查询结果将以独立的数据可视化区域（表格/图表）展示给用户，"
            f"最终回答中不要用Markdown表格复述以上数据，只基于数据输出结论性分析。"
        )

        return ToolExecutionResult(
            observation=observation,
            payload={
                "sql_traces": sql_traces,
                "data_results": data_results,
                "column_meta": column_meta,
                "chart_type": chart_type,
                "query_time": query_time,
            },
            tool_type="data",
        )

    async def _execute_skill(
        self, db: AsyncSession, arguments: Dict[str, Any], ctx: ToolExecutionContext
    ) -> ToolExecutionResult:
        """
        执行 Skill 技能（深度限1层：Skill内部为独立子智能体自治执行）

        与 RouterService._execute_skill 的区别：
            - 工具名由 LLM 从 enum 中选择（无需关键词匹配/上下文保持启发式）
            - 只透传最终回答，不暴露 Skill 内部工具调用链
            - Skill 的多轮引导由 MasterAgent 的会话记忆天然承接
              （Skill 返回"请提供XX信息"→ MasterAgent 组织回复 → 用户补充 →
               LLM 结合历史再次调用 execute_skill，question 携带补充数据）

        :param db: 数据库会话
        :param arguments: 工具参数 {"skill_name": str, "question": str}
        :param ctx: 执行上下文（llm_config/history 透传给 Skill 执行器）
        :return: observation 为 Skill 最终回答，payload 含 skill 执行元信息
        """
        from app.services.skill_executor_service import skill_executor_service
        from app.services.tool_config_service import resolve_skill_path

        # 1. 必填参数校验
        skill_name = (arguments.get("skill_name") or "").strip()
        question = (arguments.get("question") or "").strip()
        if not skill_name or not question:
            return ToolExecutionResult(
                observation=(
                    "Skill执行失败：参数 skill_name 与 question 均不能为空。"
                    "skill_name 必须从可用技能列表中选择。"
                ),
                success=False, tool_type="skill",
            )

        # 2. 技能名精确匹配注册表（LLM 可能返回近似名，做一次容错校正）
        skills_by_name: Dict[str, int] = self._tools[self.TOOL_SKILL].get("skills_by_name", {})
        matched_name = None
        if skill_name in skills_by_name:
            matched_name = skill_name
        else:
            # 容错：忽略大小写与首尾空白后匹配
            name_map = {n.lower(): n for n in skills_by_name}
            matched_name = name_map.get(skill_name.lower())
        if not matched_name:
            return ToolExecutionResult(
                observation=(
                    f"Skill执行失败：技能 {skill_name!r} 不存在。"
                    f"可用技能: {list(skills_by_name.keys())}"
                ),
                success=False, tool_type="skill",
            )

        # 3. 加载 Skill 工具配置（执行时回查，避免持有过期 ORM 对象）
        skill_cfg_id = skills_by_name[matched_name]
        stmt = select(ToolConfig).where(
            (ToolConfig.id == skill_cfg_id) & (ToolConfig.status == "active")
        )
        cfg_result = await db.execute(stmt)
        skill_cfg = cfg_result.scalar_one_or_none()
        if not skill_cfg or not skill_cfg.skill_file_path:
            return ToolExecutionResult(
                observation=f"Skill执行失败：技能 {matched_name!r} 配置缺失或已停用",
                success=False, tool_type="skill",
            )

        # 4. 解析 ZIP 路径并调用 Skill 执行引擎（统一入口，内部自动判断 single/agent 模式）
        try:
            skill_zip_path = resolve_skill_path(skill_cfg.skill_file_path)
        except Exception as e:
            return ToolExecutionResult(
                observation=f"Skill执行失败：技能文件路径解析异常 {matched_name!r}: {e}",
                success=False, tool_type="skill",
            )

        # 5. tool_config_ids 优先取上下文（MasterAgent传入），回退应用绑定
        effective_tool_ids = ctx.tool_config_ids or self.tool_config_ids

        exec_result = await skill_executor_service.execute_skill(
            zip_path=skill_zip_path,
            skill_name=skill_cfg.name,
            skill_description=skill_cfg.description or "",
            question=question,
            history=ctx.history,
            llm_config=ctx.llm_config,
            db=db,
            tool_config_ids=effective_tool_ids,
        )

        # 6. 组装结果（answer 为 Skill 最终回答，可能是多轮引导提示）
        answer = exec_result.get("answer", "")
        success = bool(exec_result.get("success", False))
        if not success or not answer:
            observation = answer or f"Skill {matched_name!r} 执行未返回结果"
        else:
            observation = (
                f"Skill {matched_name!r} 执行完成，输出如下：\n{answer}"
            )

        return ToolExecutionResult(
            observation=observation,
            success=success,
            payload={
                "skill_name": matched_name,
                "skill_answer": answer,
                "skill_files": exec_result.get("skill_files", []),
                "execution_mode": exec_result.get("execution_mode", ""),
            },
            tool_type="skill",
        )

    async def _execute_mcp_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> ToolExecutionResult:
        """
        执行 MCP 工具（透传给 mcp_client_service.call_tool）

        tool_info 在注册时缓存于工具元数据中，执行时直接透传，
        避免重复执行 initialize + tools/list 握手。

        :param tool_name: 注册的工具名（mcp__{tool_name} 格式）
        :param arguments: 工具参数（按 MCP Server 声明的 JSON Schema）
        :return: observation 为工具结果文本，payload 含原始返回
        """
        from app.services.mcp_client_service import mcp_client_service

        tool_meta = self._tools.get(tool_name, {})
        tool_info = tool_meta.get("mcp_tool_info")
        if not tool_info:
            return ToolExecutionResult(
                observation=f"MCP工具执行失败：{tool_name!r} 缺少工具元信息（可能已失效）",
                success=False, tool_type="mcp",
            )

        # 调用 MCP 客户端（call_tool 返回 {success, result, raw_result?}）
        call_result = await mcp_client_service.call_tool(tool_info, arguments)
        success = bool(call_result.get("success", False))
        raw_result = call_result.get("result")

        # 结果序列化（MCP 工具返回结构多样，统一转文本观察）
        try:
            result_text = (
                raw_result if isinstance(raw_result, str)
                else json.dumps(raw_result, ensure_ascii=False, default=str)
            )
        except (TypeError, ValueError):
            result_text = str(raw_result)

        if not success:
            observation = (
                f"MCP工具 {tool_name} 调用失败: {result_text[:1000]}\n"
                f"建议：检查参数是否符合工具定义，或稍后重试。"
            )
        else:
            observation = (
                f"MCP工具 {tool_name} 调用成功，返回结果：\n{result_text}"
            )

        return ToolExecutionResult(
            observation=observation,
            success=success,
            payload={"mcp_result": raw_result},
            tool_type="mcp",
        )


# ===================== 便捷构造入口 =====================


async def build_tool_registry(
    db: AsyncSession, application: Application
) -> ToolRegistry:
    """
    构建应用级工具注册中心（便捷入口，供 MasterAgent / chat 通道调用）

    :param db: 数据库异步会话
    :param application: 应用配置对象
    :return: 已完成工具集构建的 ToolRegistry 实例
    :raises ToolBuildError: 应用对象非法或构建失败时抛出
    """
    registry = ToolRegistry(application=application)
    await registry.build_tools(db)
    return registry

