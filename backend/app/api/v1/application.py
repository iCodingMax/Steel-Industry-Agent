"""
应用管理API路由模块
提供应用的CRUD操作和集成设置接口
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from loguru import logger

from app.core.database import get_db_session
from app.models.application import Application, AppPrompt, generate_access_hash
from app.models.user import User
from app.middlewares.auth_deps import get_current_user
from app.middlewares.exception_handler import BusinessException, success_response

router = APIRouter()

# P3-4/3-6b：应用类型值域（三类型定型，见方案 2.8）
AGENT_MODE_DOMAIN = ("classic", "chatbi", "agent")


def _reject_binding_increase(
    new_ids: Optional[List[int]],
    existing_ids: Optional[List[int]],
    message: str,
) -> None:
    """
    P3-6b 绑定强校验（update 侧）：越界绑定只允许减少/清空，不允许新增

    存量豁免设计（方案 2.8.1）：存量混合绑定不清数据，运行时白名单兜底，
    编辑保存引导清空（只减不增）——故仅拦截"新增越界绑定"方向。

    :param new_ids: 本次请求携带的绑定ID列表（None 表示未传，沿用存量）
    :param existing_ids: 存量绑定ID列表
    :param message: 拦截时的错误提示
    :raises BusinessException: 携带存量中不存在的绑定ID时抛 400
    """
    if not new_ids:
        return
    existing = set(existing_ids or [])
    if any(i not in existing for i in new_ids):
        raise BusinessException(code=400, message=message)


class ApplicationCreate(BaseModel):
    """应用创建请求模型"""
    name: str = Field(..., description="应用名称")
    description: str = Field(None, description="应用描述")
    modelName: str = Field("glm-5.1-fp8", description="LLM模型名称")
    embeddingModel: str = Field("bge-m3", description="嵌入模型名称")
    rerankModel: str = Field("bge-reranker-large", description="重排模型名称")
    systemPrompt: str = Field(None, description="系统提示词")
    userPromptTemplate: str = Field(None, description="用户提示词模板")
    greetingMessage: str = Field(None, description="开场白消息")
    knowledgeBaseIds: List[int] = Field([], description="关联知识库ID列表")
    datasourceIds: List[int] = Field([], description="关联数据源ID列表")
    toolConfigIds: List[int] = Field([], description="关联工具配置ID列表(MCP/Skills)")
    scoreThreshold: float = Field(0.6, description="检索相似度阈值(0-1之间)")
    topK: int = Field(3, description="引用分段数(1-10之间)")
    maxTokens: int = Field(8192, description="最大生成token数")
    temperature: float = Field(0.7, description="温度参数(0.0-2.0)")
    topP: float = Field(0.9, description="top_p参数(0.0-1.0)")
    agentMode: str = Field("classic", pattern="^(classic|chatbi|agent)$", description="应用类型: classic(对话助手)/chatbi(数据助手)/agent(智能体)，创建时定型")
    agentPlanEnabled: bool = Field(False, description="Agent模式规划开关(P1-1:复杂问题先经planner产出步骤清单)")


class ApplicationUpdate(BaseModel):
    """应用更新请求模型"""
    name: str = Field(None, description="应用名称")
    description: str = Field(None, description="应用描述")
    icon: str = Field(None, description="应用图标URL")
    status: str = Field(None, description="状态")
    modelName: str = Field(None, description="LLM模型名称")
    embeddingModel: str = Field(None, description="嵌入模型名称")
    rerankModel: str = Field(None, description="重排模型名称")
    systemPrompt: str = Field(None, description="系统提示词")
    userPromptTemplate: str = Field(None, description="用户提示词模板")
    greetingMessage: str = Field(None, description="开场白消息")
    knowledgeBaseIds: List[int] = Field(None, description="关联知识库ID列表")
    datasourceIds: List[int] = Field(None, description="关联数据源ID列表")
    toolConfigIds: List[int] = Field(None, description="关联工具配置ID列表(MCP/Skills)")
    scoreThreshold: float = Field(None, description="检索相似度阈值(0-1之间)")
    topK: int = Field(None, description="引用分段数(1-10之间)")
    iframeHeight: int = Field(None, description="iframe默认高度")
    iframeWidth: str = Field(None, description="iframe默认宽度")
    requireAuth: bool = Field(None, description="是否需要身份验证")
    maxTokens: int = Field(None, description="最大生成token数")
    temperature: float = Field(None, description="温度参数(0.0-2.0)")
    topP: float = Field(None, description="top_p参数(0.0-1.0)")
    agentMode: str = Field(None, pattern="^(classic|chatbi|agent)$", description="应用类型（P3-4 不可变：仅放行 classic→chatbi 定向升级，其余变更抛400）")
    agentMaxIterations: int = Field(None, ge=3, le=30, description="Agent模式最大推理迭代次数(3-30,默认8)")
    agentPlanEnabled: bool = Field(None, description="Agent模式规划开关(P1-1:复杂问题先经planner产出步骤清单)")


class AppPromptCreate(BaseModel):
    """提示词创建请求模型"""
    name: str = Field(..., description="提示词名称")
    type: str = Field("system", description="类型: system/user/tool")
    content: str = Field(..., description="提示词内容")
    isActive: bool = Field(True, description="是否启用")
    sortOrder: int = Field(0, description="排序顺序")


class AppPromptUpdate(BaseModel):
    """提示词更新请求模型"""
    name: str = Field(None, description="提示词名称")
    type: str = Field(None, description="类型")
    content: str = Field(None, description="提示词内容")
    isActive: bool = Field(None, description="是否启用")
    sortOrder: int = Field(None, description="排序顺序")


@router.get("", summary="获取应用列表")
async def get_applications(
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    keyword: str = Query(None, description="搜索关键词"),
):
    """获取应用列表，支持分页和搜索"""
    query = select(Application)
    
    if keyword:
        query = query.where(Application.name.like(f"%{keyword}%"))
    
    query = query.order_by(Application.created_at.desc())
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    apps = result.scalars().all()
    
    count_result = await db.execute(select(Application))
    total = len(count_result.scalars().all())
    
    return success_response({
        "data": [app.to_dict() for app in apps],
        "total": total,
        "page": page,
        "pageSize": page_size,
    })


@router.get("/{app_id}", summary="获取应用详情")
async def get_application(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取单个应用的详细信息"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise BusinessException(code=404, message="应用不存在")
    
    prompts_result = await db.execute(
        select(AppPrompt).where(AppPrompt.application_id == app_id).order_by(AppPrompt.sort_order)
    )
    prompts = prompts_result.scalars().all()
    
    app_dict = app.to_dict()
    app_dict["prompts"] = [p.to_dict() for p in prompts]
    
    return success_response(app_dict)


@router.post("", summary="创建应用")
async def create_application(
    data: ApplicationCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """创建新应用"""
    logger.info(f"开始创建应用, name={data.name}, user_id={user.id}")
    try:
        existing = await db.execute(select(Application).where(Application.name == data.name))
        if existing.scalar_one_or_none():
            raise BusinessException(code=400, message="应用名称已存在")

        # P3-6b 绑定强校验（闸门1，方案 2.8.1 绑定约束表）：类型定型即能力域定型
        agent_mode = data.agentMode  # schema pattern 已保证值域合法
        if agent_mode == "classic" and (data.datasourceIds or data.toolConfigIds):
            raise BusinessException(code=400, message="对话助手不支持数据源/工具配置")
        if agent_mode == "chatbi" and (data.knowledgeBaseIds or data.toolConfigIds):
            raise BusinessException(code=400, message="数据助手不支持知识库/工具配置")

        app = Application(
            name=data.name,
            description=data.description,
            model_name=data.modelName,
            embedding_model=data.embeddingModel,
            rerank_model=data.rerankModel,
            system_prompt=data.systemPrompt,
            user_prompt_template=data.userPromptTemplate,
            greeting_message=data.greetingMessage,
            knowledge_base_ids=data.knowledgeBaseIds,
            datasource_ids=data.datasourceIds,
            tool_config_ids=data.toolConfigIds,
            score_threshold=data.scoreThreshold,
            top_k=data.topK,
            max_tokens=data.maxTokens,
            temperature=int(data.temperature * 10),
            top_p=int(data.topP * 10),
            api_key=str(uuid.uuid4()).replace("-", ""),
            agent_mode=agent_mode,
            agent_plan_enabled=data.agentPlanEnabled,
            created_by=user.id,
        )
        
        db.add(app)
        await db.commit()
        await db.refresh(app)
        logger.info(f"应用创建成功, id={app.id}, name={app.name}")
        return success_response(app.to_dict())
    except Exception as e:
        logger.error(f"创建应用失败: {e}")
        raise


@router.put("/{app_id}", summary="更新应用")
async def update_application(
    app_id: int,
    data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新应用配置"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise BusinessException(code=404, message="应用不存在")
    
    if data.name and data.name != app.name:
        existing = await db.execute(select(Application).where(Application.name == data.name))
        if existing.scalar_one_or_none():
            raise BusinessException(code=400, message="应用名称已存在")

    # P3-4 类型不可变校验（方案 2.8.2）：
    #   agent_mode 与存量不一致 → 400（行为契约稳定，变更走"另存新应用"）
    #   唯一例外：classic→chatbi 定向升级（方案 2.8.8 受控路径，
    #   本次请求或存量须已绑定数据源——升级后 data 分支依赖该绑定）
    current_mode = app.agent_mode or "classic"
    is_chatbi_upgrade = data.agentMode == "chatbi" and current_mode == "classic"
    if data.agentMode is not None and data.agentMode != current_mode and not is_chatbi_upgrade:
        raise BusinessException(
            code=400,
            message=f"应用类型不可变（当前 {current_mode}），如需其他类型请另存为新应用",
        )
    if is_chatbi_upgrade:
        if not (data.datasourceIds or app.datasource_ids):
            raise BusinessException(
                code=400,
                message="升级为数据助手前请先绑定数据源",
            )
        logger.info(f"应用 {app_id} 执行 classic→chatbi 定向升级")

    # P3-6b 越界绑定只减不增（存量豁免：只拦增量不追溯存量，方案 2.8.1）
    # 类型判定基准：升级请求按目标类型 chatbi 校验（升级即切换能力域，
    # 数据源绑定方向放开，知识库/工具仍只减不增）
    effective_mode = "chatbi" if is_chatbi_upgrade else current_mode
    if effective_mode == "classic":
        _reject_binding_increase(
            data.datasourceIds, app.datasource_ids,
            "对话助手不支持数据源配置（存量绑定仅允许清空）",
        )
        _reject_binding_increase(
            data.toolConfigIds, app.tool_config_ids,
            "对话助手不支持工具配置（存量绑定仅允许清空）",
        )
    elif effective_mode == "chatbi":
        _reject_binding_increase(
            data.knowledgeBaseIds, app.knowledge_base_ids,
            "数据助手不支持知识库配置（存量绑定仅允许清空）",
        )
        _reject_binding_increase(
            data.toolConfigIds, app.tool_config_ids,
            "数据助手不支持工具配置（存量绑定仅允许清空）",
        )
    
    field_mapping = {
        'name': data.name,
        'description': data.description,
        'icon': data.icon,
        'status': data.status,
        'model_name': data.modelName,
        'embedding_model': data.embeddingModel,
        'rerank_model': data.rerankModel,
        'system_prompt': data.systemPrompt,
        'user_prompt_template': data.userPromptTemplate,
        'greeting_message': data.greetingMessage,
        'knowledge_base_ids': data.knowledgeBaseIds,
        'datasource_ids': data.datasourceIds,
        'tool_config_ids': data.toolConfigIds,
        'score_threshold': data.scoreThreshold,
        'top_k': data.topK,
        'iframe_height': data.iframeHeight,
        'iframe_width': data.iframeWidth,
        'require_auth': data.requireAuth,
        'max_tokens': data.maxTokens,
        'temperature': int(data.temperature * 10) if data.temperature is not None else None,
        'top_p': int(data.topP * 10) if data.topP is not None else None,
        'agent_mode': data.agentMode,
        'agent_max_iterations': data.agentMaxIterations,
        'agent_plan_enabled': data.agentPlanEnabled,
    }
    
    for field, value in field_mapping.items():
        if value is not None:
            setattr(app, field, value)
    
    await db.commit()
    await db.refresh(app)
    
    return success_response(app.to_dict())


@router.delete("/{app_id}", summary="删除应用")
async def delete_application(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除应用及其关联的提示词"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()

    if not app:
        raise BusinessException(code=404, message="应用不存在")

    await db.execute(delete(AppPrompt).where(AppPrompt.application_id == app_id))
    await db.execute(delete(Application).where(Application.id == app_id))
    await db.commit()
    
    return success_response(message="应用删除成功")


@router.post("/{app_id}/regenerate-api-key", summary="重新生成API密钥")
async def regenerate_api_key(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """重新生成应用的API密钥"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise BusinessException(code=404, message="应用不存在")

    new_key = str(uuid.uuid4()).replace("-", "")
    app.api_key = new_key
    
    await db.commit()
    await db.refresh(app)
    
    return success_response({"apiKey": new_key})


@router.get("/{app_id}/prompts", summary="获取应用提示词列表")
async def get_app_prompts(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """获取应用关联的所有提示词"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    if not result.scalar_one_or_none():
        raise BusinessException(code=404, message="应用不存在")
    
    prompts_result = await db.execute(
        select(AppPrompt).where(AppPrompt.application_id == app_id).order_by(AppPrompt.sort_order)
    )
    prompts = prompts_result.scalars().all()
    
    return success_response({"data": [p.to_dict() for p in prompts]})


@router.post("/{app_id}/prompts", summary="创建应用提示词")
async def create_app_prompt(
    app_id: int,
    data: AppPromptCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """为应用创建新提示词"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    if not result.scalar_one_or_none():
        raise BusinessException(code=404, message="应用不存在")
    
    prompt = AppPrompt(
        application_id=app_id,
        name=data.name,
        type=data.type,
        content=data.content,
        is_active=data.isActive,
        sort_order=data.sortOrder,
    )
    
    db.add(prompt)
    await db.commit()
    await db.refresh(prompt)
    
    return success_response(prompt.to_dict())


@router.put("/{app_id}/prompts/{prompt_id}", summary="更新应用提示词")
async def update_app_prompt(
    app_id: int,
    prompt_id: int,
    data: AppPromptUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """更新应用提示词"""
    result = await db.execute(
        select(AppPrompt).where(AppPrompt.id == prompt_id, AppPrompt.application_id == app_id)
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise BusinessException(code=404, message="提示词不存在")
    
    if data.name is not None:
        prompt.name = data.name
    if data.type is not None:
        prompt.type = data.type
    if data.content is not None:
        prompt.content = data.content
    if data.isActive is not None:
        prompt.is_active = data.isActive
    if data.sortOrder is not None:
        prompt.sort_order = data.sortOrder
    
    await db.commit()
    await db.refresh(prompt)
    
    return success_response(prompt.to_dict())


@router.delete("/{app_id}/prompts/{prompt_id}", summary="删除应用提示词")
async def delete_app_prompt(
    app_id: int,
    prompt_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除应用提示词"""
    result = await db.execute(
        select(AppPrompt).where(AppPrompt.id == prompt_id, AppPrompt.application_id == app_id)
    )
    prompt = result.scalar_one_or_none()
    
    if not prompt:
        raise BusinessException(code=404, message="提示词不存在")

    await db.execute(delete(AppPrompt).where(AppPrompt.id == prompt_id))
    await db.commit()
    
    return success_response(message="提示词删除成功")


@router.get("/{app_id}/iframe-url", summary="获取iframe嵌入URL")
async def get_iframe_url(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """生成应用的iframe嵌入URL"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    
    if not app:
        raise BusinessException(code=404, message="应用不存在")

    if app.status != "active":
        raise BusinessException(code=400, message="应用未启用")

    # 确保access_hash存在
    if not app.access_hash:
        app.access_hash = generate_access_hash()
        await db.commit()
        await db.refresh(app)
    
    return success_response({
        "url": f"/chat/{app.access_hash}",
        "embedCode": f'<iframe src="/chat/{app.access_hash}" width="{app.iframe_width}" height="{app.iframe_height}px" frameborder="0"></iframe>',
    })


@router.get("/by-hash/{access_hash}", summary="通过hash获取应用（公开接口）")
async def get_application_by_hash(
    access_hash: str,
    db: AsyncSession = Depends(get_db_session),
):
    """通过access_hash获取应用信息，公开接口无需认证"""
    result = await db.execute(select(Application).where(Application.access_hash == access_hash))
    app = result.scalar_one_or_none()

    if not app:
        raise BusinessException(code=404, message="无效的访问链接")

    if app.status != "active":
        raise BusinessException(code=400, message="应用未启用")
    
    prompts_result = await db.execute(
        select(AppPrompt).where(AppPrompt.application_id == app.id).order_by(AppPrompt.sort_order)
    )
    prompts = prompts_result.scalars().all()
    
    app_dict = app.to_dict()
    app_dict["prompts"] = [p.to_dict() for p in prompts]
    
    return success_response(app_dict)


@router.post("/{app_id}/regenerate-access-hash", summary="重新生成公开访问hash")
async def regenerate_access_hash(
    app_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """重新生成应用的公开访问hash（生成新的16位随机十六进制hash）"""
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()

    if not app:
        raise BusinessException(code=404, message="应用不存在")

    # 生成新的access_hash并更新数据库
    new_hash = generate_access_hash()
    app.access_hash = new_hash
    await db.commit()
    await db.refresh(app)
    
    logger.info(f"应用 {app_id} 的access_hash已重新生成: {new_hash}")
    return success_response({"accessHash": new_hash})