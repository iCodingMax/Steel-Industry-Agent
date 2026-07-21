"""
维度服务模块
管理钢铁行业业务维度的CRUD操作

主要功能：
1. 维度管理：创建、查询、更新、删除维度
2. 代码唯一性校验：确保维度代码不重复
3. 按数据源筛选：支持获取特定数据源下的维度
4. 层级关系：支持维度的父子层级关系

维度数据结构：
- name: 维度名称（中文）
- code: 维度代码（唯一标识）
- description: 维度描述
- datasource_id: 关联数据源ID
- table_name: 关联表名
- column_name: 关联字段名
- data_type: 数据类型（string/number/date/enum）
- level: 层级级别（1-5）
- parent_id: 父维度ID（用于构建层级）
"""
from typing import List, Optional
from sqlalchemy import select
from loguru import logger

from app.models.dimension import Dimension
from app.schemas.dimension import DimensionCreate, DimensionUpdate
from app.middlewares.exception_handler import BusinessException


class DimensionService:
    """
    维度服务类
    负责钢铁行业业务维度的生命周期管理
    支持维度的创建、查询、更新、删除和按数据源筛选
    """

    @staticmethod
    async def create(db, data: DimensionCreate) -> Dimension:
        """
        创建维度

        :param db: 数据库会话
        :param data: 维度创建参数
        :return: 创建的维度对象
        :raises BusinessException: 维度代码已存在时抛出
        """
        logger.debug(f"创建维度: name={data.name}, code={data.code}")

        # 校验代码唯一性
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
        logger.info(f"创建维度成功: {dimension.name} (ID: {dimension.id})")
        return dimension

    @staticmethod
    async def get_by_id(db, dimension_id: int) -> Optional[Dimension]:
        """
        根据ID获取维度

        :param db: 数据库会话
        :param dimension_id: 维度ID
        :return: 维度对象（不存在返回None）
        """
        stmt = select(Dimension).where(Dimension.id == dimension_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_code(db, code: str) -> Optional[Dimension]:
        """
        根据代码获取维度

        :param db: 数据库会话
        :param code: 维度代码
        :return: 维度对象（不存在返回None）
        """
        stmt = select(Dimension).where(Dimension.code == code)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[Dimension]:
        """
        获取所有维度

        :param db: 数据库会话
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数）
        :return: 维度列表
        """
        stmt = select(Dimension).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_datasource(db, datasource_id: int) -> List[Dimension]:
        """
        根据数据源获取维度

        :param db: 数据库会话
        :param datasource_id: 数据源ID
        :return: 该数据源下的维度列表
        """
        stmt = select(Dimension).where(Dimension.datasource_id == datasource_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def update(db, dimension_id: int, data: DimensionUpdate) -> Optional[Dimension]:
        """
        更新维度

        :param db: 数据库会话
        :param dimension_id: 维度ID
        :param data: 更新参数（仅包含需要更新的字段）
        :return: 更新后的维度对象
        :raises BusinessException: 维度不存在时抛出
        """
        dimension = await DimensionService.get_by_id(db, dimension_id)
        if not dimension:
            raise BusinessException(code=404, message="维度不存在")

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if hasattr(dimension, key):
                setattr(dimension, key, value)

        await db.commit()
        await db.refresh(dimension)
        logger.info(f"更新维度成功: {dimension.name} (ID: {dimension.id})")
        return dimension

    @staticmethod
    async def delete(db, dimension_id: int) -> None:
        """
        删除维度

        :param db: 数据库会话
        :param dimension_id: 维度ID
        :raises BusinessException: 维度不存在时抛出
        """
        dimension = await DimensionService.get_by_id(db, dimension_id)
        if not dimension:
            raise BusinessException(code=404, message="维度不存在")

        await db.delete(dimension)
        await db.commit()
        logger.info(f"删除维度成功: {dimension.name} (ID: {dimension_id})")


# 服务实例
dimension_service = DimensionService()
logger.info("维度服务实例已创建")
