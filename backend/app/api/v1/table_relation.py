"""
表关系API（NL2SQL 升级二期：联表查询关联键白名单）

路由前缀由 api_router 统一挂载为 /datasources，本路由内路径为 /{ds_id}/relations...
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.schemas.table_relation import (
    RelationCreate,
    RelationUpdate,
    BatchConfirmRequest,
    BatchActionRequest,
    ProbeRequest,
)
from app.services.table_relation_service import table_relation_service
from app.middlewares.exception_handler import success_response
from app.middlewares.auth_deps import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/{ds_id}/relations", summary="获取表关系列表")
async def list_relations(
    ds_id: int,
    status: Optional[str] = Query(None, description="状态过滤: active/inactive/ignored"),
    source: Optional[str] = Query(None, description="来源过滤: foreign_key/auto_guess/manual"),
    keyword: Optional[str] = Query(None, description="关键词（表名/字段名/描述）"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, description="每页条数"),
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """分页查询表关系，支持状态/来源/关键词过滤"""
    result = await table_relation_service.list_relations(
        db, ds_id, status=status, source=source, keyword=keyword,
        page=page, page_size=pageSize,
    )
    return success_response(data=result)


@router.post("/{ds_id}/relations", summary="新建表关系")
async def create_relation(
    ds_id: int,
    data: RelationCreate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """手工新建关系（画布连线/表单），存储前规范化端点方向，同四元组幂等"""
    rel = await table_relation_service.create_relation(db, ds_id, data.model_dump())
    return success_response(data=rel.to_dict(), message="表关系创建成功")


@router.put("/{ds_id}/relations/{rel_id}", summary="编辑表关系")
async def update_relation(
    ds_id: int,
    rel_id: int,
    data: RelationUpdate,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """编辑基数/描述/JOIN类型/状态/关联键分组"""
    rel = await table_relation_service.update_relation(db, ds_id, rel_id, data.model_dump(exclude_unset=True))
    return success_response(data=rel.to_dict(), message="表关系更新成功")


@router.delete("/{ds_id}/relations/{rel_id}", summary="删除表关系")
async def delete_relation(
    ds_id: int,
    rel_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """删除关系（仅 manual/auto_guess；外键关系只允许停用）"""
    await table_relation_service.delete_relation(db, ds_id, rel_id)
    return success_response(message="表关系删除成功")


@router.post("/{ds_id}/relations/batch-confirm", summary="批量确认表关系")
async def batch_confirm(
    ds_id: int,
    data: BatchConfirmRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """批量确认候选关系（inactive → active），可统一补充基数"""
    updated = await table_relation_service.batch_confirm(db, ds_id, data.ids, data.cardinality)
    return success_response(data={"updated": updated}, message=f"已确认{updated}条关系")


@router.post("/{ds_id}/relations/batch-ignore", summary="批量忽略表关系")
async def batch_ignore(
    ds_id: int,
    data: BatchActionRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """批量忽略关系（→ ignored，不参与JOIN白名单）"""
    updated = await table_relation_service.batch_ignore(db, ds_id, data.ids)
    return success_response(data={"updated": updated}, message=f"已忽略{updated}条关系")


@router.post("/{ds_id}/relations/probe", summary="表关系SQL探测")
async def probe_relation(
    ds_id: int,
    data: ProbeRequest,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """
    SQL 探测：基数实测 + 放大系数（录入时暴露关联放大风险）

    探测 SQL 服务端拼装（仅 SELECT COUNT 形态），走只读连接 + 30s 超时 + LIMIT 防大表全扫；
    结论缓存到已存在 relation 行的 probe 字段。
    """
    result = await table_relation_service.probe_relation(db, ds_id, data.model_dump())
    return success_response(data=result)


@router.post("/{ds_id}/relations/collect", summary="手动触发关系采集")
async def collect_relations(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """手动重跑三通道采集（外键 + 同名同类型推荐）"""
    result = await table_relation_service.collect_relations(db, ds_id)
    return success_response(data=result, message="关系采集完成")


@router.get("/{ds_id}/relation-graph", summary="获取表关系图聚合数据")
async def get_relation_graph(
    ds_id: int,
    db: AsyncSession = Depends(get_db_session),
    user: User = Depends(get_current_user),
):
    """画布/总览一次取全量：nodes(表+字段) + edges(关系+探测结论) + stats"""
    graph = await table_relation_service.get_relation_graph(db, ds_id)
    return success_response(data=graph)
