"""
对话API
功能：会话管理、消息发送、SSE流式响应
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
import json
import asyncio
import time

from app.core.database import get_mysql_session
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


@router.get("", summary="获取会话列表")
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取用户的会话列表"""
    sessions = await session_service.get_by_user(db, user.id, skip, limit)
    return success_response(data=[s.to_dict() for s in sessions])


@router.post("", summary="创建会话")
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """创建新会话"""
    session = await session_service.create(db, user.id, data.title)
    return success_response(data=session.to_dict())


@router.get("/{session_id}", summary="获取会话详情")
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_mysql_session),
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
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """更新会话标题"""
    session = await session_service.update_title(db, session_id, data.title)
    return success_response(data=session.to_dict())


@router.delete("/{session_id}", summary="删除会话")
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_mysql_session),
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
    db: AsyncSession = Depends(get_mysql_session),
    user: User = Depends(get_current_user),
):
    """获取会话的消息列表"""
    messages = await message_service.get_by_session(db, session_id, skip, limit)
    return success_response(data=[m.to_dict() for m in messages])


@router.post("/send", summary="发送消息")
async def send_message(
    data: ChatRequest,
    db: AsyncSession = Depends(get_mysql_session),
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

    # 调用路由分发
    answer, references, sql_traces, query_time, data_result, column_meta, chart_type = await router_service.route(
        db,
        data.question,
        data.knowledgeBaseId,
        data.datasourceId,
    )

    # 保存AI回复
    ai_msg = await message_service.create(
        db,
        session_id=data.sessionId,
        role="assistant",
        content=answer,
        intent=session.intent_type,
        references=references,
        sql_traces=sql_traces,
        data_result=data_result,
        column_meta=column_meta,
        chart_type=chart_type,
        query_time=int(query_time * 1000),
    )

    response = ChatResponse(
        messageId=ai_msg.id,
        content=answer,
        intent=session.intent_type or "hybrid",
        references=references,
        sqlTraces=sql_traces,
        queryTime=int(query_time * 1000),
        data=data_result,
        columnMeta=column_meta,
        chartType=chart_type,
    )

    return success_response(data=response)


@router.post("/stream", summary="流式对话")
async def stream_chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
):
    """SSE流式对话"""
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
            from app.core.database import MySQLAsyncSession
            db = MySQLAsyncSession()
            await db.__aenter__()

            # 检查会话是否存在
            session = await session_service.get_by_id(db, data.sessionId)
            if not session:
                yield f"data: {json.dumps({'type': 'error', 'message': '会话不存在'})}\n\n"
                return

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

            # 调用路由分发（获取意图）
            from app.services.router_service import intent_classifier
            intent = await intent_classifier.classify(data.question)

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

请提供准确、简洁的回答，并在回答中标注引用来源（如"根据文档1..."）。"""

                        full_answer = ""
                        async for chunk in llm_service.chat_stream(prompt):
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
                        )

            elif intent == "data":
                # 数据查询
                yield emit_thinking(1, 4, '意图分析', '识别用户意图，确定查询策略...')

                from app.services.chatbi_service import chatbi_service
                explanation, results, traces, query_time, explanation_prompt, column_meta, chart_type = await chatbi_service.query(
                    db, data.question, data.datasourceId
                )

                yield emit_thinking(2, 4, 'SQL生成', f'成功生成 SQL 查询语句，共 {len(traces)} 条')

                # 发送SQL溯源
                yield f"data: {json.dumps({'type': 'sql_traces', 'data': traces})}\n\n"

                yield emit_thinking(3, 4, '数据查询', f'执行 SQL 查询，返回 {len(results) if results else 0} 条结果')

                # 发送数据结果（含字段元信息和推荐图表类型）
                yield f"data: {json.dumps({'type': 'data_result', 'data': results, 'columnMeta': column_meta, 'chartType': chart_type})}\n\n"

                # 提交事务释放数据库连接，再调用LLM生成解释
                await db.commit()

                # 使用prompt流式生成解释（真正的流式输出）
                yield emit_thinking(4, 4, '结果分析', '分析查询结果，生成自然语言解释...')

                from app.services.llm_service import llm_service
                full_explanation = ""
                if explanation_prompt:
                    async for chunk in llm_service.chat_stream(explanation_prompt):
                        full_explanation += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                else:
                    full_explanation = explanation
                    yield f"data: {json.dumps({'type': 'content', 'content': explanation})}\n\n"

                # 保存AI回复（需要重新创建事务）
                await db.begin()
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

            else:
                # 混合模式：分步骤展示融合推理过程
                from app.services.chatbi_service import chatbi_service
                from app.services.vector_service import VectorIndexService
                from app.services.router_service import IntentClassifier
                from app.models.knowledge import KnowledgeBase
                from app.schemas.knowledge import KnowledgeQuery

                total_steps = 5

                # 步骤1：意图分析
                yield emit_thinking(1, total_steps, '意图分析', '识别混合问题，拆分数据查询与知识问答子问题...')

                data_question, knowledge_question = await IntentClassifier.split_hybrid_question(data.question)

                knowledge_answer = ""
                explanation = ""
                explanation_prompt = None
                knowledge_prompt = None
                references = []
                sql_traces = []
                data_result = None
                column_meta = None
                chart_type = None

                # 步骤2+3：并行执行知识检索与数据查询
                async def _do_knowledge_search():
                    """执行知识检索子任务（仅向量搜索，不生成回答）"""
                    nonlocal references, knowledge_prompt
                    if not knowledge_question or not data.knowledgeBaseId:
                        return
                    kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == data.knowledgeBaseId)
                    kb_result = await db.execute(kb_stmt)
                    kb = kb_result.scalar_one_or_none()
                    if not kb:
                        return
                    query = KnowledgeQuery(
                        knowledgeBaseId=data.knowledgeBaseId,
                        question=knowledge_question,
                        topK=3,
                    )
                    refs = await VectorIndexService.search(db, query, kb)
                    references = [r.model_dump() for r in refs]
                    # 构建知识回答prompt，但不执行（留到步骤5流式生成）
                    if refs:
                        context_text = (chr(10) * 2).join([f"【文档{i+1}】{ref.content}" for i, ref in enumerate(refs)])
                        knowledge_prompt = f"""基于以下知识内容回答用户问题，如果知识内容中没有相关信息，请明确说明。

知识内容：
{context_text}

用户问题：{knowledge_question}

请提供准确、简洁的回答。"""

                async def _do_data_query():
                    """执行数据查询子任务"""
                    nonlocal explanation, data_result, sql_traces, column_meta, chart_type, explanation_prompt
                    if not data_question or not data.datasourceId:
                        return
                    exp, results, traces, _, exp_prompt, col_meta, c_type = await chatbi_service.query(
                        db, data_question, data.datasourceId
                    )
                    explanation = exp
                    data_result = results
                    sql_traces = traces
                    column_meta = col_meta
                    chart_type = c_type
                    explanation_prompt = exp_prompt

                # 并行启动知识检索和数据查询
                yield emit_thinking(2, total_steps, '知识检索', f'并行执行知识检索与数据查询...')
                await asyncio.gather(_do_knowledge_search(), _do_data_query())

                # 按顺序展示步骤结果
                if references:
                    yield f"data: {json.dumps({'type': 'references', 'data': references})}\n\n"

                yield emit_thinking(3, total_steps, 'SQL生成', f'知识检索与SQL查询已并行完成')

                if sql_traces:
                    yield f"data: {json.dumps({'type': 'sql_traces', 'data': sql_traces})}\n\n"

                # 步骤4：数据分析
                if data_result:
                    yield emit_thinking(4, total_steps, '数据分析', f'查询返回 {len(data_result)} 条数据结果')
                    yield f"data: {json.dumps({'type': 'data_result', 'data': data_result, 'columnMeta': column_meta, 'chartType': chart_type})}\n\n"
                else:
                    yield emit_thinking(4, total_steps, '数据分析', '未获取到数据结果')

                # 步骤5：融合分析
                yield emit_thinking(5, total_steps, '融合分析', '融合知识解答与数据分析结果，生成综合回答...')

                # 提交事务释放数据库连接，再调用LLM生成解释
                await db.commit()

                from app.services.llm_service import llm_service
                full_answer = ""

                # 使用队列实现并行流式输出
                data_chunks_queue = asyncio.Queue()
                data_stream_done = asyncio.Event()

                async def _produce_data_explanation():
                    """后台生成数据分析解释，放入队列"""
                    if not data_result or len(data_result) == 0:
                        if explanation:
                            await data_chunks_queue.put(explanation)
                        data_stream_done.set()
                        return
                    if explanation_prompt:
                        async for chunk in llm_service.chat_stream(explanation_prompt):
                            await data_chunks_queue.put(chunk)
                    elif explanation:
                        await data_chunks_queue.put(explanation)
                    data_stream_done.set()

                # 并行：知识回答流式输出 + 数据分析解释后台生成
                if knowledge_prompt:
                    full_answer += "【知识解答】" + chr(10)
                    label = "【知识解答】" + chr(10)
                    yield f"data: {json.dumps({'type': 'content', 'content': label})}\n\n"

                    knowledge_answer = ""
                    data_producer = asyncio.create_task(_produce_data_explanation())

                    async for chunk in llm_service.chat_stream(knowledge_prompt):
                        # 知识解答内部不产生空行，将连续换行合并为单换行
                        chunk = chunk.replace(chr(10) * 2, chr(10))
                        knowledge_answer += chunk
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"

                    # 知识解答结束，输出换行分隔
                    full_answer += chr(10)
                    separator = chr(10)
                    yield f"data: {json.dumps({'type': 'content', 'content': separator})}\n\n"
                else:
                    # 没有知识回答，直接启动数据分析解释
                    data_producer = asyncio.create_task(_produce_data_explanation())

                # 流式输出数据分析解释（从队列中取出已生成的chunk）
                has_data_output = False
                while not data_stream_done.is_set() or not data_chunks_queue.empty():
                    try:
                        chunk = await asyncio.wait_for(data_chunks_queue.get(), timeout=0.1)
                        if not has_data_output:
                            has_data_output = True
                            full_answer += "【数据分析】" + chr(10)
                            label = "【数据分析】" + chr(10)
                            yield f"data: {json.dumps({'type': 'content', 'content': label})}\n\n"
                        full_answer += chunk
                        yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                    except asyncio.TimeoutError:
                        continue

                if not has_data_output and explanation:
                    full_answer += "【数据分析】" + chr(10) + explanation
                    label = "【数据分析】" + chr(10) + explanation
                    yield f"data: {json.dumps({'type': 'content', 'content': label})}\n\n"

                # 重新创建事务
                await db.begin()

                if not full_answer.strip():
                    full_answer = "抱歉，无法找到相关信息或数据。"
                    yield f"data: {json.dumps({'type': 'content', 'content': full_answer})}\n\n"

                # 保存AI回复
                await message_service.create(
                    db,
                    session_id=data.sessionId,
                    role="assistant",
                    content=full_answer,
                    intent="hybrid",
                    references=references,
                    sql_traces=sql_traces,
                    data_result=data_result,
                    column_meta=column_meta,
                    chart_type=chart_type,
                    thinking_steps=collected_thinking_steps,
                    query_time=int((time.time() - stream_start_time) * 1000),
                )

            # 提交事务
            await db.commit()

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            if db:
                await db.rollback()
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            if db:
                await db.close()

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )