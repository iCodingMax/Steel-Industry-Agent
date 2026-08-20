"""
路由分发服务

本模块负责用户问题的意图识别和路由分发，是系统的核心调度层。

主要组件：
1. IntentClassifier：意图分类器
   - 使用关键词预判断 + LLM对用户问题进行意图分类（knowledge/data/mcp/skill/hybrid/chat）
   - 支持混合问题拆分为数据子问题和知识子问题
   - LLM分类时参考工具管理中已配置的MCP/Skills名称和描述

2. RouterService：路由分发服务
   - 根据意图分类结果将问题分发到对应处理通道
   - 支持闲聊对话通道、知识问答通道、数据查询通道、MCP工具调用通道、Skill工具调用通道、混合分析通道
   - 融合混合分析的结果，生成统一回答

核心流程：
    用户问题
        │
        ▼
    IntentClassifier.classify()  → 意图分类
        │
        ├── chat      → llm_service.chat()                    # 闲聊对话（直接LLM回答）
        ├── knowledge → knowledge_qa_service.answer()         # 知识问答
        ├── data      → chatbi_service.query()                # 数据查询
        ├── mcp       → mcp_client_service.execute_tool_calls()  # MCP工具调用
        ├── skill     → RouterService._execute_skill()        # Skill工具调用
        └── hybrid    → 并行调用知识+数据通道，融合结果
"""
import json
import re
import time
from typing import List, Optional, Tuple, Dict
from loguru import logger

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import KnowledgeBase
from app.models.tool_config import ToolConfig
from app.services.llm_service import llm_service
from app.services.vector_service import knowledge_qa_service
from app.services.chatbi_service import chatbi_service
from app.services.mcp_client_service import mcp_client_service
from app.services.tool_config_service import resolve_skill_path
from app.schemas.knowledge import KnowledgeQuery


class IntentClassifier:
    """
    意图分类器

    使用关键词预判断 + LLM对用户问题进行意图分类，支持五种意图类型：
    - knowledge：知识问答意图（工艺知识、技术规范、概念解释等）
    - data：数据查询意图（生产数据、指标数值、统计报表等）
    - mcp：MCP工具调用意图（通过MCP协议调用外部服务，如地图、天气等）
    - skill：Skill工具调用意图（执行本地技能脚本，如代码执行、文件处理等）
    - hybrid：混合意图（同时包含知识问答与数据查询两种意图）

    分类依据（优先级从高到低）：
    1. 强MCP关键词：天气、地图等单个命中即判定为mcp
    2. 强Skill关键词：执行代码、运行脚本等单个命中即判定为skill
    3. 混合意图：有连接词且同时包含knowledge和data关键词（仅knowledge+data）
    4. 单一意图：仅包含一种意图的关键词
    5. LLM分类：对复杂问题进行深度语义理解（参考工具管理中的MCP/Skills名称与描述）
    """

    # 强MCP关键词：单个命中即判定为mcp意图（最高优先级）
    # 注意："预警"和"定位"在工业场景中是高频词（炉况预警、异常定位），
    #        不应作为强MCP关键词，天气预警可通过"天气"识别，地图定位可通过"地图"/"导航"识别
    STRONG_MCP_KEYWORDS = [
        # 天气相关
        '天气', '气温', '下雨', '刮风',
        # 地图/导航相关
        '地图', '导航', '怎么走', '路线规划', '路径规划',
        '在哪里', '附近', '周边',
        '高德', 'amap',
        # 时间查询相关（避免被 DATA_KEYWORDS 的"多少"误判为 data 意图）
        # 注意：'时间'单独使用过于宽泛（如"生产时间"、"运行时间"），故仅添加明确表达
        '北京时间', '现在几点', '几点了', '当前时间', '今天几点',
        '今天日期', '今天几号', '现在日期', '当前日期', '今天是几号',
    ]

    # MCP意图普通关键词（需要调用MCP外部工具的场景）
    MCP_KEYWORDS = [
        # 地图/地理相关
        '路线', '位置', '地点', '地址', '距离',
        '公交', '地铁', '驾车', '步行', '骑行', '高速',
        # 实时信息相关
        '温度', '新闻', '资讯', '实时',
        '股票', '汇率', '油价', '金价',
        # 外部服务相关
        '搜索', '翻译', '换算', '查询位置', '查询地点',
        '地图查询',
    ]

    # 强Skill关键词：单个命中即判定为skill意图
    # P2管控修复：仅当用户完整输入"高炉炉况诊断"5字短语或其明确执行变体时才触发Skill
    # 移除'炉况诊断'、'使用技能'、'调用技能'、'运行技能'等宽泛表达，避免工业术语误判
    STRONG_SKILL_KEYWORDS = [
        # 完整Skill名称（5字短语）
        '高炉炉况诊断',
        # 明确执行变体（需同时包含"高炉炉况诊断"完整短语）
        '执行高炉炉况诊断', '运行高炉炉况诊断',
        '使用高炉炉况诊断技能', '调用高炉炉况诊断技能',
        # P2修复：新增"产品营销文案" Skill 名称
        # 用户直接说出"产品营销文案"时立即判定为skill意图，避免被LLM误判为knowledge
        '产品营销文案',
        # 明确执行变体（需同时包含"产品营销文案"完整短语）
        '执行产品营销文案', '运行产品营销文案',
        '使用产品营销文案技能', '调用产品营销文案技能',
        # 简写变体（"产品文案"、"营销文案"在 _quick_classify 中不作为强关键词，
        # 因为过于宽泛，会误命中"介绍下产品文案"等普通问题，由 1.5 步骤动态匹配处理）
    ]

    # Skill意图普通关键词（需要多个同时命中才判定）
    # P2管控修复：清空普通关键词，仅靠STRONG_SKILL_KEYWORDS + LLM严格分类
    # 避免"高炉炉况"等子串误命中"炉况波动"、"炉况分析"等工业术语
    SKILL_KEYWORDS = []

    # data意图关键词（查询内部数据库数据）
    # 注意：高炉、转炉等领域名词不应作为data关键词，因为它们在知识问答中也很常见
    # 数据查询应通过动词/量词（展示、统计、产量等）来识别
    DATA_KEYWORDS = [
        '展示', '统计', '多少', '次数', '数量',
        '产量', '合格率', '能耗', '报表', '图表', '趋势',
        '排名', '汇总', '对比', '分析',
        '生产', '指标', '记录', '历史',
        '吹炼', '熔炼', '轧制', '连铸',
    ]

    # knowledge意图关键词（知识问答）
    KNOWLEDGE_KEYWORDS = [
        '是什么', '为什么', '怎么', '如何', '原理', '流程',
        '解释', '说明', '定义', '概念',
        '规范', '标准', '制度', '规程', '操作',
        '介绍', '简介', '概述', '概况',
    ]

    # 强chat关键词：单个命中即判定为chat，不受其他关键词影响
    # 这些是明确的闲聊/问候/自我介绍/上下文相关表达，不会与知识/数据查询混淆
    # 注意：'你能做什么'、'你会什么' 已移除，因为与"询问技能列表"高度重叠，
    #       由 INQUIRE_SKILL_PATTERNS 优先处理；不在技能关键词范围内时再由LLM兜底闲聊
    STRONG_CHAT_KEYWORDS = [
        '你好', '您好', 'hello', '嗨',  # 移除'hi'（2字符过短，JSON/技术文档中易子串误匹配）
        '谢谢', '感谢', '再见', '拜拜',
        '介绍下自己', '介绍一下自己', '你是谁', '你叫什么',
        # 上下文相关问题：用户询问自己之前提供的信息，需要参考对话历史
        # 这些表达必须走chat分支（走knowledge会检索知识库而忽略历史）
        '我叫什么', '我的名字', '我是谁', '我叫啥', '我名字',
        '你还记得', '你记得我', '刚才我说', '我刚才说',
        '我告诉过你', '我说过什么',
    ]

    # 询问技能列表的表达：优先级高于普通chat关键词，应判定为skill进入技能展示分支
    # （最终由 _execute_skill 中的 INQUIRE_SKILL_PATTERNS 返回格式化的技能列表，而非执行）
    INQUIRE_SKILL_KEYWORDS = [
        '你有什么技能', '有哪些技能', '技能列表', '技能有哪些',
        '你都会什么', '你都有什么', '什么技能', '哪些技能',
        '列出技能', '显示技能', '查看技能', '技能介绍',
        '你的技能', '我的技能', '支持什么技能',
        '你有什么skill', '有什么skill', 'skill列表',
        '你能做什么', '你会什么', '你会啥',
    ]

    @staticmethod
    def _quick_classify(question: str) -> Optional[str]:
        """
        关键词预判断（快速分类）

        分类优先级：
        0. 强chat关键词：你好、介绍下自己等，单个命中即判定为chat（最高优先级）
        1. 强MCP关键词：天气、地图等单个命中即判定为mcp
        2. 强Skill关键词：执行代码、运行脚本等单个命中即判定为skill
        3. 混合意图：有连接词且同时包含knowledge和data关键词（仅knowledge+data）
        4. 单一意图：仅包含一种意图的关键词

        :param question: 用户问题
        :return: 预判的意图类型或None（无法通过关键词判断）
        """
        question_lower = question.lower()

        # 0a. 询问技能列表（最高优先级之一，排在强chat之前）
        # "你有什么技能"、"你能做什么"等，应判定为skill（进入技能展示分支，不执行）
        for keyword in IntentClassifier.INQUIRE_SKILL_KEYWORDS:
            if keyword.lower() in question_lower:
                logger.info(f"关键词预判: skill (询问技能列表命中: {keyword})")
                return "skill"

        # 0b. 强chat关键词检测（最高优先级，不受其他关键词影响）
        # "你好"、"介绍下自己"等明确闲聊表达，即使包含"介绍"等knowledge关键词也优先判定为chat
        for keyword in IntentClassifier.STRONG_CHAT_KEYWORDS:
            if keyword.lower() in question_lower:
                logger.info(f"关键词预判: chat (强关键词命中: {keyword})")
                return "chat"

        # 1. 强MCP关键词检测（最高优先级）
        for keyword in IntentClassifier.STRONG_MCP_KEYWORDS:
            if keyword.lower() in question_lower:
                logger.info(f"关键词预判: mcp (强关键词命中: {keyword})")
                return "mcp"

        # 2. 强Skill关键词检测
        for keyword in IntentClassifier.STRONG_SKILL_KEYWORDS:
            if keyword.lower() in question_lower:
                logger.info(f"关键词预判: skill (强关键词命中: {keyword})")
                return "skill"

        # 3. 检查MCP/Skill普通关键词
        mcp_score = sum(1 for kw in IntentClassifier.MCP_KEYWORDS if kw.lower() in question_lower)
        skill_score = sum(1 for kw in IntentClassifier.SKILL_KEYWORDS if kw.lower() in question_lower)

        # 2个以上MCP普通关键词，判定为mcp
        if mcp_score >= 2 and skill_score == 0:
            logger.info(f"关键词预判: mcp (score={mcp_score})")
            return "mcp"

        # 2个以上Skill普通关键词，判定为skill
        if skill_score >= 2 and mcp_score == 0:
            logger.info(f"关键词预判: skill (score={skill_score})")
            return "skill"

        # 4. 检查data和knowledge关键词
        data_score = sum(1 for kw in IntentClassifier.DATA_KEYWORDS if kw.lower() in question_lower)
        knowledge_score = sum(1 for kw in IntentClassifier.KNOWLEDGE_KEYWORDS if kw.lower() in question_lower)

        # 5. 混合意图：仅当有连接词且同时包含knowledge和data关键词，且无MCP/Skill命中
        hybrid_connectors = ['并且', '同时', '另外', '以及', '还有', '、', ';', '；']
        has_connector = any(c in question for c in hybrid_connectors)

        if has_connector and data_score > 0 and knowledge_score > 0 and mcp_score == 0 and skill_score == 0:
            logger.info(f"关键词预判: hybrid (data={data_score}, knowledge={knowledge_score})")
            return "hybrid"

        # 6. 单一意图判断
        if mcp_score > 0 and data_score == 0 and knowledge_score == 0 and skill_score == 0:
            logger.info(f"关键词预判: mcp (score={mcp_score})")
            return "mcp"

        if skill_score > 0 and data_score == 0 and knowledge_score == 0 and mcp_score == 0:
            logger.info(f"关键词预判: skill (score={skill_score})")
            return "skill"

        if data_score > 0 and mcp_score == 0 and knowledge_score == 0 and skill_score == 0:
            logger.info(f"关键词预判: data (score={data_score})")
            return "data"

        if knowledge_score > 0 and mcp_score == 0 and data_score == 0 and skill_score == 0:
            logger.info(f"关键词预判: knowledge (score={knowledge_score})")
            return "knowledge"

        # 无法通过关键词判断，返回None让LLM处理
        return None

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """
        从文本中提取关键词（用于工具描述匹配）

        提取策略：
        1. 按标点符号和空格分割为短语
        2. 提取2-6字的中文连续字符片段作为关键词
        3. 过滤停用词

        :param text: 待提取的文本（如工具名称或描述）
        :return: 关键词列表
        """
        if not text:
            return []

        import re

        # 停用词（无实际语义的常见词）
        stop_words = {
            '的', '了', '是', '在', '和', '与', '或', '也', '都', '但',
            '可以', '需要', '使用', '通过', '进行', '以及', '如果', '当',
            '一个', '这个', '那种', '什么', '怎么', '如何', '为', '给',
            '等', '以下', '上述', '当前', '该', '此', '其',
        }

        keywords = set()

        # 按标点符号、空格分割
        segments = re.split(r'[，。；：、,;:\s\n\r（）()\[\]【】「」""\'\"]+', text)

        for seg in segments:
            seg = seg.strip()
            if not seg:
                continue

            # 提取2-6字的中文连续片段
            cn_matches = re.findall(r'[\u4e00-\u9fa5]{2,6}', seg)
            for kw in cn_matches:
                if kw not in stop_words:
                    keywords.add(kw)

            # 提取英文单词（2字母以上）
            en_matches = re.findall(r'[a-zA-Z]{2,}', seg)
            for kw in en_matches:
                if kw.lower() not in stop_words:
                    keywords.add(kw.lower())

        return list(keywords)

    @staticmethod
    async def _tool_based_classify(
        question: str,
        db: AsyncSession,
        tool_config_ids: Optional[List[int]] = None
    ) -> Optional[str]:
        """
        基于工具信息相似度的意图识别

        将用户问题与已配置的MCP/Skill工具的名称和描述进行相似度匹配。
        如果匹配度超过阈值，直接判定为对应意图，补充关键词预判的不足。

        匹配策略：
        1. 工具名称直接匹配（用户问题包含完整工具名称）
        2. 工具名称关键词匹配（工具名称的分词出现在用户问题中）
        3. 工具描述关键词匹配（从描述中提取关键词，计算与用户问题的重叠度）

        :param question: 用户问题
        :param db: 数据库会话
        :param tool_config_ids: 工具配置ID列表
        :return: 意图类型（mcp/skill）或None（未匹配到工具）
        """
        mcp_tools, skill_tools = await IntentClassifier._fetch_tool_descriptions(db, tool_config_ids)

        question_lower = question.lower()

        # --- MCP工具匹配 ---
        for tool in mcp_tools:
            name = (tool.get("name") or "").lower()
            desc = tool.get("description") or ""

            # 1. 工具名称直接匹配
            if name and len(name) >= 2 and name in question_lower:
                logger.info(f"工具相似度匹配: mcp (工具名 '{tool['name']}' 直接命中)")
                return "mcp"

            # 2. 工具名称关键词匹配
            if name:
                name_keywords = IntentClassifier._extract_keywords(tool.get("name") or "")
                matched = [kw for kw in name_keywords if kw in question_lower]
                if len(matched) >= 1 and len(matched) / max(len(name_keywords), 1) >= 0.5:
                    logger.info(f"工具相似度匹配: mcp (工具名 '{tool['name']}' 关键词命中: {matched})")
                    return "mcp"

            # 3. 工具描述关键词匹配
            if desc:
                desc_keywords = IntentClassifier._extract_keywords(desc)
                matched = [kw for kw in desc_keywords if kw in question_lower]
                # 描述关键词匹配阈值：至少命中2个，或命中率≥30%
                if len(matched) >= 2 and len(matched) / max(len(desc_keywords), 1) >= 0.3:
                    logger.info(f"工具相似度匹配: mcp (工具 '{tool['name']}' 描述匹配 {len(matched)} 个关键词: {matched})")
                    return "mcp"

        # --- Skill工具匹配 ---
        # P1改造修复：详细排查日志（定位Skill名称匹配失败问题）
        logger.info(f"[Skill排查] _tool_based_classify: skill_tools数量={len(skill_tools)}, 问题={question[:50]!r}")
        for idx, tool in enumerate(skill_tools):
            logger.info(f"[Skill排查] skill_tools[{idx}] name={tool.get('name')!r}")
        for tool in skill_tools:
            name = (tool.get("name") or "").lower()
            desc = tool.get("description") or ""

            # 1. 工具名称直接匹配（用户问题包含完整工具名称）
            if name and len(name) >= 2 and name in question_lower:
                logger.info(f"工具相似度匹配: skill (工具名 '{tool['name']}' 直接命中)")
                return "skill"
            else:
                logger.debug(f"[Skill排查] Skill '{tool.get('name')}' 名称未直接命中: name={name!r}, question_lower={question_lower!r}")

            # 1.5 反向匹配：用户问题是 Skill 名称的简写
            # 处理"产品营销文案"是"产品营销文案创作"的简写等场景
            # 限制：用户问题≥4字符且≥Skill名称长度的50%，避免短查询误命中
            if (name and len(name) >= 4 and len(question) >= 4
                    and len(question) >= len(name) * 0.5
                    and question_lower in name):
                logger.info(f"工具相似度匹配: skill (用户问题 '{question}' 是 Skill '{tool['name']}' 的简写)")
                return "skill"

            # 2. 工具名称关键词匹配（要求高命中率，避免普通问题误判）
            if name:
                name_keywords = IntentClassifier._extract_keywords(tool.get("name") or "")
                matched = [kw for kw in name_keywords if kw in question_lower]
                # P2修复：阈值从 0.8 降低到 0.6
                # 原因：Skill 名"产品营销文案创作"提取4个关键词（产品/营销/文案/创作），
                # 用户输入"产品营销文案"命中3个（命中率0.75），原阈值0.8过严不命中。
                # 降低到0.6后，0.75≥0.6 ✓ 能正确命中。
                # 同时要求命中数≥2 且命中关键词总长度≥4字符（避免短词误命中）
                matched_total_len = sum(len(kw) for kw in matched)
                if len(matched) >= 2 and matched_total_len >= 4 and len(matched) / max(len(name_keywords), 1) >= 0.6:
                    logger.info(f"工具相似度匹配: skill (工具名 '{tool['name']}' 关键词命中: {matched}, 命中率={len(matched)}/{len(name_keywords)})")
                    return "skill"

            # 3. 工具描述关键词匹配（不使用描述匹配，避免普通炉况问题被误判为skill）
            # Skill仅通过名称匹配和关键词预判触发，描述匹配过于宽泛

        return None

    @staticmethod
    async def _fetch_tool_descriptions(
        db: AsyncSession,
        tool_config_ids: Optional[List[int]] = None
    ) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
        """
        从数据库获取MCP和Skills工具的名称和描述

        参考工具管理中已配置的MCP/Skills名称与描述，供LLM意图分类使用。

        :param db: 数据库会话
        :param tool_config_ids: 指定的工具配置ID列表，为空时获取全部active工具
        :return: (mcp_tools描述列表, skill_tools描述列表)
                 每个元素为 {"name": ..., "description": ..., "file_name": ...}
        """
        mcp_tools: List[Dict[str, str]] = []
        skill_tools: List[Dict[str, str]] = []

        try:
            if tool_config_ids:
                stmt = select(ToolConfig).where(
                    ToolConfig.id.in_(tool_config_ids) &
                    (ToolConfig.status == 'active')
                )
            else:
                stmt = select(ToolConfig).where(ToolConfig.status == 'active')

            result = await db.execute(stmt)
            tools = list(result.scalars().all())

            for tool in tools:
                info = {
                    "name": tool.name or "",
                    "description": tool.description or "",
                }
                # Skill类型额外附带文件名信息
                if tool.tool_type == "skill" and tool.skill_file_name:
                    info["file_name"] = tool.skill_file_name

                if tool.tool_type == "mcp":
                    mcp_tools.append(info)
                elif tool.tool_type == "skill":
                    skill_tools.append(info)
        except Exception as e:
            logger.warning(f"获取工具描述失败: {e}")

        return mcp_tools, skill_tools

    @staticmethod
    async def classify(
        question: str,
        db: Optional[AsyncSession] = None,
        tool_config_ids: Optional[List[int]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        """
        意图分类

        分类优先级（从高到低）：
        0. 上下文感知：检测到Skill交互上下文时，保持skill意图（多轮对话支持）
        1. 关键词快速预判：强关键词命中即返回
        2. 工具相似度匹配：用户问题与已配置MCP/Skill工具的名称、描述进行相似度匹配
        3. LLM深度分类：对复杂问题进行语义理解（参考工具名称和描述）

        :param question: 用户问题
        :param db: 数据库会话（用于获取工具描述，可选）
        :param tool_config_ids: 工具配置ID列表（可选，限定工具范围）
        :param history: 对话历史（用于上下文感知，检测Skill多轮交互）
        :return: 意图类型（knowledge/data/mcp/skill/hybrid/chat）
        """
        # 0. 上下文感知：检测Skill交互上下文，保持skill意图
        # 当上一轮assistant回复表明正在进行Skill交互（如"请提供以上信息"），
        # 且当前问题不包含强MCP/chat关键词时，直接保持skill意图，避免多轮对话被误判
        if history and len(history) > 0:
            logger.debug(f"上下文感知: history长度={len(history)}, 消息角色={[m.get('role') for m in history]}")
            last_assistant_msg = None
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg.get("content", "")
                    break

            if last_assistant_msg:
                # P1改造修复：详细排查日志（定位Skill多轮交互识别失败问题）
                logger.info(
                    f"[Skill排查] last_assistant_msg前100字符={last_assistant_msg[:100]!r}, "
                    f"后100字符={last_assistant_msg[-100:]!r}, 总长={len(last_assistant_msg)}"
                )
                # Skill交互特征词：表明上一轮是Skill执行并等待用户补充信息
                # 覆盖各类Skill的引导回复："请提供/请输入/请发送/请上传/请提交"等
                skill_context_markers = [
                    # 提供类
                    '请提供以上信息', '请提供以下信息',
                    '请提供产品', '请提供：', '请提供:',
                    '请提供数据', '请提供参数',
                    # 输入类
                    '请输入', '请填写',
                    # 补充类
                    '请补充以下', '请补充相关', '请补充：', '请补充:',
                    # 发送/上传/提交类（高炉炉况诊断等场景）
                    '请发送数据', '请发送', '发送数据',
                    '请上传', '请提交',
                    # 启动诊断/分析类（高炉炉况诊断等场景）
                    '启动诊断', '启动分析', '开始诊断', '开始分析',
                    # 等待数据
                    '等待您的数据', '等待数据', '等待您',
                    # Skill执行标识
                    'Skill执行', '技能执行',
                ]
                is_skill_context = any(marker in last_assistant_msg for marker in skill_context_markers)
                logger.info(f"[Skill排查] 精确短语匹配 is_skill_context={is_skill_context}")

                # 组合特征检测：同时包含"引导词 + 动作词"或"等待词 + 数据词"
                # 覆盖"请您尽可能完整地补充以下七个维度"等非连续表达
                if not is_skill_context:
                    has_following_kw = any(kw in last_assistant_msg for kw in
                                          ['以下', '维度', '上述', '如下', '下面'])
                    has_action_kw = any(kw in last_assistant_msg for kw in
                                        ['提供', '补充', '填写', '输入', '完善',
                                         '发送', '上传', '提交', '粘贴'])
                    if has_following_kw and has_action_kw:
                        is_skill_context = True
                        logger.info("Skill上下文保持: 组合特征命中（引导词 + 动作词）")
                    else:
                        logger.info(f"[Skill排查] 组合1未命中: following={has_following_kw}, action={has_action_kw}")

                # 扩展组合特征：等待类引导（如"将立刻为您启动诊断"）
                if not is_skill_context:
                    has_wait_kw = any(kw in last_assistant_msg for kw in
                                      ['将立刻', '将立即', '将马上', '为您启动', '马上启动',
                                       '我将', '我会', '等待', '收到后'])
                    has_data_kw = any(kw in last_assistant_msg for kw in
                                      ['数据', '诊断', '分析', '信息', '参数', '指标'])
                    if has_wait_kw and has_data_kw:
                        is_skill_context = True
                        logger.info("Skill上下文保持: 组合特征命中（等待词 + 数据词）")
                    else:
                        logger.info(f"[Skill排查] 组合2未命中: wait={has_wait_kw}, data={has_data_kw}")

                if is_skill_context:
                    # 当检测到Skill交互上下文时，只检查明确的"结束性"关键词
                    # （用户说"再见"、"拜拜"等可能想结束Skill交互）
                    # 不检查'hi'等短关键词，避免JSON数据/技术文档中的子串误匹配中断Skill交互
                    # 也不检查强MCP关键词，避免工业术语（如"预警"、"定位"等）误判导致中断Skill交互
                    question_lower = question.lower()
                    # 明确结束性关键词：只有这些才能中断Skill交互
                    skill_end_keywords = ['再见', '拜拜', '结束', '退出', '不玩了', '算了']
                    has_end_keyword = any(kw in question for kw in skill_end_keywords)
                    # P1改造修复：详细排查日志
                    if has_end_keyword:
                        logger.info(f"[Skill排查] 用户明确结束Skill交互，命中结束关键词")
                        # 不返回 skill，继续走后续分类流程
                    else:
                        # P2管控修复v2：精确区分"参数数据输入"与"自然语言查询"
                        # 上一轮Skill引导后，用户可能：
                        #   a) 补充参数数据（JSON/多行key=value）→ 保持skill
                        #   b) 转为数据查询（"展示2024年9月..."）→ 应走NL2SQL，不能保持skill
                        #   c) 转为知识咨询（"那压差怎么调整？"）→ 应走RAG，不能保持skill
                        stripped_q = question.strip()

                        # ===== 特征1：参数数据输入（严格判定，避免误判自然语言查询）=====
                        # 1a. JSON 格式（最严格的"数据输入"特征）
                        is_json = stripped_q.startswith('{') or stripped_q.startswith('[')
                        # 1b. 多行 key=value 参数列表（要求多个"="或多个换行+冒号+数字，排除自然语言单冒号）
                        line_count = question.count('\n') + 1
                        has_multiple_kv = (
                            (question.count('=') >= 2 or (line_count >= 3 and question.count(':') >= 3))
                            and any(c.isdigit() for c in question)
                        )
                        # 1c. 高密度数字（短文本含多个数字，且非自然语言问句特征）
                        #     排除含年份/月份+查询动词的长文本（如"展示2024年9月..."）
                        digit_count = sum(1 for c in question if c.isdigit())
                        is_data_dense = digit_count >= 8 and len(question) < 200
                        # 1d. Markdown 结构化素材（产品/文案/介绍类 Skill 输入）
                        #     检测是否包含标题标记、列表标记、分隔线等 Markdown 特征
                        has_md_heading = bool(re.search(r'#{1,6}\s+\S', question))
                        has_md_list = bool(re.search(r'^[\s]*[-*+]\s+', question, re.MULTILINE))
                        has_md_separator = bool(re.search(r'^[\s]*-{3,}', question, re.MULTILINE))
                        # 产品/文案/营销类关键词（Skill 素材输入特征）
                        skill_content_kw = ['产品', '文案', '营销', '素材', '介绍', '撰写', '撰写文案',
                                           '生成文案', '宣传', '推广', '定位', '卖点', '目标用户',
                                           '客户评价', '价格', '行动号召', 'CTA']
                        skill_content_hits = [kw for kw in skill_content_kw if kw in question]
                        has_skill_content = len(skill_content_hits) > 0
                        # 判断是否为 Skill 素材输入（Markdown 结构化 + Skill 关键词）
                        is_skill_content = (has_md_heading or has_md_list or has_md_separator) and has_skill_content
                        is_data_input = is_json or has_multiple_kv or is_data_dense or is_skill_content

                        # ===== 特征2：自然语言查询/咨询特征（出现即视为非"参数数据"）=====
                        # 2a. 数据查询动词/图表词（NL2SQL意图的强信号）
                        has_data_query_kw = any(kw in question for kw in [
                            '展示', '查询', '统计', '列出', '报表', '图表', '趋势',
                            '对比', '汇总', '排名', '多少', '数量', '次数', '产量',
                            '折线图', '柱状图', '饼图', '表格', '平均值', '合计',
                        ])
                        # 2b. 时间词（数据查询的常见伴随特征，如"2024年9月"）
                        #     注意：单独"年"字可能误命中"2-3年"等描述性内容，
                        #     故要求与数据查询动词共现才算时间词
                        has_time_kw_alone = any(kw in question for kw in [
                            '年', '月', '日', '上周', '本周', '上月', '本月', '上年度', '本年度',
                        ])
                        has_time_kw = has_time_kw_alone and has_data_query_kw
                        # 2c. 知识咨询词（RAG意图的强信号）
                        #     注意：单独"解释"可能误命中"可追溯可解释"等描述性内容，
                        #     故要求与疑问词共现才算咨询词
                        has_consult_question = any(kw in question for kw in [
                            '如何', '怎么', '为什么', '是什么', '什么是', '怎样',
                        ])
                        has_consult_other = any(kw in question for kw in [
                            '应该', '原理', '说明', '定义', '概念',
                            '规范', '标准', '制度', '规程', '操作',
                        ])
                        has_consult_kw = has_consult_question or has_consult_other

                        # ===== 判定：仅当含"参数数据"特征且不含任何"自然语言"特征时才保持 skill =====
                        has_natural_lang_feature = (
                            has_data_query_kw or has_time_kw or has_consult_kw
                        )
                        # P2修复：当 is_skill_content=True（Markdown结构+Skill关键词）且
                        # Skill 内容关键词命中≥2个时，直接保持 skill，不检查自然语言特征。
                        # 原因：用户提供的详细产品素材（如产品名称/定位/卖点/客户评价）
                        # 可能含"年"（2-3年）、"解释"（可追溯可解释）等描述性词，
                        # 这些不是数据查询或知识咨询信号，不应破坏 Skill 上下文保持。
                        if is_skill_content and len(skill_content_hits) >= 2:
                            logger.info(
                                f"意图分类完成(Skill上下文保持-素材强匹配): "
                                f"问题={question[:30]}..., 意图=skill, "
                                f"命中关键词={skill_content_hits}"
                            )
                            return "skill"
                        if is_data_input and not has_natural_lang_feature:
                            logger.info(f"意图分类完成(Skill上下文保持-数据输入): 问题={question[:30]}..., 意图=skill")
                            return "skill"
                        else:
                            logger.info(
                                f"[Skill排查] 上下文命中但当前为自然语言查询/咨询，回到正常分类: "
                                f"is_data_input={is_data_input}(json={is_json},kv={has_multiple_kv},dense={is_data_dense},skill_content={is_skill_content}), "
                                f"data_query={has_data_query_kw}, time={has_time_kw}(alone={has_time_kw_alone}), consult={has_consult_kw}"
                            )
                            # 不返回 skill，继续走关键词预判/LLM 分类
            else:
                logger.warning(f"[Skill排查] history非空但未找到assistant消息, history角色={[m.get('role') for m in history]}")
        else:
            logger.info(f"[Skill排查] history为空或长度0, history={history}, 无法检测Skill上下文")

        # 1. 关键词预判断（快速路径）
        quick_result = IntentClassifier._quick_classify(question)
        if quick_result:
            logger.info(f"意图分类完成(关键词预判): 问题={question[:30]}..., 意图={quick_result}")
            return quick_result

        # 1.5 动态 Skill 名称强匹配（在工具相似度匹配之前）
        # P2修复：用户直接说出 Skill 名称（如"产品营销文案"）时，STRONG_SKILL_KEYWORDS 未覆盖
        # 此时若 _tool_based_classify 的反向匹配仍未命中（如 Skill 名是其他变体），
        # 会走到 LLM 分类被误判为 knowledge。这里主动加载所有 Skill 名作为强关键词，
        # 双向子串匹配 + 长度约束，确保用户输入 Skill 名时立即判定为 skill 意图。
        if db is not None:
            try:
                _, skill_tools_for_match = await IntentClassifier._fetch_tool_descriptions(db, tool_config_ids)
                q_lower = question.lower()
                for tool in skill_tools_for_match:
                    name = (tool.get("name") or "").lower()
                    if not name or len(name) < 2:
                        continue
                    # 双向匹配：用户问题完整包含 Skill 名 OR Skill 名包含用户问题（简写）
                    # 长度约束：用户问题≥4字符，且≥Skill名长度的40%，避免短查询误命中
                    if name in q_lower:
                        logger.info(f"意图分类完成(Skill名称强匹配): Skill '{tool['name']}' 被完整包含, 意图=skill")
                        return "skill"
                    if (len(question) >= 4 and len(question) >= len(name) * 0.4
                            and q_lower in name):
                        logger.info(f"意图分类完成(Skill名称简写匹配): 用户'{question}' 是 Skill '{tool['name']}' 的简写, 意图=skill")
                        return "skill"
            except Exception as e:
                logger.warning(f"Skill名称动态强匹配失败: {e}")

        # 2. 工具相似度匹配（中间路径，基于已配置工具的名称和描述）
        if db is not None:
            tool_result = await IntentClassifier._tool_based_classify(question, db, tool_config_ids)
            if tool_result:
                logger.info(f"意图分类完成(工具相似度匹配): 问题={question[:30]}..., 意图={tool_result}")
                return tool_result

        # 3. 获取工具描述（用于增强LLM分类）
        mcp_tools_desc: List[Dict[str, str]] = []
        skill_tools_desc: List[Dict[str, str]] = []
        if db is not None:
            mcp_tools_desc, skill_tools_desc = await IntentClassifier._fetch_tool_descriptions(db, tool_config_ids)

        # 4. LLM深度分类（复杂路径，参考工具名称和描述）
        # P0改造：传入 history，让 LLM 分类时能看到对话历史，识别延续性意图
        # 例如：上一轮"展示2023年8月数据" + 当前"那9月呢" → 正确分类为 data
        intent = await llm_service.classify_intent(
            question=question,
            mcp_tools=mcp_tools_desc,
            skill_tools=skill_tools_desc,
            history=history,
        )
        logger.info(f"意图分类完成(LLM): 问题={question[:30]}..., 意图={intent}")
        return intent

    @staticmethod
    async def split_hybrid_question(question: str) -> Tuple[str, str]:
        """
        将混合问题拆分为数据子问题和知识子问题

        对于hybrid类型的问题，将其拆分为两个独立的子问题，
        分别路由到数据查询通道和知识问答通道。

        :param question: 用户原始混合问题
        :return: (数据子问题, 知识子问题)

        拆分逻辑：
            1. 使用LLM将混合问题拆分为数据部分和知识部分
            2. 解析LLM返回的格式（"数据问题：xxx" 和 "知识问题：xxx"）
            3. 如果拆分失败，使用原问题作为两个子问题
        """
        prompt = f"""请将以下混合问题拆分为两部分：数据查询部分和知识问答部分。

用户问题：{question}

拆分规则（非常重要）：
1. 数据问题：提取涉及"展示"、"查询"、"统计"、"图表"等数据查询需求的部分
   - 必须从原问题中逐字提取，不要添加、修改或补充任何原问题中没有的内容
   - 不要将知识问答部分的上下文混入数据问题
   - 必须完整保留所有时间范围信息（如"2023年8月"、"2025年9月第一周"等）
   - 必须完整保留所有查询条件和统计要求
   - 示例："使用折线图展示2023年8月的每日吹炼次数" 是正确的数据问题
   - 错误示例："使用折线图展示" 或 "2023年8月的每日吹炼次数"（不完整）
   - 错误示例：将知识部分的"炉况打分"等术语混入数据问题
2. 知识问题：提取涉及"如何"、"应该"、"解释"、"什么是"、"原理"、"调整"等知识问答需求的部分
   - 保留完整的问题上下文

请按以下格式返回，每行一个：
数据问题：xxx
知识问题：xxx

如果某部分不存在，则留空。只返回结果，不要解释。

示例1（数据在前）：
用户问题："使用折线图展示2023年8月的每日吹炼次数；当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?"
拆分结果：
数据问题：使用折线图展示2023年8月的每日吹炼次数
知识问题：当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?

示例2（数据在后）：
用户问题："当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?使用折线图展示2023年8月的每日吹炼次数"
拆分结果：
数据问题：使用折线图展示2023年8月的每日吹炼次数
知识问题：当前压差不稳，炉料质量不是很好，应该如何调整以减少炉况波动?
"""

        result = await llm_service.chat(prompt)
        logger.info(f"混合问题拆分结果: {result[:50]}...")

        data_question = ""
        knowledge_question = ""

        # 解析LLM返回的格式
        for line in result.strip().split("\n"):
            line = line.strip()
            if line.startswith("数据问题：") or line.startswith("数据问题:"):
                data_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()
            elif line.startswith("知识问题：") or line.startswith("知识问题:"):
                knowledge_question = line.split("：", 1)[-1].split(":", 1)[-1].strip()

        # 如果拆分失败，使用原问题作为两个子问题
        if not data_question and not knowledge_question:
            logger.warning(f"混合问题拆分失败，使用原问题: {question[:30]}...")
            data_question = question
            knowledge_question = question

        logger.info(f"拆分完成: 数据问题={data_question[:30]}..., 知识问题={knowledge_question[:30]}...")
        return data_question, knowledge_question


class RouterService:
    """
    路由分发服务

    根据用户问题的意图分类结果，将请求分发到对应处理通道。
    支持五种路由模式：
    1. 知识问答通道（knowledge意图）：调用knowledge_qa_service
    2. 数据查询通道（data意图）：调用chatbi_service
    3. MCP工具调用通道（mcp意图）：调用mcp_client_service
    4. Skill工具调用通道（skill意图）：基于Skill配置生成响应
    5. 混合分析通道（hybrid意图）：并行调用知识+数据通道，融合结果

    返回值统一格式：(回答内容, 知识引用, SQL溯源, 查询耗时, 数据结果, 字段元信息, 推荐图表类型)
    """

    @staticmethod
    async def _filter_tool_ids_by_type(
        db: AsyncSession,
        tool_config_ids: Optional[List[int]],
        tool_type: str
    ) -> List[int]:
        """
        根据工具类型筛选工具配置ID

        :param db: 数据库会话
        :param tool_config_ids: 原始工具配置ID列表
        :param tool_type: 工具类型（mcp/skill）
        :return: 符合类型的工具配置ID列表
        """
        if not tool_config_ids:
            return []
        try:
            stmt = select(ToolConfig.id).where(
                ToolConfig.id.in_(tool_config_ids) &
                (ToolConfig.tool_type == tool_type) &
                (ToolConfig.status == 'active')
            )
            result = await db.execute(stmt)
            return [row[0] for row in result.all()]
        except Exception as e:
            logger.warning(f"筛选工具ID失败: {e}")
            return []

    @staticmethod
    async def _execute_skill(
        db: AsyncSession,
        tool_config_ids: List[int],
        question: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
        llm_config: Optional[Dict[str, any]] = None,
    ) -> Dict:
        """
        执行Skill工具调用

        参考工具管理中Skill的名称、描述和文件信息，使用LLM分析用户问题
        并基于Skill配置生成响应。

        :param db: 数据库会话
        :param tool_config_ids: 工具配置ID列表（将自动筛选skill类型）
        :param question: 用户问题
        :param system_prompt: 系统提示词
        :param history: 对话历史（多轮对话上下文）
        :param llm_config: 应用级LLM配置（base_url, api_key, model 等）
        :return: 工具调用结果，包含 answer, tool_calls, tool_results 等
        """
        result = {
            "answer": "",
            "tool_calls": [],
            "tool_results": [],
            "success": True
        }

        # 筛选skill类型的工具
        skill_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "skill")

        if not skill_ids:
            result["answer"] = "抱歉，当前应用未配置Skills工具。请先在应用设置中添加Skills工具。"
            result["success"] = False
            return result

        # 加载Skill工具信息
        try:
            stmt = select(ToolConfig).where(
                ToolConfig.id.in_(skill_ids) &
                (ToolConfig.status == 'active')
            )
            tool_result = await db.execute(stmt)
            skills = list(tool_result.scalars().all())
        except Exception as e:
            logger.error(f"加载Skill工具失败: {e}")
            result["answer"] = f"加载Skill工具失败: {str(e)}"
            result["success"] = False
            return result

        if not skills:
            result["answer"] = "抱歉，未找到可用的Skill工具。"
            result["success"] = False
            return result

        # 构建Skill描述信息
        skills_description = []
        for skill in skills:
            desc = {
                "name": skill.name,
                "description": skill.description or "",
                "file_name": skill.skill_file_name or "",
            }
            skills_description.append(desc)

        # ---------- 检测用户是"询问技能列表"还是"要求执行技能" ----------
        # 询问类表达：用户想了解有哪些技能，而非执行某个技能
        INQUIRE_SKILL_PATTERNS = [
            '你有什么技能', '有哪些技能', '技能列表', '技能有哪些',
            '你都会什么', '你都有什么', '你能做什么', '你会什么', '你会啥',
            '有什么技能', '什么技能', '哪些技能',
            '列出技能', '显示技能', '查看技能', '技能介绍',
            '你的技能', '支持什么技能',
            '你有什么skill', '有什么skill', 'skill列表',
        ]
        question_lower = question.strip().lower()
        # P1改造修复：详细排查日志（定位INQUIRE_SKILL_PATTERNS误判问题）
        logger.info(f"[Skill排查] _execute_skill入口: question={question[:50]!r}, question_lower={question_lower!r}")
        # 1. 模式直接匹配
        is_inquire = any(p in question_lower for p in INQUIRE_SKILL_PATTERNS)
        if is_inquire:
            matched_patterns = [p for p in INQUIRE_SKILL_PATTERNS if p in question_lower]
            logger.info(f"[Skill排查] INQUIRE_SKILL_PATTERNS直接命中: {matched_patterns}")
            # P1改造修复：直接匹配命中后，检查用户问题是否完整包含某个Skill名称
            # 如果包含Skill名称（如"高炉炉况诊断是什么技能"包含"高炉炉况诊断"），
            # 说明用户想了解该Skill的使用方式，应执行Skill而非返回技能列表
            question_contains_skill_name = any(
                (s.name or "").lower() in question_lower
                for s in skills
                if s.name and len(s.name) >= 2
            )
            if question_contains_skill_name:
                is_inquire = False
                logger.info(f"INQUIRE_SKILL_PATTERNS直接命中，但问题完整包含Skill名称，视为要求执行Skill而非询问列表")
        # 2. 反向兜底检测：问题包含"技能/skill"且包含疑问词（什么/哪些/介绍/列表等），词序不限
        if not is_inquire:
            has_skill_kw = any(kw in question_lower for kw in ['技能', 'skill'])
            has_question_kw = any(kw in question_lower for kw in
                                  ['什么', '哪些', '介绍', '列表', '查看', '列出', '显示', '支持'])
            if has_skill_kw and has_question_kw:
                # P1改造修复：用户问题包含"技能"+"什么"，但同时完整包含某个Skill名称时，
                # 说明用户想执行该Skill（询问使用方式/参数等），不应视为"询问技能列表"
                # 例如："高炉炉况诊断技能的使用方式是什么？" → 包含"高炉炉况诊断"Skill名称 → 执行Skill
                question_contains_skill_name = any(
                    (s.name or "").lower() in question_lower
                    for s in skills
                    if s.name and len(s.name) >= 2
                )
                if question_contains_skill_name:
                    logger.info(f"询问技能兜底检测命中，但问题完整包含Skill名称，视为要求执行Skill而非询问列表")
                else:
                    is_inquire = True
                    logger.info(f"询问技能兜底判定：问题包含技能+疑问词 -> 视为技能列表询问")
            else:
                logger.info(f"[Skill排查] INQUIRE_SKILL_PATTERNS未命中: has_skill_kw={has_skill_kw}, has_question_kw={has_question_kw}")

        if is_inquire:
            # 用户在询问技能列表，返回展示信息而非执行
            logger.info(f"用户询问技能列表，展示 {len(skills)} 个可用Skill")

            skill_lines = []
            for idx, s in enumerate(skills_description, 1):
                name = s["name"]
                desc = s["description"]
                skill_lines.append(f"**{idx}. {name}**\n   {desc}")

            answer_text = f"我目前拥有以下 **{len(skills)} 个技能**：\n\n"
            answer_text += "\n\n".join(skill_lines)
            answer_text += "\n\n---\n"
            answer_text += "💡 **使用方式**：直接说出技能名称（如「高炉炉况诊断」）即可触发对应技能。"
            result["answer"] = answer_text
            result["success"] = True
            # 记录工具调用信息（仅展示，未执行）
            for s in skills_description:
                result["tool_calls"].append({
                    "tool_name": s["name"],
                    "arguments": {"action": "list"}
                })
                result["tool_results"].append({
                    "tool_name": s["name"],
                    "success": True,
                    "result": "技能展示（未执行）",
                })
            return result

        # ---------- 用户要求执行技能，调用 Skill 执行引擎 ----------
        from app.services.skill_executor_service import skill_executor_service

        # ========== 0. Skill多轮交互上下文保持 ==========
        # 当上一轮assistant回复包含"请提供以下信息"等Skill交互特征词时，
        # 说明正在进行的Skill多轮交互，应保持上一轮的Skill，不重新智能匹配
        # 否则用户提供的输入数据（可能包含其他Skill的关键词如"高炉"、"诊断"）会导致错误匹配
        if history and len(history) > 0:
            last_assistant_msg = None
            for msg in reversed(history):
                if msg.get("role") == "assistant":
                    last_assistant_msg = msg.get("content", "")
                    break

            if last_assistant_msg:
                # Skill交互特征词检测：放宽匹配规则，支持各类Skill的引导回复
                # 1) 精确短语匹配（原逻辑保留，命中即判定）
                # 覆盖"请提供/请输入/请发送/请上传/请提交"等各类引导表达
                skill_context_markers = [
                    # 提供类
                    '请提供以上信息', '请提供以下信息',
                    '请提供产品', '请提供：', '请提供:',
                    '请提供数据', '请提供参数',
                    # 输入类
                    '请输入', '请填写',
                    # 补充类
                    '请补充以下', '请补充相关', '请补充：', '请补充:',
                    # 发送/上传/提交类（高炉炉况诊断等场景）
                    '请发送数据', '请发送', '发送数据',
                    '请上传', '请提交',
                    # 启动诊断/分析类（高炉炉况诊断等场景）
                    '启动诊断', '启动分析', '开始诊断', '开始分析',
                    # 等待数据
                    '等待您的数据', '等待数据', '等待您',
                    # Skill执行标识
                    'Skill执行', '技能执行',
                ]
                is_skill_context = any(marker in last_assistant_msg for marker in skill_context_markers)

                # 2) 组合特征检测：同时包含"引导词 + 动作词"
                #    覆盖"请您尽可能完整地补充以下七个维度的信息"这类非连续表达
                if not is_skill_context:
                    has_following_kw = any(kw in last_assistant_msg for kw in
                                          ['以下', '维度', '上述', '如下', '下面'])
                    has_action_kw = any(kw in last_assistant_msg for kw in
                                        ['提供', '补充', '填写', '输入', '完善',
                                         '发送', '上传', '提交', '粘贴'])
                    if has_following_kw and has_action_kw:
                        is_skill_context = True
                        logger.info("Skill上下文保持: 组合特征命中（引导词 + 动作词）")

                # 3) 扩展组合特征：等待类引导（如"将立刻为您启动诊断"）
                if not is_skill_context:
                    has_wait_kw = any(kw in last_assistant_msg for kw in
                                      ['将立刻', '将立即', '将马上', '为您启动', '马上启动',
                                       '我将', '我会', '等待', '收到后'])
                    has_data_kw = any(kw in last_assistant_msg for kw in
                                      ['数据', '诊断', '分析', '信息', '参数', '指标'])
                    if has_wait_kw and has_data_kw:
                        is_skill_context = True
                        logger.info("Skill上下文保持: 组合特征命中（等待词 + 数据词）")

                if is_skill_context:
                    # P2修复：优先检测当前问题是否完整包含某个 Skill 名称
                    # 若用户明确输入了另一个 Skill 的名称（如"高炉炉况诊断"），
                    # 说明想切换到该 Skill，应跳过上下文保持，走智能匹配选择正确的 Skill
                    # 否则会错误地保持上一轮的 Skill（如"产品营销文案"）
                    question_lower_check = question.lower()
                    switch_skill = None
                    for skill in skills:
                        s_name = (skill.name or "").lower()
                        if s_name and len(s_name) >= 2 and s_name in question_lower_check:
                            switch_skill = skill
                            break
                    if switch_skill:
                        logger.info(
                            f"Skill上下文保持被覆盖：用户问题完整包含Skill名称 '{switch_skill.name}'，"
                            f"跳过上下文保持，走智能匹配选择该 Skill"
                        )
                        # 不 return，落到下方智能匹配逻辑（智能匹配会优先选择名称完全匹配的 Skill）
                    else:
                        # 从上一轮assistant消息内容中匹配Skill名称
                        # 回答1通常包含Skill相关的关键词（如"产品营销文案"）
                        last_msg_lower = last_assistant_msg.lower()
                        for skill in skills:
                            s_name = (skill.name or "").lower()
                            # Skill名称或核心关键词出现在上一轮回复中
                            if s_name and len(s_name) >= 2 and s_name in last_msg_lower:
                                logger.info(f"Skill上下文保持: 上一轮回复包含Skill名称 '{skill.name}'，直接使用")
                                result["tool_calls"].append({
                                    "tool_name": skill.name,
                                    "arguments": {"question": question}
                                })
                                try:
                                    skill_zip_path = resolve_skill_path(skill.skill_file_path)
                                    logger.info(f"开始执行Skill [{skill.name}]（上下文保持），文件: {skill_zip_path}")
                                    exec_result = await skill_executor_service.execute_skill(
                                        zip_path=skill_zip_path,
                                        skill_name=skill.name,
                                        skill_description=skill.description or "",
                                        question=question,
                                        history=history,
                                        llm_config=llm_config,
                                    )
                                    result["answer"] = exec_result.get("answer", "Skill执行未返回结果")
                                    result["success"] = exec_result.get("success", False)
                                    result["tool_results"].append({
                                        "tool_name": skill.name,
                                        "success": exec_result.get("success", False),
                                        "result": exec_result.get("answer", ""),
                                        "skill_files": exec_result.get("skill_files", []),
                                    })
                                    logger.info(f"Skill [{skill.name}] 执行完成（上下文保持）: success={result['success']}")
                                except Exception as e:
                                    logger.error(f"Skill调用分析异常(上下文保持): {type(e).__name__}: {e}", exc_info=True)
                                    result["answer"] = f"抱歉，Skill工具调用过程中出现错误：{type(e).__name__}: {str(e)}"
                                    result["success"] = False
                                return result

                        # 如果名称未直接匹配，尝试用名称关键词匹配上一轮回复
                        for skill in skills:
                            name_keywords = IntentClassifier._extract_keywords(skill.name or "")
                            if name_keywords:
                                matched_in_last = [kw for kw in name_keywords if kw.lower() in last_msg_lower]
                                if len(matched_in_last) / max(len(name_keywords), 1) >= 0.5:
                                    logger.info(f"Skill上下文保持: 上一轮回复匹配Skill '{skill.name}' 关键词 {matched_in_last}，直接使用")
                                    result["tool_calls"].append({
                                        "tool_name": skill.name,
                                        "arguments": {"question": question}
                                    })
                                    try:
                                        skill_zip_path = resolve_skill_path(skill.skill_file_path)
                                        exec_result = await skill_executor_service.execute_skill(
                                            zip_path=skill_zip_path,
                                            skill_name=skill.name,
                                            skill_description=skill.description or "",
                                            question=question,
                                            history=history,
                                            llm_config=llm_config,
                                        )
                                        result["answer"] = exec_result.get("answer", "Skill执行未返回结果")
                                        result["success"] = exec_result.get("success", False)
                                        result["tool_results"].append({
                                            "tool_name": skill.name,
                                            "success": exec_result.get("success", False),
                                            "result": exec_result.get("answer", ""),
                                            "skill_files": exec_result.get("skill_files", []),
                                        })
                                        logger.info(f"Skill [{skill.name}] 执行完成（关键词上下文保持）: success={result['success']}")
                                    except Exception as e:
                                        logger.error(f"Skill调用分析异常(关键词上下文保持): {type(e).__name__}: {e}", exc_info=True)
                                        result["answer"] = f"抱歉，Skill工具调用过程中出现错误：{type(e).__name__}: {str(e)}"
                                        result["success"] = False
                                    return result

                        logger.warning("检测到Skill交互上下文但无法匹配到具体Skill，回退到智能匹配")

        # ========== 根据用户问题智能匹配最合适的 Skill ==========
        # 优先级：1. 名称完全包含 > 2. 名称关键词匹配 > 3. 描述关键词匹配
        question_lower = question.lower()

        # 记录每个Skill的匹配分数和信息，用于排序选择
        skill_scores: List[Dict[str, any]] = []
        for idx, skill in enumerate(skills):
            s_name = (skill.name or "").lower()
            s_desc = (skill.description or "").lower()
            s_file = (skill.skill_file_name or "").lower()
            score = 0.0
            matched_reasons = []
            name_keywords: List[str] = []
            desc_keywords: List[str] = []

            # 1. 用户问题完整包含Skill名称（最高优先级）
            if s_name and len(s_name) >= 2 and s_name in question_lower:
                score += 100
                matched_reasons.append(f"名称完全匹配: {skill.name}")

            # 2. Skill文件名（去掉时间戳后的skill名）包含在问题中
            if s_file:
                file_match = re.search(r'skill_\d+_(.+?)\.zip', s_file)
                if file_match:
                    core_name = file_match.group(1).replace('-', '').replace('_', '')
                    if core_name and core_name in question_lower.replace(' ', ''):
                        score += 80
                        matched_reasons.append(f"文件名核心匹配: {core_name}")

            # 3. 名称关键词匹配（≥80%命中率）
            if s_name:
                name_keywords = IntentClassifier._extract_keywords(skill.name or "")
                matched_kw = [kw for kw in name_keywords if kw in question_lower]
                if len(name_keywords) > 0:
                    ratio = len(matched_kw) / len(name_keywords)
                    if len(matched_kw) >= 2 and ratio >= 0.8:
                        score += 60 * ratio
                        matched_reasons.append(f"名称关键词命中: {matched_kw}")
                    elif len(matched_kw) >= 1 and ratio >= 0.5:
                        score += 30 * ratio
                        matched_reasons.append(f"名称关键词部分命中: {matched_kw}")

            # 4. 描述关键词匹配（≥2个命中或≥30%命中率，中等权重避免误判）
            if s_desc:
                desc_keywords = IntentClassifier._extract_keywords(skill.description or "")
                matched_desc_kw = [kw for kw in desc_keywords if kw in question_lower]
                if len(desc_keywords) > 0:
                    ratio = len(matched_desc_kw) / len(desc_keywords)
                    if len(matched_desc_kw) >= 2 and ratio >= 0.3:
                        score += 40 * ratio
                        matched_reasons.append(f"描述关键词命中: {matched_desc_kw}")

            # 5. 单个强关键词命中（小幅度加分，作为兜底）
            strong_terms = set(name_keywords + desc_keywords)
            for term in strong_terms:
                if len(term) >= 2 and term in question_lower:
                    score += 5
                    found_in_reasons = False
                    for r in matched_reasons:
                        if term in r:
                            found_in_reasons = True
                            break
                    if not found_in_reasons:
                        matched_reasons.append(f"强关键词: {term}")

            # 排序打破平局：按原列表顺序（保持稳定性）
            tiebreak = -idx * 0.001
            skill_scores.append({
                "skill": skill,
                "score": score + tiebreak,
                "reasons": matched_reasons,
            })

        # 按匹配分数降序排序，选择最高分的 Skill
        skill_scores.sort(key=lambda x: x["score"], reverse=True)
        best = skill_scores[0]
        skill = best["skill"]

        if best["reasons"]:
            logger.info(f"Skill智能匹配: 选择 '{skill.name}' (得分={best['score']:.2f})，原因: {'; '.join(best['reasons'])}")
        else:
            logger.warning(f"Skill匹配无明显特征，默认选择: '{skill.name}' (得分={best['score']:.2f})")

        # 记录工具调用信息（只记录最终选中的Skill，避免混淆）
        result["tool_calls"].append({
            "tool_name": skill.name,
            "arguments": {"question": question}
        })

        try:
            skill_zip_path = resolve_skill_path(skill.skill_file_path)
            logger.info(f"开始执行Skill [{skill.name}]，文件: {skill_zip_path}")

            exec_result = await skill_executor_service.execute_skill(
                zip_path=skill_zip_path,
                skill_name=skill.name,
                skill_description=skill.description or "",
                question=question,
                history=history,
                llm_config=llm_config,
            )

            result["answer"] = exec_result.get("answer", "Skill执行未返回结果")
            result["success"] = exec_result.get("success", False)

            # 记录工具执行结果
            result["tool_results"].append({
                "tool_name": skill.name,
                "success": exec_result.get("success", False),
                "result": exec_result.get("answer", ""),
                "skill_files": exec_result.get("skill_files", []),
            })

            logger.info(f"Skill [{skill.name}] 执行完成: success={result['success']}")
        except Exception as e:
            logger.error(f"Skill调用分析异常: {type(e).__name__}: {e}", exc_info=True)
            result["answer"] = f"抱歉，Skill工具调用过程中出现错误：{type(e).__name__}: {str(e)}"
            result["success"] = False

        return result

    @staticmethod
    async def route(
        db: AsyncSession,
        question: str,
        knowledge_base_id: Optional[int] = None,
        datasource_id: Optional[int] = None,
        tool_config_ids: Optional[List[int]] = None,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
        llm_config: Optional[Dict[str, any]] = None,
    ) -> Tuple[str, List[dict], List[dict], float, Optional[List[dict]], Optional[List[dict]], Optional[str]]:
        """
        路由分发

        根据用户问题的意图分类结果，将请求分发到对应处理通道。

        :param db: 数据库会话
        :param question: 用户问题
        :param knowledge_base_id: 知识库ID（可选，知识问答时使用）
        :param datasource_id: 数据源ID（可选，数据查询时使用）
        :param tool_config_ids: 工具配置ID列表（可选，MCP/Skill工具调用时使用）
        :param history: 对话历史（多轮对话上下文，格式 [{"role": "user/assistant", "content": "..."}]）
        :param system_prompt: 应用系统提示词（约束LLM行为，闲聊时使用）
        :param llm_config: 应用级LLM配置（base_url, api_key, model 等），Skill执行时使用
        :return: (回答内容, 知识引用, SQL溯源, 查询耗时, 数据结果, 字段元信息, 推荐图表类型)

        路由逻辑：
            1. 调用IntentClassifier进行意图分类（传入db和tool_config_ids以获取工具描述）
            2. 根据意图类型分发到对应通道：
               - knowledge: 调用knowledge_qa_service进行知识问答
               - data: 调用chatbi_service进行数据查询
               - mcp: 调用mcp_client_service进行MCP工具调用
               - skill: 调用_execute_skill进行Skill工具调用
               - hybrid: 并行调用知识+数据通道，融合结果
            3. 各通道均传入history，使LLM能理解多轮对话上下文
            4. 返回统一格式的结果
        """
        start_time = time.time()
        logger.info(f"开始路由分发: 问题={question[:50]}...")

        # 1. 意图分类（传入db和tool_config_ids以便获取工具描述，传入history用于上下文感知）
        intent = await IntentClassifier.classify(question, db, tool_config_ids, history=history)
        logger.info(f"意图分类结果: {intent}")

        # 初始化返回变量
        references: List[dict] = []
        sql_traces: List[dict] = []
        answer = ""
        data_result = None
        column_meta = None
        chart_type = None

        try:
            if intent == "chat":
                # 闲聊/问候/自我介绍通道
                logger.info("路由到闲聊对话通道")
                # 闲聊回答受应用系统提示词约束，未配置时使用默认提示词
                chat_system_prompt = system_prompt or "你是一个智能助手。请用友好、专业的语气回答用户的问题。如果用户是在问候或自我介绍，请简要介绍你的能力范围。"
                answer = await llm_service.chat(question, system_prompt=chat_system_prompt, history=history, config=llm_config)
                logger.info(f"闲聊对话完成: 回答长度={len(answer)}")

            elif intent == "knowledge":
                # 知识问答通道
                logger.info("路由到知识问答通道")
                if knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=question,
                            topK=5,
                        )
                        answer, refs, query_time = await knowledge_qa_service.answer(db, query, kb, history=history)
                        references = [ref.model_dump() for ref in refs]
                        logger.info(f"知识问答完成: 引用数={len(references)}")
                    else:
                        answer = "抱歉，指定的知识库不存在。"
                        logger.warning(f"知识库不存在: ID={knowledge_base_id}")
                else:
                    answer = "请先选择知识库进行知识问答。"
                    logger.warning("未指定知识库，无法进行知识问答")

            elif intent == "data":
                # 数据查询通道
                logger.info("路由到数据查询通道")
                explanation, results, traces, query_time, _, column_meta, chart_type = await chatbi_service.query(
                    db, question, datasource_id, history=history
                )
                answer = explanation
                data_result = results
                sql_traces = traces
                logger.info(f"数据查询完成: 结果数={len(results) if results else 0}")

            elif intent == "mcp":
                # MCP工具调用通道
                logger.info("路由到MCP工具调用通道")
                mcp_tool_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "mcp")
                if mcp_tool_ids:
                    tool_result = await mcp_client_service.execute_tool_calls(
                        db=db,
                        tool_config_ids=mcp_tool_ids,
                        question=question,
                        history=history,
                    )
                    answer = tool_result.get("answer", "MCP工具调用失败")
                    logger.info(f"MCP工具调用完成: 成功={tool_result.get('success')}")
                else:
                    answer = "抱歉，当前应用未配置MCP工具。请先在应用设置中添加MCP工具。"
                    logger.warning("未配置MCP工具，无法进行MCP工具调用")

            elif intent == "skill":
                # Skill工具调用通道
                logger.info("路由到Skill工具调用通道")
                skill_result = await RouterService._execute_skill(
                    db=db,
                    tool_config_ids=tool_config_ids or [],
                    question=question,
                    history=history,
                    llm_config=llm_config,
                )
                answer = skill_result.get("answer", "Skill工具调用失败")
                logger.info(f"Skill工具调用完成: 成功={skill_result.get('success')}")

            elif intent == "hybrid":
                # 混合分析通道：仅包含知识问答+数据查询，先拆分子问题，再分别路由
                logger.info("路由到混合分析通道")
                data_question, knowledge_question = await IntentClassifier.split_hybrid_question(question)

                knowledge_answer = ""
                explanation = ""
                results = None

                # 执行知识问答（使用拆分后的知识子问题）
                if knowledge_question and knowledge_base_id:
                    logger.info("执行混合分析-知识问答部分")
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=knowledge_question,
                            topK=3,
                        )
                        knowledge_answer, refs, _ = await knowledge_qa_service.answer(db, query, kb, history=history)
                        references = [ref.model_dump() for ref in refs]
                        logger.info(f"混合分析-知识问答完成: 引用数={len(references)}")

                # 执行数据查询（使用拆分后的数据子问题）
                if data_question and datasource_id:
                    logger.info("执行混合分析-数据查询部分")
                    explanation, results, traces, _, _, column_meta, chart_type = await chatbi_service.query(
                        db, data_question, datasource_id, history=history
                    )
                    data_result = results
                    sql_traces = traces
                    logger.info(f"混合分析-数据查询完成: 结果数={len(results) if results else 0}")

                # 融合结果（将知识回答和数据分析整合为统一回答）
                parts = []
                if knowledge_answer:
                    parts.append(f"【知识解答】\n{knowledge_answer}")
                if explanation:
                    parts.append(f"【数据分析】\n{explanation}")

                answer = "\n\n".join(parts) if parts else "抱歉，无法找到相关信息或数据。"
                logger.info("混合分析结果融合完成")

            else:
                # Fallback：未知意图，返回友好提示
                answer = "抱歉，无法理解您的问题。请尝试重新描述。"
                logger.warning(f"未知意图: {intent}")

            # 计算总耗时
            query_time = time.time() - start_time
            logger.info(f"路由分发完成: 意图={intent}, 耗时={query_time:.2f}s")

            return answer, references, sql_traces, query_time, data_result, column_meta, chart_type

        except Exception as e:
            logger.error(f"路由分发失败: 问题={question[:30]}..., 错误={e}", exc_info=True)
            return f"处理失败: {str(e)}", [], [], time.time() - start_time, None, None, None


# 服务实例（供其他模块调用）
intent_classifier = IntentClassifier()
router_service = RouterService()
