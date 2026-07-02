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
    answer, references, sql_traces, query_time = await router_service.route(
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
        query_time=int(query_time * 1000),
    )

    response = ChatResponse(
        messageId=ai_msg.id,
        content=answer,
        intent=session.intent_type or "hybrid",
        references=references,
        sqlTraces=sql_traces,
        queryTime=int(query_time * 1000),
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
                yield f"data: {json.dumps({'type': 'thinking', 'step': 1, 'total_steps': 3, 'title': '查询知识库', 'description': '正在检索相关文档知识...'})}\n\n"

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

                        yield f"data: {json.dumps({'type': 'thinking', 'step': 2, 'total_steps': 3, 'title': '知识匹配完成', 'description': f'找到 {len(refs)} 条相关文档，相似度最高 {max([r.score for r in refs]):.2f}' if refs else f'找到 0 条相关文档'})}\n\n"

                        # 发送引用信息
                        yield f"data: {json.dumps({'type': 'references', 'data': [r.model_dump() for r in refs]})}\n\n"

                        # 流式生成回答
                        yield f"data: {json.dumps({'type': 'thinking', 'step': 3, 'total_steps': 3, 'title': '生成回答', 'description': '基于知识库内容生成自然语言回答...'})}\n\n"

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
                        )

            elif intent == "data":
                # 数据查询
                yield f"data: {json.dumps({'type': 'thinking', 'step': 1, 'total_steps': 4, 'title': '意图分析', 'description': '识别用户意图，确定查询策略...'})}\n\n"

                from app.services.chatbi_service import chatbi_service
                explanation, results, traces, query_time, explanation_prompt, column_meta, chart_type = await chatbi_service.query(
                    db, data.question, data.datasourceId
                )

                yield f"data: {json.dumps({'type': 'thinking', 'step': 2, 'total_steps': 4, 'title': 'SQL生成', 'description': f'成功生成 SQL 查询语句，共 {len(traces)} 条'})}\n\n"

                # 发送SQL溯源
                yield f"data: {json.dumps({'type': 'sql_traces', 'data': traces})}\n\n"

                yield f"data: {json.dumps({'type': 'thinking', 'step': 3, 'total_steps': 4, 'title': '数据查询', 'description': f'执行 SQL 查询，返回 {len(results) if results else 0} 条结果'})}\n\n"

                # 发送数据结果（含字段元信息和推荐图表类型）
                yield f"data: {json.dumps({'type': 'data_result', 'data': results, 'columnMeta': column_meta, 'chartType': chart_type})}\n\n"

                # 提交事务释放数据库连接，再调用LLM生成解释
                await db.commit()

                # 使用prompt流式生成解释（真正的流式输出）
                yield f"data: {json.dumps({'type': 'thinking', 'step': 4, 'total_steps': 4, 'title': '结果分析', 'description': '分析查询结果，生成自然语言解释...'})}\n\n"

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
                    query_time=int(query_time * 1000),
                )

            else:
                # 混合模式
                yield f"data: {json.dumps({'type': 'content', 'content': '正在分析您的问题...'})}\n\n"

                # 简化处理
                answer, references, sql_traces, query_time = await router_service.route(
                    db,
                    data.question,
                    data.knowledgeBaseId,
                    data.datasourceId,
                )

                # 分块发送
                for chunk in answer.split("\n"):
                    if chunk.strip():
                        content = chunk + "\n"
                        yield f"data: {json.dumps({'type': 'content', 'content': content})}\n\n"
                        await asyncio.sleep(0.05)

                # 保存AI回复
                await message_service.create(
                    db,
                    session_id=data.sessionId,
                    role="assistant",
                    content=answer,
                    intent="hybrid",
                    references=references,
                    sql_traces=sql_traces,
                    query_time=int(query_time * 1000),
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