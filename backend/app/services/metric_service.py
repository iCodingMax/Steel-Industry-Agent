"""
指标服务模块
管理钢铁行业业务指标的CRUD操作

主要功能：
1. 指标管理：创建、查询、更新、删除指标
2. 代码唯一性校验：确保指标代码不重复
3. 按数据源筛选：支持获取特定数据源下的指标

指标数据结构：
- name: 指标名称（中文）
- code: 指标代码（唯一标识）
- description: 指标描述
- datasource_id: 关联数据源ID
- sql_expression: SQL表达式模板（包含{start_date}、{end_date}等变量）
- result_type: 结果类型（number/list/table）
- unit: 单位（如吨、%、元）
- group_name: 指标分组（如产量、质量、能耗）
- tags: 标签列表（JSON格式）
"""
import json
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricUpdate
from app.middlewares.exception_handler import BusinessException


class MetricService:
    """
    指标服务类
    负责钢铁行业业务指标的生命周期管理
    支持指标的创建、查询、更新、删除和按数据源筛选
    """

    @staticmethod
    async def create(db, data: MetricCreate) -> Metric:
        """
        创建指标

        :param db: 数据库会话
        :param data: 指标创建参数
        :return: 创建的指标对象
        :raises BusinessException: 指标代码已存在时抛出
        """
        logger.debug(f"创建指标: name={data.name}, code={data.code}")

        # 校验代码唯一性
        existing = await MetricService.get_by_code(db, data.code)
        if existing:
            raise BusinessException(code=400, message=f"指标代码已存在: {data.code}")

        metric = Metric(
            name=data.name,
            code=data.code,
            description=data.description,
            datasource_id=data.datasourceId,
            sql_expression=data.sqlExpression,
            result_type=data.resultType,
            unit=data.unit,
            group_name=data.groupName,
            tags=json.dumps(data.tags, ensure_ascii=False) if data.tags else None,
        )
        db.add(metric)
        await db.commit()
        await db.refresh(metric)
        logger.info(f"创建指标成功: {metric.name} (ID: {metric.id})")
        return metric

    @staticmethod
    async def get_by_id(db, metric_id: int) -> Optional[Metric]:
        """
        根据ID获取指标

        :param db: 数据库会话
        :param metric_id: 指标ID
        :return: 指标对象（不存在返回None）
        """
        stmt = select(Metric).where(Metric.id == metric_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Metric]:
        """
        根据代码获取指标

        :param db: 数据库会话
        :param code: 指标代码
        :return: 指标对象（不存在返回None）
        """
        stmt = select(Metric).where(Metric.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Metric]:
        """
        获取所有指标

        :param db: 数据库会话
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数）
        :return: 指标列表
        """
        stmt = select(Metric).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_datasource(db, datasource_id: int) -> List[Metric]:
        """
        根据数据源获取指标

        :param db: 数据库会话
        :param datasource_id: 数据源ID
        :return: 该数据源下的指标列表
        """
        stmt = select(Metric).where(Metric.datasource_id == datasource_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db, metric_id: int, data: MetricUpdate) -> Optional[Metric]:
        """
        更新指标

        :param db: 数据库会话
        :param metric_id: 指标ID
        :param data: 更新参数（仅包含需要更新的字段）
        :return: 更新后的指标对象
        :raises BusinessException: 指标不存在或代码重复时抛出
        """
        metric = await MetricService.get_by_id(db, metric_id)
        if not metric:
            raise BusinessException(code=404, message="指标不存在")

        # 如果代码被修改，校验新代码唯一性
        if data.code and data.code != metric.code:
            existing = await MetricService.get_by_code(db, data.code)
            if existing:
                raise BusinessException(code=400, message=f"指标代码已存在: {data.code}")

        update_data = data.model_dump(exclude_unset=True)
        if "tags" in update_data and update_data["tags"]:
            update_data["tags"] = json.dumps(update_data["tags"], ensure_ascii=False)
        for key, value in update_data.items():
            if hasattr(metric, key):
                setattr(metric, key, value)

        await db.commit()
        await db.refresh(metric)
        logger.info(f"更新指标成功: {metric.name} (ID: {metric.id})")
        return metric

    @staticmethod
    async def delete(db, metric_id: int) -> None:
        """
        删除指标

        :param db: 数据库会话
        :param metric_id: 指标ID
        :raises BusinessException: 指标不存在时抛出
        """
        metric = await MetricService.get_by_id(db, metric_id)
        if not metric:
            raise BusinessException(code=404, message="指标不存在")

        await db.delete(metric)
        await db.commit()
        logger.info(f"删除指标成功: {metric.name} (ID: {metric_id})")


# 服务实例
metric_service = MetricService()
logger.info("指标服务实例已创建")
