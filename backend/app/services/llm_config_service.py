"""
大模型配置服务
"""
import json
from typing import List, Optional
from sqlalchemy import select, update
from loguru import logger

from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.middlewares.exception_handler import BusinessException


class LLMConfigService:
    """LLM配置服务类"""

    @staticmethod
    async def create(db, data: LLMConfigCreate) -> LLMConfig:
        """创建LLM配置"""
        if data.isDefault:
            await LLMConfigService.clear_default(db)

        config = LLMConfig(
            name=data.name,
            type=data.type,
            base_url=data.baseUrl,
            api_key=data.apiKey,
            model_name=data.modelName,
            model_type=data.modelType,
            max_tokens=data.maxTokens,
            temperature=data.temperature,
            top_p=data.topP,
            extra_params=json.dumps(data.extraParams, ensure_ascii=False) if data.extraParams else None,
            is_default=data.isDefault,
            description=data.description,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        logger.info(f"创建LLM配置: {config.name} (ID: {config.id})")
        return config

    @staticmethod
    async def get_by_id(db, config_id: int) -> Optional[LLMConfig]:
        """根据ID获取配置"""
        stmt = select(LLMConfig).where(LLMConfig.id == config_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[LLMConfig]:
        """获取所有配置"""
        stmt = select(LLMConfig).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_type(db, config_type: str) -> List[LLMConfig]:
        """根据类型获取配置"""
        stmt = select(LLMConfig).where(LLMConfig.type == config_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_model_type(db, model_type: str) -> Optional[LLMConfig]:
        """根据模型类型获取默认配置"""
        stmt = select(LLMConfig).where(
            (LLMConfig.model_type == model_type) & (LLMConfig.is_default == True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db, config_id: int, data: LLMConfigUpdate) -> Optional[LLMConfig]:
        """更新配置"""
        config = await LLMConfigService.get_by_id(db, config_id)
        if not config:
            raise BusinessException(code=404, message="配置不存在")

        if data.isDefault:
            await LLMConfigService.clear_default(db)

        update_data = data.model_dump(exclude_unset=True)
        if "extraParams" in update_data and update_data["extraParams"]:
            update_data["extraParams"] = json.dumps(update_data["extraParams"], ensure_ascii=False)
        for key, value in update_data.items():
            if hasattr(config, key):
                setattr(config, key, value)

        await db.commit()
        await db.refresh(config)
        logger.info(f"更新LLM配置: {config.name} (ID: {config.id})")
        return config

    @staticmethod
    async def delete(db, config_id: int) -> None:
        """删除配置"""
        config = await LLMConfigService.get_by_id(db, config_id)
        if not config:
            raise BusinessException(code=404, message="配置不存在")

        await db.delete(config)
        await db.commit()
        logger.info(f"删除LLM配置: {config.name} (ID: {config_id})")

    @staticmethod
    async def clear_default(db) -> None:
        """清除所有默认配置"""
        stmt = update(LLMConfig).where(LLMConfig.is_default == True).values(is_default=False)
        await db.execute(stmt)


llm_config_service = LLMConfigService()
