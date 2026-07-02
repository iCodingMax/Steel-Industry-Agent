"""
指标服务
"""
import json
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.metric import Metric
from app.schemas.metric import MetricCreate, MetricUpdate
from app.middlewares.exception_handler import BusinessException


class MetricService:
    """指标服务类"""

    @staticmethod
    async def create(db, data: MetricCreate) -> Metric:
        """创建指标"""
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
        logger.info(f"创建指标: {metric.name} (ID: {metric.id})")
        return metric

    @staticmethod
    async def get_by_id(db, metric_id: int) -> Optional[Metric]:
        """根据ID获取指标"""
        stmt = select(Metric).where(Metric.id == metric_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Metric]:
        """根据代码获取指标"""
        stmt = select(Metric).where(Metric.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Metric]:
        """获取所有指标"""
        stmt = select(Metric).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_datasource(db, datasource_id: int) -> List[Metric]:
        """根据数据源获取指标"""
        stmt = select(Metric).where(Metric.datasource_id == datasource_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db, metric_id: int, data: MetricUpdate) -> Optional[Metric]:
        """更新指标"""
        metric = await MetricService.get_by_id(db, metric_id)
        if not metric:
            raise BusinessException(code=404, message="指标不存在")

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
        logger.info(f"更新指标: {metric.name} (ID: {metric.id})")
        return metric

    @staticmethod
    async def delete(db, metric_id: int) -> None:
        """删除指标"""
        metric = await MetricService.get_by_id(db, metric_id)
        if not metric:
            raise BusinessException(code=404, message="指标不存在")

        await db.delete(metric)
        await db.commit()
        logger.info(f"删除指标: {metric.name} (ID: {metric_id})")


metric_service = MetricService()
