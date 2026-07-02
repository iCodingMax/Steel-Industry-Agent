"""
维度服务
"""
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.dimension import Dimension
from app.schemas.dimension import DimensionCreate, DimensionUpdate
from app.middlewares.exception_handler import BusinessException


class DimensionService:
    """维度服务类"""

    @staticmethod
    async def create(db, data: DimensionCreate) -> Dimension:
        """创建维度"""
        existing = await DimensionService.get_by_code(db, data.code)
        if existing:
            raise BusinessException(code=400, message=f"维度代码已存在: {data.code}")

        dimension = Dimension(
            name=data.name,
            code=data.code,
            description=data.description,
            datasource_id=data.datasourceId,
            table_name=data.tableName,
            column_name=data.columnName,
            data_type=data.dataType,
            level=data.level,
            parent_id=data.parentId,
        )
        db.add(dimension)
        await db.commit()
        await db.refresh(dimension)
        logger.info(f"创建维度: {dimension.name} (ID: {dimension.id})")
        return dimension

    @staticmethod
    async def get_by_id(db, dimension_id: int) -> Optional[Dimension]:
        """根据ID获取维度"""
        stmt = select(Dimension).where(Dimension.id == dimension_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Dimension]:
        """根据代码获取维度"""
        stmt = select(Dimension).where(Dimension.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Dimension]:
        """获取所有维度"""
        stmt = select(Dimension).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_datasource(db, datasource_id: int) -> List[Dimension]:
        """根据数据源获取维度"""
        stmt = select(Dimension).where(Dimension.datasource_id == datasource_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db, dimension_id: int, data: DimensionUpdate) -> Optional[Dimension]:
        """更新维度"""
        dimension = await DimensionService.get_by_id(db, dimension_id)
        if not dimension:
            raise BusinessException(code=404, message="维度不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(dimension, key):
                setattr(dimension, key, value)

        await db.commit()
        await db.refresh(dimension)
        logger.info(f"更新维度: {dimension.name} (ID: {dimension.id})")
        return dimension

    @staticmethod
    async def delete(db, dimension_id: int) -> None:
        """删除维度"""
        dimension = await DimensionService.get_by_id(db, dimension_id)
        if not dimension:
            raise BusinessException(code=404, message="维度不存在")

        await db.delete(dimension)
        await db.commit()
        logger.info(f"删除维度: {dimension.name} (ID: {dimension_id})")


dimension_service = DimensionService()
