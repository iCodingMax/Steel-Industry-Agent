"""
对话API
功能：会话管理、消息发送、SSE流式响应
"""
import re
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field, field_validator
import json
import asyncio
import time
from loguru import logger

from app.core.database import get_db_session
from app.models.session import Session, Message
from app.services.session_service import session_service, message_service
from app.services.router_service import router_service
from app.middlewares.exception_handler import success_response, BusinessException
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


class SessionCreate(BaseModel):
    """创建会话请求"""
    title: Optional[str] = Field(None, description="会话标题")


class SessionUpdate(BaseModel):
    """更新会话请求"""
    title: str = Field(..., description="会话标题")


class ChatRequest(BaseModel):
    """对话请求"""
    sessionId: int = Field(..., description="会话ID")
    question: str = Field(..., description="用户问题", min_length=1)
    knowledgeBaseId: Optional[int] = Field(None, description="知识库ID")
    datasourceId: Optional[int] = Field(None, description="数据源ID")
    llmConfigId: Optional[int] = Field(None, description="LLM配置ID")
    toolConfigIds: Optional[List[int]] = Field(None, description="工具配置ID列表(MCP/Skills)")
    
    model_config = {'extra': 'allow'}


class ChatResponse(BaseModel):
    """对话响应"""
    messageId: int
    content: str
    intent: str
    references: List[dict]
    sqlTraces: List[dict]
    queryTime: int
    data: Optional[List[dict]] = None
    columnMeta: Optional[List[dict]] = None
    chartType: Optional[str] = None
    needsClarification: bool = False  # S3：True=本条回复为澄清追问（会话已挂起awaiting_input）


@router.get("", summary="获取会话列表")
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取用户的会话列表"""
    sessions = await session_service.get_by_user(db, user.id, skip, limit)
    return success_response(data=[s.to_dict() for s in sessions])


@router.post("", summary="创建会话")
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新会话"""
    session = await session_service.create(db, user.id, data.title)
    return success_response(data=session.to_dict())


@router.get("/{session_id}", summary="获取会话详情")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取会话详情"""
    session = await session_service.get_by_id(db, session_id)
    if not session:
        return success_response(data=None, message="会话不存在")

    # 获取消息列表
    messages = await message_service.get_by_session(db, session_id)
    session_dict = session.to_dict()
    session_dict["messages"] = [m.to_dict() for m in messages]

    return success_response(data=session_dict)


@router.put("/{session_id}", summary="更新会话")
async def update_session(
    session_id: int,
    data: SessionUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新会话标题"""
    session = await session_service.update_title(db, session_id, data.title)
    return success_response(data=session.to_dict())


@router.delete("/{session_id}", summary="删除会话")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除会话"""
    await session_service.delete(db, session_id)
    return success_response(message="删除成功")


@router.get("/{session_id}/messages", summary="获取会话消息")
async def list_messages(
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取会话的消息列表"""
    messages = await message_service.get_by_session(db, session_id, skip, limit)
    return success_response(data=[m.to_dict() for m in messages])


@router.post("/send", summary="发送消息")
async def send_message(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """发送消息并获取回复"""
    # 检查会话是否存在
    session = await session_service.get_by_id(db, data.sessionId)
    if not session:
        raise BusinessException(code=404, message="会话不存在")

    # 保存用户消息
    user_msg = await message_service.create(
        db,
        session_id=data.sessionId,
        role="user",
        content=data.question,
    )

    # 获取工具配置ID列表
    tool_config_ids = data.toolConfigIds or []

    # 加载应用配置（工具配置ID回退 + agent模式分流判断）
    app_obj = None
    if hasattr(session, 'application_id') and session.application_id:
        from app.models.application import Application
        app_result = await db.execute(
            select(Application).where(Application.id == session.application_id)
        )
        app_obj = app_result.scalar_one_or_none()
        if app_obj and app_obj.tool_config_ids:
            tool_config_ids = app_obj.tool_config_ids

    # P3-8：主通道绑定回退（与 embed_chat 同款语义）
    # 请求参数为空时回退到应用绑定的第一个知识库/数据源；显式传参优先（保留会话级临时切换能力）
    if not data.knowledgeBaseId and app_obj is not None and app_obj.knowledge_base_ids:
        data.knowledgeBaseId = app_obj.knowledge_base_ids[0]
    if not data.datasourceId and app_obj is not None and app_obj.datasource_ids:
        data.datasourceId = app_obj.datasource_ids[0]

    # 获取对话历史
    chat_history: List[Dict[str, str]] = await message_service.get_history(db, data.sessionId)

    # agent模式分流：应用配置为agent模式时走MasterAgent ReAct循环
    _agent_needs_clarification = False  # S3挂起标志（仅agent分支置True）
    if app_obj is not None and getattr(app_obj, 'agent_mode', 'classic') == 'agent':
        from app.services.master_agent_service import master_agent_service
        # S3挂起恢复：会话处于awaiting_input时，将用户补充与原始问题合并后继续处理
        # P2-10：try_resume 返回 (合并问题, 累计追问次数)，次数透传给 MasterAgent
        effective_question = data.question
        _clarify_count = 0
        resumed = await session_service.try_resume_awaiting(db, session, data.question)
        if resumed:
            effective_question, _clarify_count = resumed
            logger.info(
                f"[send_message] 恢复挂起会话，已合并用户补充与原始问题，"
                f"累计追问次数={_clarify_count}"
            )
        # M3：传入session_id/user_id激活三层记忆（中期摘要+长期记忆隔离）
        agent_result = await master_agent_service.run(
            db, app_obj, effective_question, history=chat_history,
            session_id=data.sessionId, user_id=user.id,
            clarify_count=_clarify_count,
        )
        answer, references, sql_traces, query_time, data_result, column_meta, chart_type = agent_result.to_route_tuple()
        response_intent = "agent"
        _agent_needs_clarification = agent_result.needs_clarification
    else:
        # 调用路由分发（传入多轮对话历史）
        # P3-6：传入应用类型做意图白名单拦截（agent 分流已在上方处理，此处必为 classic/chatbi）
        answer, references, sql_traces, query_time, data_result, column_meta, chart_type = await router_service.route(
            db,
            data.question,
            data.knowledgeBaseId,
            data.datasourceId,
            tool_config_ids,
            history=chat_history,
            agent_mode=getattr(app_obj, 'agent_mode', None) if app_obj is not None else None,
        )
        # M4改造：hybrid通道已下线，存量会话intent兜底改为knowledge
        response_intent = session.intent_type or "knowledge"

    # 保存AI回复
    ai_msg = await message_service.create(
        db,
        session_id=data.sessionId,
        role="assistant",
        content=answer,
        intent=response_intent,
        references=references,
        sql_traces=sql_traces,
        data_result=data_result,
        column_meta=column_meta,
        chart_type=chart_type,
        query_time=int(query_time * 1000),
    )

    # S3挂起：agent模式触发clarify追问时，将会话置为awaiting_input
    # （用户下次回复时由try_resume_awaiting合并原始问题恢复执行）
    if _agent_needs_clarification:
        # P2-10：透传恢复链路的累计追问基数；达到硬上限时拒绝挂起，
        # 追问文本已作为最终回答返回，会话保持active（下次输入按新问题处理）
        _suspended = await session_service.set_awaiting_input(
            db, session,
            question=agent_result.clarify_question,
            original_question=effective_question,
            message_id=ai_msg.id,
            clarify_base=_clarify_count,
        )
        if not _suspended:
            # 拒绝挂起：不再提示前端"继续追问"，按普通回答收尾
            _agent_needs_clarification = False

    response = ChatResponse(
        messageId=ai_msg.id,
        content=answer,
        intent=response_intent,
        references=references,
        sqlTraces=sql_traces,
        queryTime=int(query_time * 1000),
        data=data_result,
        columnMeta=column_meta,
        chartType=chart_type,
        needsClarification=_agent_needs_clarification,
    )

    return success_response(data=response)


@router.post("/stream", summary="流式对话")
async def stream_chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
):
    """SSE流式对话"""
    logger.debug(f"收到流式对话请求: {data.dict()}")
    async def generate():
        """生成SSE流"""
        db = None
        stream_start_time = time.time()
        collected_thinking_steps: list = []

        def emit_thinking(step: int, total_steps: int, title: str, description: str):
            """发送思考步骤事件并收集步骤"""
            collected_thinking_steps.append({
                "step": step,
                "total_steps": total_steps,
                "title": title,
                "description": description,
            })
            return f"data: {json.dumps({'type': 'thinking', 'step': step, 'total_steps': total_steps, 'title': title, 'description': description})}\n\n"
        try:
            # 手动创建数据库session，避免依赖注入在yield后关闭session
            from app.core.database import SystemAsyncSession
            db = SystemAsyncSession()
            await db.__aenter__()

            # 初始化data_producer，避免finally块中引用未定义变量
            data_producer: Optional[asyncio.Task] = None

            # 检查会话是否存在
            session = await session_service.get_by_id(db, data.sessionId)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在'})}\n\n"
                return

            # 加载应用配置（获取系统提示词和工具配置）
            app_system_prompt = None
            app_obj = None
            tool_config_ids: List[int] = list(data.toolConfigIds) if data.toolConfigIds else []
            # 预解析应用级LLM配置（从应用配置的model_name查找），供各意图分支使用
            resolved_llm_config_params = None
            if hasattr(session, 'application_id') and session.application_id:
                from app.models.application import Application
                app_result = await db.execute(
                    select(Application).where(Application.id == session.application_id)
                )
                app_obj = app_result.scalar_one_or_none()
                if app_obj:
                    app_system_prompt = app_obj.system_prompt
                    if app_system_prompt:
                        logger.debug(f"加载应用系统提示词，长度={len(app_system_prompt)}")
                    # 从应用配置获取工具配置ID（如果请求中未指定）
                    if not tool_config_ids and app_obj.tool_config_ids:
                        tool_config_ids = list(app_obj.tool_config_ids)

                    # 从应用配置解析LLM配置：优先前端传入的llmConfigId，
                    # 其次根据应用的model_name查找匹配的LLM配置，
                    # 最后回退到系统默认LLM配置
                    from app.services.llm_config_service import llm_config_service as _llm_cfg_svc
                    from app.models.llm_config import LLMConfig as _LLMCfgModel
                    _llm_cfg = None
                    if data.llmConfigId:
                        _llm_cfg = await _llm_cfg_svc.get_by_id(db, data.llmConfigId)
                    if not _llm_cfg and app_obj.model_name:
                        _stmt = select(_LLMCfgModel).where(
                            (_LLMCfgModel.model_name == app_obj.model_name) &
                            (_LLMCfgModel.model_type == 'llm') &
                            (_LLMCfgModel.status == 'active')
                        )
                        _cfg_result = await db.execute(_stmt)
                        _llm_cfg = _cfg_result.scalar_one_or_none()
                        # P2修复：精确匹配不到时，用"前缀匹配"兜底
                        # 例：Application.model_name=gemma4:e4b 但 LLMConfig.model_name=gemma4
                        if not _llm_cfg and ':' in app_obj.model_name:
                            _prefix = app_obj.model_name.split(':')[0]
                            logger.warning(
                                f"[应用配置解析] 精确匹配无结果，尝试前缀匹配: "
                                f"应用model_name={app_obj.model_name!r}, prefix={_prefix!r}"
                            )
                            _stmt2 = select(_LLMCfgModel).where(
                                _LLMCfgModel.model_name.ilike(f"{_prefix}%") &
                                (_LLMCfgModel.model_type == 'llm') &
                                (_LLMCfgModel.status == 'active')
                            )
                            _cfg_result2 = await db.execute(_stmt2)
                            _llm_cfg = _cfg_result2.scalar_one_or_none()
                            if _llm_cfg:
                                logger.warning(
                                    f"[应用配置解析] 前缀匹配成功: 使用 LLMConfig model={_llm_cfg.model_name!r} "
                                    f"匹配应用model_name={app_obj.model_name!r}"
                                )
                    if not _llm_cfg:
                        _llm_cfg = await _llm_cfg_svc.get_default_by_model_type(db, 'llm')
                    if _llm_cfg:
                        resolved_llm_config_params = {
                            'base_url': _llm_cfg.base_url.rstrip('/') + ('' if _llm_cfg.base_url.rstrip('/').endswith('/v1') else '/v1'),
                            'api_key': _llm_cfg.api_key or 'not-needed',
                            'model': _llm_cfg.model_name,
                            'max_tokens': _llm_cfg.max_tokens,
                            'temperature': _llm_cfg.temperature,
                            'enable_thinking': _llm_cfg.enable_thinking,
                        }
                    # P2修复：应用级LLM配置解析日志（排查是否正确使用gemma4:e4b）
                    if resolved_llm_config_params:
                        logger.info(
                            f"[应用配置解析] 应用ID={session.application_id}, 应用名={app_obj.name!r}, "
                            f"应用model_name={app_obj.model_name!r}, 请求llmConfigId={data.llmConfigId!r}, "
                            f"解析到LLM配置: model={resolved_llm_config_params.get('model')!r}, "
                            f"base_url={resolved_llm_config_params.get('base_url')}, "
                            f"max_tokens={resolved_llm_config_params.get('max_tokens')}, "
                            f"temperature={resolved_llm_config_params.get('temperature')}"
                        )
                    else:
                        from app.core.config import settings as _settings
                        logger.error(
                            f"[应用配置解析] 应用ID={session.application_id}, 应用名={app_obj.name!r}, "
                            f"应用model_name={app_obj.model_name!r}, 请求llmConfigId={data.llmConfigId!r}, "
                            f"**未解析到任何LLM配置，将使用系统默认模型 {_settings.XINFERENCE_LLM_MODEL!r}**"
                        )

            # P3-8：主通道绑定回退（与 embed_chat 同款语义）
            # 请求参数为空时回退到应用绑定的第一个知识库/数据源；显式传参优先（保留会话级临时切换能力）
            # 注：agent 模式分支不受影响（MasterAgent 自行使用 app_obj 绑定的工具上下文）
            if not data.knowledgeBaseId and app_obj is not None and app_obj.knowledge_base_ids:
                data.knowledgeBaseId = app_obj.knowledge_base_ids[0]
            if not data.datasourceId and app_obj is not None and app_obj.datasource_ids:
                data.datasourceId = app_obj.datasource_ids[0]

            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'sessionId': data.sessionId})}\n\n"

            # 保存用户消息
            user_msg = await message_service.create(
                db,
                session_id=data.sessionId,
                role="user",
                content=data.question,
            )

            yield f"data: {json.dumps({'type': 'user_message', 'messageId': user_msg.id})}\n\n"

            # 加载多轮对话历史（在用户消息保存后，获取之前的历史，不含当前消息）
            chat_history: List[Dict[str, str]] = await message_service.get_history(db, data.sessionId)
            # 注意：get_history会取最近N条消息（含刚保存的user消息），需排除最后一条当前用户消息
            # 使用strip后比较，避免前后空格导致比较失败
            _question_stripped = (data.question or "").strip()
            if chat_history and chat_history[-1].get("content", "").strip() == _question_stripped:
                chat_history = chat_history[:-1]
            logger.info(f"[stream_chat] 当前问题={_question_stripped[:50]}, 历史条数={len(chat_history)}")

            # ==================== agent模式分流（MasterAgent ReAct循环） ====================
            # 应用配置为agent模式时，跳过查询改写与意图分类，由MasterAgent
            # 在工具观察结果驱动下多轮自主决策，SSE事件协议与classic模式保持兼容
            if app_obj is not None and getattr(app_obj, 'agent_mode', 'classic') == 'agent':
                from app.services.master_agent_service import master_agent_service, AgentRunResult

                # S3挂起恢复：会话处于awaiting_input时，将用户补充与原始问题合并后继续处理
                # P2-10：try_resume 返回 (合并问题, 累计追问次数)，次数透传给 run_stream
                effective_question = data.question
                _clarify_count = 0
                resumed = await session_service.try_resume_awaiting(db, session, data.question)
                if resumed:
                    effective_question, _clarify_count = resumed
                    yield emit_thinking(1, 3, '智能体分析', '检测到追问补充，结合原始问题继续处理...')
                    logger.info(
                        f"[stream_chat] 恢复挂起会话，已合并用户补充与原始问题，"
                        f"累计追问次数={_clarify_count}"
                    )

                yield emit_thinking(1, 3, '智能体分析', 'Agent模式：正在分析问题并规划工具调用...')
                yield f"data: {json.dumps({'type': 'intent', 'intent': 'agent'})}\n\n"

                # P3-1：消费 MasterAgent run_stream 原生事件流（astream custom 流），
                # plan/step/reflect/clarify 即时转发（前端步骤条实时推进），
                # 终点 result 事件携带 AgentRunResult，替代 P0-4 哨兵队列模式
                # M3：传入session_id/user_id激活三层记忆（中期摘要+长期记忆用户隔离）
                event_stream = master_agent_service.run_stream(
                    db, app_obj, effective_question,
                    history=chat_history, llm_config=resolved_llm_config_params,
                    session_id=data.sessionId, user_id=user.id,
                    clarify_count=_clarify_count,
                )
                agent_result = None
                try:
                    async for evt in event_stream:
                        evt_type = evt.get("type")
                        if evt_type == "result":
                            # 终点事件：取 AgentRunResult 走统一收尾
                            # （前端协议无 result 事件，不转发）
                            agent_result = evt.get("data")
                            continue
                        if evt_type == "step":
                            # step 事件同步收集 thinking_steps（消息持久化用）
                            _st = evt.get("status")
                            _st_label = {"executing": "执行中", "success": "成功", "failed": "失败"}.get(_st, _st)
                            collected_thinking_steps.append({
                                "step": evt.get("iteration", 1),
                                "total_steps": 3,
                                "title": "工具调用",
                                "description": f"第{evt.get('iteration')}轮调用 {evt.get('tool')}（{_st_label}）",
                            })
                        # 转发事件（plan/step/reflect/clarify，SSE 协议兼容）
                        yield f"data: {json.dumps(evt)}\n\n"
                except GeneratorExit:
                    # 客户端断开SSE：aclose() 关闭内部流（astream 迭代器随上下文
                    # 清理自然取消，无哨兵、无显式 cancel 协议）
                    await event_stream.aclose()
                    raise

                # 异常兜底：result 事件缺失（理论不可达，防御式收尾）
                if agent_result is None:
                    agent_result = AgentRunResult(
                        answer="抱歉，智能体执行过程中发生异常，请稍后重试。",
                        query_time=time.time() - stream_start_time,
                        success=False,
                    )

                # 推送结构化结果（与classic模式事件序列一致）
                if agent_result.references:
                    yield f"data: {json.dumps({'type': 'references', 'data': agent_result.references})}\n\n"
                if agent_result.sql_traces:
                    yield f"data: {json.dumps({'type': 'sql_traces', 'data': agent_result.sql_traces})}\n\n"
                if agent_result.data_result:
                    yield f"data: {json.dumps({'type': 'data_result', 'data': agent_result.data_result, 'columnMeta': agent_result.column_meta, 'chartType': agent_result.chart_type})}\n\n"

                # S3 clarify追问：推送clarify事件（前端渲染追问卡片）+ 挂起会话
                # content事件仍发送追问文本，保证旧前端兼容显示
                if agent_result.needs_clarification:
                    yield f"data: {json.dumps({'type': 'clarify', 'question': agent_result.clarify_question})}\n\n"

                # 推送最终回答
                yield emit_thinking(3, 3, '生成回答', '智能体已完成分析，输出最终回答...')
                # P0-1：answer_streamed=True 时增量已通过 answer_delta 事件下发
                # （前端打字机已渲染完整回答），跳过整段 content 避免重复显示；
                # False（降级/异常回退非流式）时保持整段下发
                if agent_result.answer and not agent_result.answer_streamed:
                    yield f"data: {json.dumps({'type': 'content', 'content': agent_result.answer})}\n\n"

                # 保存AI回复
                ai_msg = await message_service.create(
                    db,
                    session_id=data.sessionId,
                    role="assistant",
                    content=agent_result.answer,
                    intent="agent",
                    references=agent_result.references,
                    sql_traces=agent_result.sql_traces,
                    data_result=agent_result.data_result,
                    column_meta=agent_result.column_meta,
                    chart_type=agent_result.chart_type,
                    thinking_steps=collected_thinking_steps,
                    query_time=int((time.time() - stream_start_time) * 1000),
                )

                # S3挂起：clarify追问将会话置为awaiting_input
                # （用户下次回复时由try_resume_awaiting合并原始问题恢复执行）
                if agent_result.needs_clarification:
                    # P2-10：透传恢复链路的累计追问基数；达到硬上限时拒绝挂起，
                    # 追问文本已作为最终回答返回，会话保持active
                    _suspended = await session_service.set_awaiting_input(
                        db, session,
                        question=agent_result.clarify_question,
                        original_question=effective_question,
                        message_id=ai_msg.id,
                        clarify_base=_clarify_count,
                    )
                    if not _suspended:
                        # 拒绝挂起：clarify 事件已推送，不再重复提示（下次输入按新问题处理）
                        logger.info(
                            f"[stream_chat] 追问次数达硬上限拒绝挂起: session_id={data.sessionId}"
                        )

                # 提交事务 + 结束事件（与classic路径共用收尾协议）
                await db.commit()
                elapsed_time = time.time() - stream_start_time
                yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"
                return

            # P0改造：查询改写（基于历史做指代消解和省略补全）
            # 原始问题已保存到数据库（用户看到的仍是原始输入）
            # 改写后的问题用于意图分类、RAG检索、NL2SQL等后续处理
            # JSON数据保护：如果用户输入是JSON格式（如Skill数据输入），跳过改写避免破坏格式
            # 图表切换保护：如果用户只是切换图表类型（如"改为柱状图"），跳过改写
            #   — 否则 rewrite_query 会把"使用柱状图展示"补全为"使用柱状图展示不同班次的炉况报告结果"，
            #     导致后续图表切换检测正则不再匹配，走了正常查询重新生成SQL
            _is_chart_switch = False
            _chart_switch_pattern = re.compile(
                r'^(?:改为|换成|用|使用|改成|切换为|变更为?)\s*'
                r'(?:表格|柱状图?|条形图?|折线图?|曲线图?|饼图?|'
                r'环形图?|雷达图?|散点图?)\s*(?:展示|显示|呈现|查看)?$'
            )
            if chat_history and _chart_switch_pattern.match((data.question or "").strip()):
                _is_chart_switch = True
                logger.info(f"[stream_chat] 检测到纯图表切换指令，跳过查询改写: {data.question[:50]}")

            if chat_history and not _is_chart_switch:
                from app.services.llm_service import llm_service
                # 检测是否为JSON数据（Skill多轮交互场景，如高炉炉况诊断数据输入）
                _is_json_data = False
                _stripped_q = (data.question or "").strip()
                if _stripped_q.startswith("{") and _stripped_q.endswith("}"):
                    try:
                        import json as _json
                        _json.loads(_stripped_q)
                        _is_json_data = True
                        logger.info("[stream_chat] 检测到JSON数据输入，跳过查询改写避免破坏格式")
                    except Exception:
                        # 不是合法JSON，可能是包含花括号的自然语言，正常改写
                        pass

                if not _is_json_data:
                    effective_question = await llm_service.rewrite_query(data.question, chat_history)
                    if effective_question != data.question:
                        logger.info(
                            f"[stream_chat] 查询改写: 原问题={data.question[:50]}, 改写={effective_question[:50]}"
                        )
                        data.question = effective_question

            # 调用意图分类（传入db和tool_config_ids，以便LLM参考工具管理中的MCP/Skills名称和描述）
            # 传入chat_history用于上下文感知（如Skill多轮交互保持）
            from app.services.router_service import intent_classifier
            # P1改造修复：详细排查日志（定位Skill多轮交互识别失败问题）
            logger.info(
                f"[stream_chat][Skill排查] classify调用前: question前50字符={data.question[:50]!r}, "
                f"chat_history长度={len(chat_history) if chat_history else 0}, "
                f"history角色={[m.get('role') for m in chat_history] if chat_history else []}"
            )
            if chat_history:
                for idx, m in enumerate(chat_history):
                    logger.info(f"[stream_chat][Skill排查] history[{idx}] role={m.get('role')}, content前50字符={m.get('content','')[:50]!r}")
            intent = await intent_classifier.classify(
                data.question, db, tool_config_ids, history=chat_history,
                agent_mode=getattr(app_obj, 'agent_mode', None) if app_obj is not None else None,
            )
            logger.info(f"[stream_chat][Skill排查] classify返回 intent={intent}")

            yield f"data: {json.dumps({'type': 'intent', 'intent': intent})}\n\n"

            # 根据意图执行查询
            if intent == "knowledge":
                # 知识问答流式输出
                yield emit_thinking(1, 3, '查询知识库', '正在检索相关文档知识...')

                from app.services.vector_service import VectorIndexService
                from app.models.knowledge import KnowledgeBase
                from app.schemas.knowledge import KnowledgeQuery

                if data.knowledgeBaseId:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == data.knowledgeBaseId)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=data.knowledgeBaseId,
                            question=data.question,
                            topK=5,
                            scoreThreshold=0.0,
                        )
                        refs = await VectorIndexService.search(db, query, kb)

                        yield emit_thinking(2, 3, '知识匹配完成', f'找到 {len(refs)} 条相关文档，相似度最高 {max([r.score for r in refs]):.2f}' if refs else f'找到 0 条相关文档')

                        # 发送引用信息
                        yield f"data: {json.dumps({'type': 'references', 'data': [r.model_dump() for r in refs]})}\n\n"

                        # 流式生成回答
                        yield emit_thinking(3, 3, '生成回答', '基于知识库内容生成自然语言回答...')

                        from app.services.llm_service import llm_service
                        from app.services.llm_config_service import llm_config_service
                        
                        # 获取LLM配置
                        llm_config = None
                        if data.llmConfigId:
                            llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                        elif session.llm_config_id:
                            llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)
                        
                        # 构建配置参数
                        llm_config_params = None
                        if llm_config:
                            llm_config_params = {
                                'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                                'api_key': llm_config.api_key or 'not-needed',
                                'model': llm_config.model_name,
                                'max_tokens': llm_config.max_tokens,
                                'temperature': llm_config.temperature,
                                'enable_thinking': llm_config.enable_thinking,
                            }
                        context_text = "\n\n".join([f"【文档{i+1}】{ref.content}" for i, ref in enumerate(refs)])
                        prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{data.question}

请提供准确、简洁的回答。"""

                        full_answer = ""
                        async for chunk in llm_service.chat_stream(prompt, app_system_prompt, chat_history, llm_config_params):
                            full_answer += chunk
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                        # 保存AI回复
                        await message_service.create(
                            db,
                            session_id=data.sessionId,
                            role="assistant",
                            content=full_answer,
                            intent="knowledge",
                            references=[r.model_dump() for r in refs],
                            thinking_steps=collected_thinking_steps,
                            query_time=int((time.time() - stream_start_time) * 1000),
                        )

                else:
                    # 没有指定知识库，直接调用LLM回答
                    # P3-5 调试通道建议类型（方案 2.8.4）：stream_chat 为应用调试
                    # 通道（创建者可见），按问题特征给出建议应用类型
                    from app.services.router_service import build_suggested_app_type_hint
                    _kb_hint = build_suggested_app_type_hint(data.question)
                    yield emit_thinking(
                        2, 3, '直接回答',
                        f'未选择知识库，直接回答用户问题...{_kb_hint}' if _kb_hint else '未选择知识库，直接回答用户问题...'
                    )
                    
                    from app.services.llm_service import llm_service
                    from app.services.llm_config_service import llm_config_service
                    
                    # 获取LLM配置
                    llm_config = None
                    if data.llmConfigId:
                        llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                    elif session.llm_config_id:
                        llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)
                    
                    # 构建配置参数
                    llm_config_params = None
                    if llm_config:
                        llm_config_params = {
                            'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                            'api_key': llm_config.api_key or 'not-needed',
                            'model': llm_config.model_name,
                            'max_tokens': llm_config.max_tokens,
                            'temperature': llm_config.temperature,
                            'enable_thinking': llm_config.enable_thinking,
                        }

                    full_answer = ""
                    async for chunk in llm_service.chat_stream(data.question, app_system_prompt, chat_history, llm_config_params):
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    
                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="knowledge",
                        references=[],
                        thinking_steps=collected_thinking_steps,
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "data":
                # 数据查询
                yield emit_thinking(1, 4, '意图分析', '识别用户意图，确定查询策略...')

                from app.services.chatbi_service import chatbi_service

                # ====== 图表切换检测 ======
                # _is_chart_switch 已在 rewrite_query 之前用原始问题检测过
                # 当用户仅要求切换展示形式（如"改为柱状图"、"使用柱状图展示"）时，
                # 直接复用上一轮的SQL和数据结果，只更新图表类型，不重新生成SQL
                if _is_chart_switch and chat_history:
                    # 从数据库取最近一条 intent="data" 的 assistant 消息
                    from sqlalchemy import desc as sql_desc
                    prev_data_stmt = (
                        select(Message)
                        .where(Message.session_id == data.sessionId, Message.role == "assistant", Message.intent == "data")
                        .order_by(sql_desc(Message.id))
                        .limit(1)
                    )
                    prev_data_result = await db.execute(prev_data_stmt)
                    prev_msg = prev_data_result.scalar_one_or_none()

                    if prev_msg and prev_msg.sql_traces and prev_msg.data_result:
                        # 复用上一轮的SQL和数据，只更新图表类型
                        traces = prev_msg.sql_traces
                        results = prev_msg.data_result
                        column_meta = prev_msg.column_meta
                        # 从当前问题匹配新的图表类型
                        chart_type = chatbi_service.suggest_chart_type(data.question)
                        query_time = 0.01
                        explanation = f"已将展示形式切换为{chart_type}，数据与上一轮查询结果一致。"
                        explanation_prompt = None
                        logger.info(
                            f"[图表切换] 检测到仅切换图表类型，复用上一轮SQL和数据，"
                            f"新图表类型={chart_type}, SQL={traces[0].get('sql', '')[:60] if traces else 'N/A'}"
                        )
                    else:
                        _is_chart_switch = False  # 上一轮无数据，降级为正常查询

                if not _is_chart_switch:
                    # P2修复：补传 history 给 chatbi_service，让 NL2SQL 引擎能拿到多轮对话上下文
                    # 否则"那八月呢"这种延续性提问无法正确改写和生成 SQL
                    explanation, results, traces, query_time, explanation_prompt, column_meta, chart_type = await chatbi_service.query(
                        db, data.question, data.datasourceId, history=chat_history
                    )

                yield emit_thinking(2, 4, 'SQL生成', f'成功生成 SQL 查询语句，共 {len(traces)} 条')

                # 发送SQL溯源
                yield f"data: {json.dumps({'type': 'sql_traces', 'data': traces})}\n\n"

                yield emit_thinking(3, 4, '数据查询', f'执行 SQL 查询，返回 {len(results) if results else 0} 条结果')

                # 发送数据结果（含字段元信息和推荐图表类型）
                yield f"data: {json.dumps({'type': 'data_result', 'data': results, 'columnMeta': column_meta, 'chartType': chart_type})}\n\n"

                # 提交事务释放数据库连接
                await db.commit()

                # 使用prompt流式生成解释（真正的流式输出）
                yield emit_thinking(4, 4, '结果分析', '分析查询结果，生成自然语言解释...')

                from app.services.llm_service import llm_service
                from app.services.llm_config_service import llm_config_service

                # 获取LLM配置
                llm_config = None
                if data.llmConfigId:
                    llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                elif session.llm_config_id:
                    llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)
                
                # 构建配置参数
                llm_config_params = None
                if llm_config:
                    llm_config_params = {
                        'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                        'api_key': llm_config.api_key or 'not-needed',
                        'model': llm_config.model_name,
                        'max_tokens': llm_config.max_tokens,
                        'temperature': llm_config.temperature,
                        'enable_thinking': llm_config.enable_thinking,
                    }

                full_explanation = ""
                if explanation_prompt:
                    async for chunk in llm_service.chat_stream(explanation_prompt, app_system_prompt, chat_history, llm_config_params):
                        full_explanation += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                else:
                    full_explanation = explanation
                    yield f"data: {json.dumps({'type': 'content', 'content': explanation})}\n\n"

                # 保存AI回复（commit后查询会自动开启新事务，无需显式begin）
                await message_service.create(
                    db,
                    session_id=data.sessionId,
                    role="assistant",
                    content=full_explanation,
                    intent="data",
                    sql_traces=traces,
                    data_result=results,
                    column_meta=column_meta,
                    chart_type=chart_type,
                    thinking_steps=collected_thinking_steps,
                    query_time=int(query_time * 1000),
                )

            elif intent == "mcp":
                # MCP工具调用模式
                from app.services.mcp_client_service import mcp_client_service
                from app.services.router_service import RouterService

                # 筛选mcp类型的工具ID
                mcp_tool_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "mcp")

                if mcp_tool_ids:
                    total_steps = 4
                    yield emit_thinking(1, total_steps, '意图分析', '识别用户需要调用MCP工具的意图...')

                    yield emit_thinking(2, total_steps, '加载MCP服务', f'加载 {len(mcp_tool_ids)} 个MCP Server配置...')

                    # 加载工具列表
                    mcp_tools = await mcp_client_service.load_mcp_tools(db, mcp_tool_ids)
                    yield emit_thinking(3, total_steps, '调用MCP工具', '调用MCP工具中...')

                    # 执行工具调用
                    tool_result = await mcp_client_service.execute_tool_calls(
                        db=db,
                        tool_config_ids=mcp_tool_ids,
                        question=data.question,
                        system_prompt=app_system_prompt,
                    )

                    # 发送工具调用结果
                    yield f"data: {json.dumps({'type': 'tool_calls', 'data': tool_result.get('tool_calls', [])})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_results', 'data': tool_result.get('tool_results', [])})}\n\n"

                    # 仅显示实际被调用的MCP工具名称（而非所有已配置的MCP工具）
                    actual_mcp_tool_names = '、'.join([
                        call.get('tool_name', '') for call in tool_result.get('tool_calls', [])
                        if call.get('tool_name')
                    ])
                    if actual_mcp_tool_names:
                        yield emit_thinking(4, total_steps, '生成回答',
                                            f'已调用MCP工具"{actual_mcp_tool_names}"，整合结果生成自然语言回答...')
                    else:
                        yield emit_thinking(4, total_steps, '生成回答', '整合MCP工具调用结果，生成自然语言回答...')

                    # 流式输出最终回答
                    full_answer = tool_result.get('answer', 'MCP工具调用失败')
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    # 保存AI回复（包含工具调用信息）
                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="mcp",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=tool_result.get('tool_calls', []),
                        tool_results=tool_result.get('tool_results', []),
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )
                else:
                    full_answer = "抱歉，当前应用未配置MCP工具。请先在应用设置中添加MCP工具。"
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="mcp",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=[],
                        tool_results=[],
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "skill":
                # Skill工具调用模式
                from app.services.router_service import RouterService

                # 直接使用已解析的应用级LLM配置（resolved_llm_config_params）
                # 该配置从应用配置的model_name解析而来，确保Skill执行使用应用选择的模型
                llm_config_params = resolved_llm_config_params
                if llm_config_params:
                    logger.debug(f"Skill执行使用应用级LLM配置: model={llm_config_params.get('model')}")
                else:
                    logger.warning("Skill执行未找到应用级LLM配置，将使用系统默认配置")

                # 筛选skill类型的工具ID
                skill_tool_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "skill")

                if skill_tool_ids:
                    total_steps = 4
                    yield emit_thinking(1, total_steps, '意图分析', '识别用户需要调用Skill工具的意图...')

                    yield emit_thinking(2, total_steps, '加载工具', f'加载 {len(skill_tool_ids)} 个Skill工具配置...')

                    yield emit_thinking(3, total_steps, '工具分析', '执行Skill工具中...')

                    # 执行Skill调用分析（传入应用级LLM配置和对话历史，支持多轮交互）
                    skill_result = await RouterService._execute_skill(
                        db=db,
                        tool_config_ids=skill_tool_ids,
                        question=data.question,
                        system_prompt=app_system_prompt,
                        llm_config=llm_config_params,
                        history=chat_history,
                    )

                    # 发送工具调用结果
                    yield f"data: {json.dumps({'type': 'tool_calls', 'data': skill_result.get('tool_calls', [])})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_results', 'data': skill_result.get('tool_results', [])})}\n\n"

                    # 仅显示实际被调用的Skill工具名称（而非所有已配置的Skill工具）
                    actual_skill_tool_names = '、'.join([
                        call.get('tool_name', '') for call in skill_result.get('tool_calls', [])
                        if call.get('tool_name')
                    ])
                    if actual_skill_tool_names:
                        yield emit_thinking(4, total_steps, '生成回答',
                                            f'已执行Skill工具"{actual_skill_tool_names}"，整合结果生成自然语言回答...')
                    else:
                        yield emit_thinking(4, total_steps, '生成回答', '整合Skill工具分析结果，生成自然语言回答...')

                    # 输出最终回答
                    full_answer = skill_result.get('answer', 'Skill工具调用失败')
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="skill",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=skill_result.get('tool_calls', []),
                        tool_results=skill_result.get('tool_results', []),
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )
                else:
                    full_answer = "抱歉，当前应用未配置Skills工具。请先在应用设置中添加Skills工具。"
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="skill",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=[],
                        tool_results=[],
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "chat":
                # 闲聊/问候/自我介绍通道
                yield emit_thinking(1, 1, '直接回答', '识别为闲聊对话，直接生成回答...')

                from app.services.llm_service import llm_service
                from app.services.llm_config_service import llm_config_service

                # 获取LLM配置
                llm_config = None
                if data.llmConfigId:
                    llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                elif session.llm_config_id:
                    llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)

                # 构建配置参数
                llm_config_params = None
                if llm_config:
                    llm_config_params = {
                        'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                        'api_key': llm_config.api_key or 'not-needed',
                        'model': llm_config.model_name,
                        'max_tokens': llm_config.max_tokens,
                        'temperature': llm_config.temperature,
                        'enable_thinking': llm_config.enable_thinking,
                    }

                # 闲聊回答受应用系统提示词约束，未配置时使用默认提示词
                chat_system_prompt = app_system_prompt or "你是一个智能助手。请用友好、专业的语气回答用户的问题。如果用户是在问候或自我介绍，请简要介绍你的能力范围。"
                # 注：历史嵌入由 llm_service.chat_stream 统一处理，无需在此重复

                full_answer = ""
                async for chunk in llm_service.chat_stream(data.question, chat_system_prompt, chat_history, llm_config_params):
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                # 保存AI回复
                await message_service.create(
                    db,
                    session_id=data.sessionId,
                    role="assistant",
                    content=full_answer,
                    intent="chat",
                    references=[],
                    thinking_steps=collected_thinking_steps,
                    query_time=int((time.time() - stream_start_time) * 1000),
                )

            else:
                # M4改造：hybrid混合通道已下线，未知/存量hybrid意图统一降级走知识问答通道
                from app.services.vector_service import VectorIndexService
                from app.models.knowledge import KnowledgeBase
                from app.schemas.knowledge import KnowledgeQuery

                yield emit_thinking(1, 3, '查询知识库', '正在检索相关文档知识...')

                if data.knowledgeBaseId:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == data.knowledgeBaseId)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=data.knowledgeBaseId,
                            question=data.question,
                            topK=5,
                            scoreThreshold=0.0,
                        )
                        refs = await VectorIndexService.search(db, query, kb)

                        yield emit_thinking(2, 3, '知识匹配完成', f'找到 {len(refs)} 条相关文档，相似度最高 {max([r.score for r in refs]):.2f}' if refs else f'找到 0 条相关文档')

                        # 发送引用信息
                        yield f"data: {json.dumps({'type': 'references', 'data': [r.model_dump() for r in refs]})}\n\n"

                        # 流式生成回答
                        yield emit_thinking(3, 3, '生成回答', '基于知识库内容生成自然语言回答...')

                        from app.services.llm_service import llm_service
                        from app.services.llm_config_service import llm_config_service

                        # 获取LLM配置
                        llm_config = None
                        if data.llmConfigId:
                            llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                        elif session.llm_config_id:
                            llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)

                        # 构建配置参数
                        llm_config_params = None
                        if llm_config:
                            llm_config_params = {
                                'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                                'api_key': llm_config.api_key or 'not-needed',
                                'model': llm_config.model_name,
                                'max_tokens': llm_config.max_tokens,
                                'temperature': llm_config.temperature,
                                'enable_thinking': llm_config.enable_thinking,
                            }

                        context_text = "\n\n".join([f"【文档{i+1}】{ref.content}" for i, ref in enumerate(refs)])
                        prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{data.question}

请提供准确、简洁的回答。"""

                        full_answer = ""
                        async for chunk in llm_service.chat_stream(prompt, app_system_prompt, chat_history, llm_config_params):
                            full_answer += chunk
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                        # 保存AI回复（意图兜底记录为knowledge，便于前端类型解析）
                        await message_service.create(
                            db,
                            session_id=data.sessionId,
                            role="assistant",
                            content=full_answer,
                            intent="knowledge",
                            references=[r.model_dump() for r in refs],
                            thinking_steps=collected_thinking_steps,
                            query_time=int((time.time() - stream_start_time) * 1000),
                        )

                else:
                    # 未指定知识库，直接调用LLM回答
                    # P3-5 调试通道建议类型（方案 2.8.4）：stream_chat 为应用调试
                    # 通道（创建者可见），按问题特征给出建议应用类型
                    from app.services.router_service import build_suggested_app_type_hint
                    _kb_hint = build_suggested_app_type_hint(data.question)
                    yield emit_thinking(
                        2, 3, '直接回答',
                        f'未选择知识库，直接回答用户问题...{_kb_hint}' if _kb_hint else '未选择知识库，直接回答用户问题...'
                    )

                    from app.services.llm_service import llm_service
                    from app.services.llm_config_service import llm_config_service

                    # 获取LLM配置
                    llm_config = None
                    if data.llmConfigId:
                        llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                    elif session.llm_config_id:
                        llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)

                    # 构建配置参数
                    llm_config_params = None
                    if llm_config:
                        llm_config_params = {
                            'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                            'api_key': llm_config.api_key or 'not-needed',
                            'model': llm_config.model_name,
                            'max_tokens': llm_config.max_tokens,
                            'temperature': llm_config.temperature,
                            'enable_thinking': llm_config.enable_thinking,
                        }

                    full_answer = ""
                    async for chunk in llm_service.chat_stream(data.question, app_system_prompt, chat_history, llm_config_params):
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=data.sessionId,
                        role="assistant",
                        content=full_answer,
                        intent="knowledge",
                        references=[],
                        thinking_steps=collected_thinking_steps,
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            # 提交事务
            await db.commit()

            # 发送完成事件（包含耗时）
            elapsed_time = time.time() - stream_start_time
            yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"

        except Exception as e:
            # 回滚事务（如果存在）
            try:
                if db:
                    await db.rollback()
            except Exception:
                pass

            # 异常日志
            logger.error(f"[stream_chat] 流式处理异常: {type(e).__name__}: {e}", exc_info=True)

            # 发送错误事件，但不再 raise——避免流式连接断开导致前端 catch 块覆盖 error 消息
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {str(e)}'})}\n\n"

                # 发送done事件以确保前端正确结束
                elapsed_time = time.time() - stream_start_time
                yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"
            except Exception as yield_err:
                logger.warning(f"[stream_chat] 发送error事件时二次异常: {yield_err}")
        finally:
            if data_producer and not data_producer.done():
                data_producer.cancel()
                try:
                    await data_producer
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            if db:
                await db.__aexit__(None, None, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class EmbedChatRequest(BaseModel):
    """嵌入对话请求"""
    # 兼容前端传入整数类型的sessionId（数据库自增ID），使用validator强制转为字符串
    # 避免因类型不匹配导致422校验错误
    sessionId: str = Field(..., description="会话ID")
    question: str = Field(..., description="用户问题", min_length=1)
    knowledgeBaseId: Optional[int] = Field(None, description="知识库ID")
    datasourceId: Optional[int] = Field(None, description="数据源ID")
    applicationId: Optional[int] = Field(None, description="应用ID")
    llmConfigId: Optional[int] = Field(None, description="LLM配置ID")
    chatUserId: Optional[int] = Field(None, description="对话用户ID，用于数据隔离")
    chatUsername: Optional[str] = Field(None, description="对话用户名，用于数据隔离")

    @field_validator("sessionId")
    @classmethod
    def coerce_session_id_to_str(cls, v):
        """强制将sessionId转为字符串，兼容前端传入整数的情况"""
        if v is None:
            raise ValueError("sessionId不能为空")
        return str(v)


@router.post("/embed/chat", summary="嵌入模式对话")
async def embed_chat(
    data: EmbedChatRequest,
):
    """
    嵌入模式对话API，支持iframe嵌入场景
    无需认证，根据applicationId获取应用配置进行对话
    支持知识问答、智能问数、融合推理三种模式
    """
    async def generate():
        db = None
        stream_start_time = time.time()
        collected_thinking_steps: list = []

        def emit_thinking(step: int, total_steps: int, title: str, description: str):
            """发送思考步骤事件并收集步骤"""
            collected_thinking_steps.append({
                "step": step,
                "total_steps": total_steps,
                "title": title,
                "description": description,
            })
            return f"data: {json.dumps({'type': 'thinking', 'step': step, 'total_steps': total_steps, 'title': title, 'description': description})}\n\n"

        try:
            from app.core.database import SystemAsyncSession
            db = SystemAsyncSession()
            await db.__aenter__()

            # 初始化data_producer，避免finally块中引用未定义变量
            data_producer: Optional[asyncio.Task] = None

            # ==================== 处理会话ID：将字符串sessionId映射为真实数据库session ====================
            # 前端传入的sessionId格式：debug-${appId}-${timestamp}（字符串）
            # 数据库sessions表使用INTEGER自增主键，需要创建真实session或查找对应session
            real_session_id: int = 0
            try:
                # 首先尝试直接转换整数（兼容正常整数会话ID）
                real_session_id = int(data.sessionId)
                # 校验session是否存在
                session = await session_service.get_by_id(db, real_session_id)
                if not session:
                    # 不存在则继续走创建逻辑
                    raise ValueError("session not found")
            except (ValueError, TypeError):
                # 非数字格式（debug模式），需要创建真实数据库会话
                # embed_chat 无需认证，使用系统默认用户创建session满足外键约束
                # 同时通过 chat_user_id 字段记录实际对话用户，实现数据隔离
                from app.models.chat_user import ChatUser
                from app.models.user import User

                embed_user_id: int = 0
                embed_chat_user_id: Optional[int] = None
                embed_title = data.question[:30] if data.question else "嵌入对话"

                # 获取对话用户信息：用于标题展示和 chat_user_id 数据隔离
                if data.chatUserId:
                    chat_user = await db.get(ChatUser, data.chatUserId)
                    if chat_user:
                        embed_chat_user_id = chat_user.id
                        embed_title = f"{chat_user.name or chat_user.username} - {embed_title}"

                # 使用 users 表的默认系统用户创建 session，满足外键约束
                default_user_stmt = select(User).order_by(User.id.asc()).limit(1)
                default_user_result = await db.execute(default_user_stmt)
                default_user = default_user_result.scalar_one_or_none()
                if default_user:
                    embed_user_id = default_user.id
                else:
                    # 极端情况没有用户，抛错
                    raise BusinessException(code=500, message="系统中未创建用户，请先初始化用户")

                # 创建真实数据库会话
                # user_id: 系统用户（满足外键约束）
                # chat_user_id: 对话用户（实现数据隔离，可为空）
                new_session = await session_service.create(
                    db=db,
                    user_id=embed_user_id,
                    chat_user_id=embed_chat_user_id,
                    title=embed_title
                )
                session = new_session
                real_session_id = new_session.id
                logger.info(f"[embed_chat] 创建嵌入会话成功: 前端key={data.sessionId}, 真实session_id={real_session_id}")

            # 发送start事件，带上真实的sessionId（前端如果需要可以更新）
            yield f"data: {json.dumps({'type': 'start', 'sessionId': real_session_id, 'clientSessionId': data.sessionId})}\n\n"

            # 保存用户消息（之前缺失，必须在意图分支之前保存）
            await message_service.create(
                db,
                session_id=real_session_id,
                role="user",
                content=data.question,
            )
            # ==============================================================================================

            # 加载多轮对话历史（排除当前刚保存的用户消息）
            chat_history: List[Dict[str, str]] = await message_service.get_history(db, real_session_id)
            # 使用strip后比较，避免前后空格导致比较失败
            _question_stripped = (data.question or "").strip()
            if chat_history and chat_history[-1].get("content", "").strip() == _question_stripped:
                chat_history = chat_history[:-1]
            logger.info(f"[embed_chat] 当前问题={_question_stripped[:50]}, 历史条数={len(chat_history)}")

            # ==================== 应用配置加载（P2-8：上移至改写之前，供 agent 分流判断） ====================
            knowledge_base_id = data.knowledgeBaseId
            datasource_id = data.datasourceId
            greeting_message = ""

            # 检索参数（从应用配置获取）
            app_score_threshold = 0.0
            app_top_k = 5
            app_system_prompt = None

            # 工具配置ID列表（从应用配置获取）
            tool_config_ids: List[int] = []

            # 预解析LLM配置，供各意图分支使用
            resolved_llm_config_params = None

            # 应用配置对象（agent 分流与意图白名单判断依据）
            app = None
            if data.applicationId:
                from app.models.application import Application
                app_result = await db.execute(
                    select(Application).where(Application.id == data.applicationId)
                )
                app = app_result.scalar_one_or_none()
                if app:
                    greeting_message = app.greeting_message or ""
                    app_system_prompt = app.system_prompt
                    if app_system_prompt:
                        logger.debug(f"加载应用系统提示词，长度={len(app_system_prompt)}")
                    if app.knowledge_base_ids and len(app.knowledge_base_ids) > 0:
                        knowledge_base_id = app.knowledge_base_ids[0]
                    if app.datasource_ids and len(app.datasource_ids) > 0:
                        datasource_id = app.datasource_ids[0]
                    # 从应用配置获取工具配置ID列表
                    if app.tool_config_ids:
                        tool_config_ids = list(app.tool_config_ids)

                    # 从应用配置获取检索参数
                    app_score_threshold = app.score_threshold if app.score_threshold is not None else 0.0
                    app_top_k = app.top_k if app.top_k is not None else 5

                    # 从应用配置解析LLM配置：优先使用前端传入的llmConfigId，
                    # 其次根据应用的model_name查找匹配的LLM配置，
                    # 最后回退到系统默认LLM配置
                    from app.services.llm_config_service import llm_config_service
                    from app.models.llm_config import LLMConfig as LLMConfigModel

                    llm_config = None
                    if data.llmConfigId:
                        llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                    if not llm_config and app.model_name:
                        # 根据应用配置的model_name查找LLM配置
                        stmt = select(LLMConfigModel).where(
                            (LLMConfigModel.model_name == app.model_name) &
                            (LLMConfigModel.model_type == 'llm') &
                            (LLMConfigModel.status == 'active')
                        )
                        cfg_result = await db.execute(stmt)
                        llm_config = cfg_result.scalar_one_or_none()
                        # P2修复：精确匹配不到时，用"前缀匹配"兜底
                        if not llm_config and ':' in app.model_name:
                            _prefix = app.model_name.split(':')[0]
                            logger.warning(
                                f"[嵌入应用配置解析] 精确匹配无结果，尝试前缀匹配: "
                                f"应用model_name={app.model_name!r}, prefix={_prefix!r}"
                            )
                            _stmt2 = select(LLMConfigModel).where(
                                LLMConfigModel.model_name.ilike(f"{_prefix}%") &
                                (LLMConfigModel.model_type == 'llm') &
                                (LLMConfigModel.status == 'active')
                            )
                            _cfg_result2 = await db.execute(_stmt2)
                            llm_config = _cfg_result2.scalar_one_or_none()
                            if llm_config:
                                logger.warning(
                                    f"[嵌入应用配置解析] 前缀匹配成功: 使用 LLMConfig model={llm_config.model_name!r} "
                                    f"匹配应用model_name={app.model_name!r}"
                                )
                    if not llm_config:
                        # 回退到系统默认LLM配置
                        llm_config = await llm_config_service.get_default_by_model_type(db, 'llm')

                    if llm_config:
                        resolved_llm_config_params = {
                            'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                            'api_key': llm_config.api_key or 'not-needed',
                            'model': llm_config.model_name,
                            'max_tokens': llm_config.max_tokens,
                            'temperature': llm_config.temperature,
                            'enable_thinking': llm_config.enable_thinking,
                        }
                    # P2修复：嵌入入口应用级LLM配置解析日志（排查是否正确使用gemma4:e4b）
                    if resolved_llm_config_params:
                        logger.info(
                            f"[嵌入应用配置解析] 应用ID={data.applicationId}, 应用名={app.name!r}, "
                            f"应用model_name={app.model_name!r}, 请求llmConfigId={data.llmConfigId!r}, "
                            f"解析到LLM配置: model={resolved_llm_config_params.get('model')!r}, "
                            f"base_url={resolved_llm_config_params.get('base_url')}, "
                            f"max_tokens={resolved_llm_config_params.get('max_tokens')}, "
                            f"temperature={resolved_llm_config_params.get('temperature')}"
                        )
                    else:
                        from app.core.config import settings as _settings
                        logger.error(
                            f"[嵌入应用配置解析] 应用ID={data.applicationId}, 应用名={app.name!r}, "
                            f"应用model_name={app.model_name!r}, 请求llmConfigId={data.llmConfigId!r}, "
                            f"**未解析到任何LLM配置，将使用系统默认模型 {_settings.XINFERENCE_LLM_MODEL!r}**"
                        )

            # ==================== agent模式分流（P2-8：与主通道 stream_chat 同款语义） ====================
            # 应用配置为 agent 模式时，跳过查询改写与意图分类，由 MasterAgent
            # 在工具观察结果驱动下多轮自主决策；SSE 事件协议与主通道保持一致。
            # 影响场景：应用调试、第三方网页嵌入、浮窗助手（三者均走 embed_chat）
            if app is not None and getattr(app, 'agent_mode', 'classic') == 'agent':
                from app.services.master_agent_service import master_agent_service, AgentRunResult

                # S3挂起恢复：会话处于awaiting_input时，将用户补充与原始问题合并后继续处理
                # P2-10：恢复结果携带累计追问次数，透传给 MasterAgent（≥1 注入禁再追问提示词）
                effective_question = data.question
                _clarify_count = 0
                resumed = await session_service.try_resume_awaiting(db, session, data.question)
                if resumed:
                    effective_question, _clarify_count = resumed
                    yield emit_thinking(1, 3, '智能体分析', '检测到追问补充，结合原始问题继续处理...')
                    logger.info(
                        f"[embed_chat] 恢复挂起会话，已合并用户补充与原始问题，累计追问次数={_clarify_count}"
                    )

                yield emit_thinking(1, 3, '智能体分析', 'Agent模式：正在分析问题并规划工具调用...')
                yield f"data: {json.dumps({'type': 'intent', 'intent': 'agent'})}\n\n"

                # 消费 MasterAgent run_stream 事件流（plan/step/reflect/clarify 即时转发，
                # 终点 result 事件携带 AgentRunResult；GeneratorExit 时 aclose 取消内部流）
                event_stream = master_agent_service.run_stream(
                    db, app, effective_question,
                    history=chat_history, llm_config=resolved_llm_config_params,
                    session_id=real_session_id, user_id=session.user_id,
                    clarify_count=_clarify_count,
                )
                agent_result = None
                try:
                    async for evt in event_stream:
                        evt_type = evt.get("type")
                        if evt_type == "result":
                            # 终点事件：取 AgentRunResult 走统一收尾（前端协议无 result 事件）
                            agent_result = evt.get("data")
                            continue
                        if evt_type == "step":
                            # step 事件同步收集 thinking_steps（消息持久化用）
                            _st = evt.get("status")
                            _st_label = {"executing": "执行中", "success": "成功", "failed": "失败"}.get(_st, _st)
                            collected_thinking_steps.append({
                                "step": evt.get("iteration", 1),
                                "total_steps": 3,
                                "title": "工具调用",
                                "description": f"第{evt.get('iteration')}轮调用 {evt.get('tool')}（{_st_label}）",
                            })
                        # 转发事件（plan/step/reflect/clarify，SSE 协议兼容）
                        yield f"data: {json.dumps(evt)}\n\n"
                except GeneratorExit:
                    # 客户端断开SSE：aclose() 关闭内部流（astream 迭代器随上下文清理自然取消）
                    await event_stream.aclose()
                    raise

                # 异常兜底：result 事件缺失（理论不可达，防御式收尾）
                if agent_result is None:
                    agent_result = AgentRunResult(
                        answer="抱歉，智能体执行过程中发生异常，请稍后重试。",
                        query_time=time.time() - stream_start_time,
                        success=False,
                    )

                # 推送结构化结果（与主通道事件序列一致）
                if agent_result.references:
                    yield f"data: {json.dumps({'type': 'references', 'data': agent_result.references})}\n\n"
                if agent_result.sql_traces:
                    yield f"data: {json.dumps({'type': 'sql_traces', 'data': agent_result.sql_traces})}\n\n"
                if agent_result.data_result:
                    yield f"data: {json.dumps({'type': 'data_result', 'data': agent_result.data_result, 'columnMeta': agent_result.column_meta, 'chartType': agent_result.chart_type})}\n\n"

                # S3 clarify追问：推送clarify事件（前端渲染追问卡片）+ 挂起会话
                if agent_result.needs_clarification:
                    yield f"data: {json.dumps({'type': 'clarify', 'question': agent_result.clarify_question})}\n\n"

                # 推送最终回答
                yield emit_thinking(3, 3, '生成回答', '智能体已完成分析，输出最终回答...')
                # P0-1：answer_streamed=True 时增量已通过 answer_delta 事件下发
                # （前端打字机已渲染完整回答），跳过整段 content 避免重复显示；
                # False（降级/异常回退非流式）时保持整段下发
                if agent_result.answer and not agent_result.answer_streamed:
                    yield f"data: {json.dumps({'type': 'content', 'content': agent_result.answer})}\n\n"

                # 保存AI回复
                ai_msg = await message_service.create(
                    db,
                    session_id=real_session_id,
                    role="assistant",
                    content=agent_result.answer,
                    intent="agent",
                    references=agent_result.references,
                    sql_traces=agent_result.sql_traces,
                    data_result=agent_result.data_result,
                    column_meta=agent_result.column_meta,
                    chart_type=agent_result.chart_type,
                    thinking_steps=collected_thinking_steps,
                    query_time=int((time.time() - stream_start_time) * 1000),
                )

                # S3挂起：clarify追问将会话置为awaiting_input
                if agent_result.needs_clarification:
                    # P2-10：透传恢复链路的累计追问基数；达到硬上限时拒绝挂起，
                    # 追问文本已作为最终回答返回，会话保持active
                    _suspended = await session_service.set_awaiting_input(
                        db, session,
                        question=agent_result.clarify_question,
                        original_question=effective_question,
                        message_id=ai_msg.id,
                        clarify_base=_clarify_count,
                    )
                    if not _suspended:
                        logger.info(
                            f"[embed_chat] 追问次数达硬上限拒绝挂起: session_id={real_session_id}"
                        )

                # 提交事务 + 结束事件（与classic路径共用收尾协议）
                await db.commit()
                elapsed_time = time.time() - stream_start_time
                yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"
                return

            # P0改造：查询改写（基于历史做指代消解和省略补全）
            # 原始问题已保存到数据库（用户看到的仍是原始输入）
            # 改写后的问题用于意图分类、RAG检索、NL2SQL等后续处理
            # JSON数据保护：如果用户输入是JSON格式（如Skill数据输入），跳过改写避免破坏格式
            # 图表切换保护：如果用户只是切换图表类型，跳过改写（同 stream_chat 分支逻辑）
            _is_chart_switch = False
            _chart_switch_pattern = re.compile(
                r'^(?:改为|换成|用|使用|改成|切换为|变更为?)\s*'
                r'(?:表格|柱状图?|条形图?|折线图?|曲线图?|饼图?|'
                r'环形图?|雷达图?|散点图?)\s*(?:展示|显示|呈现|查看)?$'
            )
            if chat_history and _chart_switch_pattern.match((data.question or "").strip()):
                _is_chart_switch = True
                logger.info(f"[embed_chat] 检测到纯图表切换指令，跳过查询改写: {data.question[:50]}")

            if chat_history and not _is_chart_switch:
                from app.services.llm_service import llm_service
                # 检测是否为JSON数据（Skill多轮交互场景，如高炉炉况诊断数据输入）
                _is_json_data = False
                _stripped_q = (data.question or "").strip()
                if _stripped_q.startswith("{") and _stripped_q.endswith("}"):
                    try:
                        import json as _json
                        _json.loads(_stripped_q)
                        _is_json_data = True
                        logger.info("[embed_chat] 检测到JSON数据输入，跳过查询改写避免破坏格式")
                    except Exception:
                        # 不是合法JSON，可能是包含花括号的自然语言，正常改写
                        pass

                if not _is_json_data:
                    effective_question = await llm_service.rewrite_query(data.question, chat_history)
                    if effective_question != data.question:
                        logger.info(
                            f"[embed_chat] 查询改写: 原问题={data.question[:50]}, 改写={effective_question[:50]}"
                        )
                        data.question = effective_question

            # P2-8：应用配置（知识库/数据源回退、检索参数、LLM解析、app对象）
            # 已上移至查询改写之前加载，此处不再重复加载

            from app.services.router_service import intent_classifier
            # P1改造修复：详细排查日志（定位Skill多轮交互识别失败问题）
            logger.info(
                f"[embed_chat][Skill排查] classify调用前: question前50字符={data.question[:50]!r}, "
                f"chat_history长度={len(chat_history) if chat_history else 0}, "
                f"history角色={[m.get('role') for m in chat_history] if chat_history else []}"
            )
            if chat_history:
                for idx, m in enumerate(chat_history):
                    logger.info(f"[embed_chat][Skill排查] history[{idx}] role={m.get('role')}, content前50字符={m.get('content','')[:50]!r}")
            # P3-6：embed_chat 传入应用类型做意图白名单拦截（app 未加载或非 agent 类型时正常透传）
            _embed_agent_mode = None
            if data.applicationId and app is not None:
                _embed_agent_mode = getattr(app, 'agent_mode', None)
            intent = await intent_classifier.classify(
                data.question, db, tool_config_ids, history=chat_history,
                agent_mode=_embed_agent_mode,
            )
            logger.info(f"[embed_chat][Skill排查] classify返回 intent={intent}")

            yield f"data: {json.dumps({'type': 'intent', 'intent': intent})}\n\n"

            if intent == "knowledge":
                # 知识问答流式输出
                yield emit_thinking(1, 3, '查询知识库', '正在检索相关文档知识...')

                from app.services.vector_service import VectorIndexService
                from app.models.knowledge import KnowledgeBase
                from app.schemas.knowledge import KnowledgeQuery

                if knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=data.question,
                            topK=app_top_k,
                            scoreThreshold=app_score_threshold,
                        )
                        refs = await VectorIndexService.search(db, query, kb)

                        yield emit_thinking(2, 3, '知识匹配完成', f'找到 {len(refs)} 条相关文档，相似度最高 {max([r.score for r in refs]):.2f}' if refs else f'找到 0 条相关文档')

                        # 发送引用信息
                        yield f"data: {json.dumps({'type': 'references', 'data': [r.model_dump() for r in refs]})}\n\n"

                        # 流式生成回答
                        yield emit_thinking(3, 3, '生成回答', '基于知识库内容生成自然语言回答...')

                        from app.services.llm_service import llm_service

                        context_text = "\n\n".join([f"【文档{i+1}】{ref.content}" for i, ref in enumerate(refs)])
                        prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{data.question}

请提供准确、简洁的回答。"""

                        full_answer = ""
                        async for chunk in llm_service.chat_stream(prompt, app_system_prompt, chat_history, resolved_llm_config_params):
                            full_answer += chunk
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                        # 保存AI回复（知识问答-带引用）
                        await message_service.create(
                            db,
                            session_id=real_session_id,
                            role="assistant",
                            content=full_answer,
                            intent="knowledge",
                            references=[r.model_dump() for r in refs],
                            thinking_steps=collected_thinking_steps,
                            query_time=int((time.time() - stream_start_time) * 1000),
                        )

                else:
                    # 没有指定知识库，直接调用LLM回答
                    yield emit_thinking(2, 3, '直接回答', '未选择知识库，直接回答用户问题...')

                    from app.services.llm_service import llm_service
                    full_answer = ""
                    async for chunk in llm_service.chat_stream(data.question, app_system_prompt, chat_history):
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 保存AI回复（知识问答-无引用）
                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="knowledge",
                        references=[],
                        thinking_steps=collected_thinking_steps,
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "data":
                # 数据查询
                yield emit_thinking(1, 4, '意图分析', '识别用户意图，确定查询策略...')

                from app.services.chatbi_service import chatbi_service

                # ====== 图表切换检测（_is_chart_switch 已在 rewrite_query 之前检测）======
                if _is_chart_switch and chat_history:
                    from sqlalchemy import desc as sql_desc
                    prev_data_stmt = (
                        select(Message)
                        .where(Message.session_id == real_session_id, Message.role == "assistant", Message.intent == "data")
                        .order_by(sql_desc(Message.id))
                        .limit(1)
                    )
                    prev_data_result = await db.execute(prev_data_stmt)
                    prev_msg = prev_data_result.scalar_one_or_none()

                    if prev_msg and prev_msg.sql_traces and prev_msg.data_result:
                        traces = prev_msg.sql_traces
                        results = prev_msg.data_result
                        column_meta = prev_msg.column_meta
                        chart_type = chatbi_service.suggest_chart_type(data.question)
                        query_time = 0.01
                        explanation = f"已将展示形式切换为{chart_type}，数据与上一轮查询结果一致。"
                        explanation_prompt = None
                        logger.info(
                            f"[图表切换] 检测到仅切换图表类型，复用上一轮SQL和数据，"
                            f"新图表类型={chart_type}, SQL={traces[0].get('sql', '')[:60] if traces else 'N/A'}"
                        )
                    else:
                        _is_chart_switch = False

                if not _is_chart_switch:
                    # P2修复：补传 history，让 NL2SQL 引擎能拿到多轮对话上下文
                    explanation, results, traces, query_time, explanation_prompt, column_meta, chart_type = await chatbi_service.query(
                        db, data.question, datasource_id, history=chat_history
                    )

                yield emit_thinking(2, 4, 'SQL生成', f'成功生成 SQL 查询语句，共 {len(traces)} 条')

                # 发送SQL溯源
                if traces:
                    yield f"data: {json.dumps({'type': 'sql_traces', 'data': traces})}\n\n"

                yield emit_thinking(3, 4, '数据查询', f'执行 SQL 查询，返回 {len(results) if results else 0} 条结果')

                # 发送数据结果（含字段元信息和推荐图表类型）
                if results:
                    yield f"data: {json.dumps({'type': 'data_result', 'data': results, 'columnMeta': column_meta, 'chartType': chart_type})}\n\n"

                # 提交事务释放数据库连接，再调用LLM生成解释
                await db.commit()

                # 使用prompt流式生成解释
                yield emit_thinking(4, 4, '结果分析', '分析查询结果，生成自然语言解释...')

                from app.services.llm_service import llm_service
                full_answer = ""
                if explanation_prompt:
                    async for chunk in llm_service.chat_stream(explanation_prompt, app_system_prompt, chat_history):
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                else:
                    full_answer = explanation
                    yield f"data: {json.dumps({'type': 'content', 'content': explanation})}\n\n"

                # 保存AI回复（数据查询）
                await message_service.create(
                    db,
                    session_id=real_session_id,
                    role="assistant",
                    content=full_answer,
                    intent="data",
                    sql_traces=traces,
                    data_result=results,
                    column_meta=column_meta,
                    chart_type=chart_type,
                    thinking_steps=collected_thinking_steps,
                    query_time=int(query_time * 1000),
                )

            elif intent == "mcp":
                # MCP工具调用模式
                from app.services.mcp_client_service import mcp_client_service
                from app.services.router_service import RouterService

                # 筛选mcp类型的工具ID
                mcp_tool_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "mcp")

                if mcp_tool_ids:
                    total_steps = 4
                    yield emit_thinking(1, total_steps, '意图分析', '识别用户需要调用MCP工具的意图...')

                    yield emit_thinking(2, total_steps, '加载MCP服务', f'加载 {len(mcp_tool_ids)} 个MCP Server配置...')

                    # 加载工具列表
                    mcp_tools = await mcp_client_service.load_mcp_tools(db, mcp_tool_ids)
                    yield emit_thinking(3, total_steps, '调用MCP工具', '调用MCP工具中...')

                    # 执行工具调用
                    tool_result = await mcp_client_service.execute_tool_calls(
                        db=db,
                        tool_config_ids=mcp_tool_ids,
                        question=data.question,
                        system_prompt=app_system_prompt,
                    )

                    # 发送工具调用结果
                    yield f"data: {json.dumps({'type': 'tool_calls', 'data': tool_result.get('tool_calls', [])})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_results', 'data': tool_result.get('tool_results', [])})}\n\n"

                    # 仅显示实际被调用的MCP工具名称（而非所有已配置的MCP工具）
                    actual_mcp_tool_names = '、'.join([
                        call.get('tool_name', '') for call in tool_result.get('tool_calls', [])
                        if call.get('tool_name')
                    ])
                    if actual_mcp_tool_names:
                        yield emit_thinking(4, total_steps, '生成回答',
                                            f'已调用MCP工具"{actual_mcp_tool_names}"，整合结果生成自然语言回答...')
                    else:
                        yield emit_thinking(4, total_steps, '生成回答', '整合MCP工具调用结果，生成自然语言回答...')

                    # 输出最终回答
                    full_answer = tool_result.get('answer', 'MCP工具调用失败')
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="mcp",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=tool_result.get('tool_calls', []),
                        tool_results=tool_result.get('tool_results', []),
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )
                else:
                    full_answer = "抱歉，当前应用未配置MCP工具。请先在应用设置中添加MCP工具。"
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="mcp",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=[],
                        tool_results=[],
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "skill":
                # Skill工具调用模式
                from app.services.router_service import RouterService

                # 直接使用已解析的应用级LLM配置（resolved_llm_config_params）
                # 该配置从应用配置的model_name解析而来，确保Skill执行使用应用选择的模型
                llm_config_params = resolved_llm_config_params
                if llm_config_params:
                    logger.debug(f"Skill执行使用应用级LLM配置: model={llm_config_params.get('model')}")
                else:
                    logger.warning("Skill执行未找到应用级LLM配置，将使用系统默认配置")

                # 筛选skill类型的工具ID
                skill_tool_ids = await RouterService._filter_tool_ids_by_type(db, tool_config_ids, "skill")

                if skill_tool_ids:
                    total_steps = 4
                    yield emit_thinking(1, total_steps, '意图分析', '识别用户需要调用Skill工具的意图...')

                    yield emit_thinking(2, total_steps, '加载工具', f'加载 {len(skill_tool_ids)} 个Skill工具配置...')

                    yield emit_thinking(3, total_steps, '工具分析', '执行Skill工具中...')

                    # 执行Skill调用分析（传入应用级LLM配置和对话历史，支持多轮交互）
                    skill_result = await RouterService._execute_skill(
                        db=db,
                        tool_config_ids=skill_tool_ids,
                        question=data.question,
                        system_prompt=app_system_prompt,
                        llm_config=llm_config_params,
                        history=chat_history,
                    )

                    # 发送工具调用结果
                    yield f"data: {json.dumps({'type': 'tool_calls', 'data': skill_result.get('tool_calls', [])})}\n\n"
                    yield f"data: {json.dumps({'type': 'tool_results', 'data': skill_result.get('tool_results', [])})}\n\n"

                    # 仅显示实际被调用的Skill工具名称（而非所有已配置的Skill工具）
                    actual_skill_tool_names = '、'.join([
                        call.get('tool_name', '') for call in skill_result.get('tool_calls', [])
                        if call.get('tool_name')
                    ])
                    if actual_skill_tool_names:
                        yield emit_thinking(4, total_steps, '生成回答',
                                            f'已执行Skill工具"{actual_skill_tool_names}"，整合结果生成自然语言回答...')
                    else:
                        yield emit_thinking(4, total_steps, '生成回答', '整合Skill工具分析结果，生成自然语言回答...')

                    # 输出最终回答
                    full_answer = skill_result.get('answer', 'Skill工具调用失败')
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="skill",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=skill_result.get('tool_calls', []),
                        tool_results=skill_result.get('tool_results', []),
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )
                else:
                    full_answer = "抱歉，当前应用未配置Skills工具。请先在应用设置中添加Skills工具。"
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="skill",
                        thinking_steps=collected_thinking_steps,
                        tool_calls=[],
                        tool_results=[],
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            elif intent == "chat":
                # 闲聊/问候/自我介绍通道
                yield emit_thinking(1, 1, '直接回答', '识别为闲聊对话，直接生成回答...')

                from app.services.llm_service import llm_service
                from app.services.llm_config_service import llm_config_service

                # 获取LLM配置
                llm_config = None
                if data.llmConfigId:
                    llm_config = await llm_config_service.get_by_id(db, data.llmConfigId)
                elif session.llm_config_id:
                    llm_config = await llm_config_service.get_by_id(db, session.llm_config_id)

                # 构建配置参数
                llm_config_params = None
                if llm_config:
                    llm_config_params = {
                        'base_url': llm_config.base_url.rstrip('/') + ('' if llm_config.base_url.rstrip('/').endswith('/v1') else '/v1'),
                        'api_key': llm_config.api_key or 'not-needed',
                        'model': llm_config.model_name,
                        'max_tokens': llm_config.max_tokens,
                        'temperature': llm_config.temperature,
                        'enable_thinking': llm_config.enable_thinking,
                    }

                # 闲聊回答受应用系统提示词约束，未配置时使用默认提示词
                chat_system_prompt = app_system_prompt or "你是一个智能助手。请用友好、专业的语气回答用户的问题。如果用户是在问候或自我介绍，请简要介绍你的能力范围。"
                # 注：历史嵌入由 llm_service.chat_stream 统一处理，无需在此重复

                full_answer = ""
                async for chunk in llm_service.chat_stream(data.question, chat_system_prompt, chat_history, llm_config_params):
                    full_answer += chunk
                    yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                # 保存AI回复
                await message_service.create(
                    db,
                    session_id=real_session_id,
                    role="assistant",
                    content=full_answer,
                    intent="chat",
                    references=[],
                    thinking_steps=collected_thinking_steps,
                    query_time=int((time.time() - stream_start_time) * 1000),
                )

            else:
                # M4改造：hybrid混合通道已下线，未知/存量hybrid意图统一降级走知识问答通道
                from app.services.vector_service import VectorIndexService
                from app.models.knowledge import KnowledgeBase
                from app.schemas.knowledge import KnowledgeQuery

                yield emit_thinking(1, 3, '查询知识库', '正在检索相关文档知识...')

                if knowledge_base_id:
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_base_id)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()

                    if kb:
                        query = KnowledgeQuery(
                            knowledgeBaseId=knowledge_base_id,
                            question=data.question,
                            topK=app_top_k,
                            scoreThreshold=app_score_threshold,
                        )
                        refs = await VectorIndexService.search(db, query, kb)

                        yield emit_thinking(2, 3, '知识匹配完成', f'找到 {len(refs)} 条相关文档，相似度最高 {max([r.score for r in refs]):.2f}' if refs else f'找到 0 条相关文档')

                        # 发送引用信息
                        yield f"data: {json.dumps({'type': 'references', 'data': [r.model_dump() for r in refs]})}\n\n"

                        # 流式生成回答
                        yield emit_thinking(3, 3, '生成回答', '基于知识库内容生成自然语言回答...')

                        from app.services.llm_service import llm_service

                        context_text = "\n\n".join([f"【文档{i+1}】{ref.content}" for i, ref in enumerate(refs)])
                        prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{data.question}

请提供准确、简洁的回答。"""

                        full_answer = ""
                        async for chunk in llm_service.chat_stream(prompt, app_system_prompt, chat_history, resolved_llm_config_params):
                            full_answer += chunk
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                        # 保存AI回复（意图兜底记录为knowledge，便于前端类型解析）
                        await message_service.create(
                            db,
                            session_id=real_session_id,
                            role="assistant",
                            content=full_answer,
                            intent="knowledge",
                            references=[r.model_dump() for r in refs],
                            thinking_steps=collected_thinking_steps,
                            query_time=int((time.time() - stream_start_time) * 1000),
                        )

                else:
                    # 未指定知识库，直接调用LLM回答
                    yield emit_thinking(2, 3, '直接回答', '未选择知识库，直接回答用户问题...')

                    from app.services.llm_service import llm_service
                    full_answer = ""
                    async for chunk in llm_service.chat_stream(data.question, app_system_prompt, chat_history):
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 保存AI回复
                    await message_service.create(
                        db,
                        session_id=real_session_id,
                        role="assistant",
                        content=full_answer,
                        intent="knowledge",
                        references=[],
                        thinking_steps=collected_thinking_steps,
                        query_time=int((time.time() - stream_start_time) * 1000),
                    )

            await db.commit()

            # 发送完成事件（包含耗时）
            elapsed_time = time.time() - stream_start_time
            yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"

        except Exception as e:
            # 异常时发送 error 事件，但不再 raise——避免流式连接断开导致前端 catch 块覆盖 error 消息
            logger.error(f"[embed_chat] 流式处理异常: {type(e).__name__}: {e}", exc_info=True)
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': f'{type(e).__name__}: {str(e)}'})}\n\n"
                # 发送 done 事件，让前端知道流结束
                elapsed_time = time.time() - stream_start_time
                yield f"data: {json.dumps({'type': 'done', 'elapsed_time': elapsed_time})}\n\n"
            except Exception as yield_err:
                logger.warning(f"[embed_chat] 发送error事件时二次异常: {yield_err}")
        finally:
            if data_producer and not data_producer.done():
                data_producer.cancel()
                try:
                    await data_producer
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass
            if db:
                await db.__aexit__(None, None, None)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )