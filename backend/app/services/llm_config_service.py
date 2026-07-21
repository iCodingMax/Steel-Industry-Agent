"""
大模型配置服务模块
管理LLM相关配置的CRUD操作和连接测试
支持三种模型类型：llm（对话模型）、embedding（向量化模型）、rerank（重排模型）

主要功能：
1. 配置管理：创建、查询、更新、删除模型配置
2. 默认配置：支持设置和管理默认配置
3. 连接测试：验证模型服务是否可正常访问
"""
import json
from typing import List, Optional
from sqlalchemy import select, update
from loguru import logger

from app.models.llm_config import LLMConfig
from app.schemas.llm_config import LLMConfigCreate, LLMConfigUpdate
from app.middlewares.exception_handler import BusinessException


class LLMConfigService:
    """
    LLM配置服务类
    负责大模型配置的生命周期管理
    支持多种模型类型的配置和连接测试
    """

    @staticmethod
    async def create(db, data: LLMConfigCreate) -> LLMConfig:
        """
        创建LLM配置

        :param db: 数据库会话
        :param data: 配置创建参数
        :return: 创建的配置对象
        :raises BusinessException: 配置创建失败时抛出
        """
        logger.debug(f"创建LLM配置: name={data.name}, modelType={data.modelType}")

        if data.isDefault:
            await LLMConfigService.clear_default(db)
            logger.debug("已清除其他默认配置")

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
            status="active",
            description=data.description,
        )
        db.add(config)
        await db.commit()
        await db.refresh(config)
        logger.info(f"创建LLM配置成功: {config.name} (ID: {config.id})")
        return config

    @staticmethod
    async def get_by_id(db, config_id: int) -> Optional[LLMConfig]:
        """
        根据ID获取配置

        :param db: 数据库会话
        :param config_id: 配置ID
        :return: 配置对象（不存在返回None）
        """
        stmt = select(LLMConfig).where(LLMConfig.id == config_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_all(db, skip: int = 0, limit: int = 100) -> List[LLMConfig]:
        """
        获取所有配置

        :param db: 数据库会话
        :param skip: 跳过条数（分页参数）
        :param limit: 返回条数（分页参数）
        :return: 配置列表
        """
        stmt = select(LLMConfig).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_type(db, config_type: str) -> List[LLMConfig]:
        """
        根据类型获取配置（如 xinference/openai）

        :param db: 数据库会话
        :param config_type: 配置类型
        :return: 配置列表
        """
        stmt = select(LLMConfig).where(LLMConfig.type == config_type)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_model_type(db, model_type: str) -> Optional[LLMConfig]:
        """
        根据模型类型获取默认配置

        :param db: 数据库会话
        :param model_type: 模型类型（llm/embedding/rerank）
        :return: 默认配置对象（不存在返回None）
        """
        stmt = select(LLMConfig).where(
            (LLMConfig.model_type == model_type) & (LLMConfig.is_default == True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def update(db, config_id: int, data: LLMConfigUpdate) -> Optional[LLMConfig]:
        """
        更新配置

        :param db: 数据库会话
        :param config_id: 配置ID
        :param data: 更新参数（仅包含需要更新的字段）
        :return: 更新后的配置对象
        :raises BusinessException: 配置不存在时抛出
        """
        config = await LLMConfigService.get_by_id(db, config_id)
        if not config:
            raise BusinessException(code=404, message="配置不存在")

        # 如果设置为默认配置，先清除其他默认配置
        if data.isDefault:
            await LLMConfigService.clear_default(db)

        update_data = data.model_dump(exclude_unset=True)
        
        field_mapping = {
            'baseUrl': 'base_url',
            'apiKey': 'api_key',
            'modelName': 'model_name',
            'modelType': 'model_type',
            'maxTokens': 'max_tokens',
            'temperature': 'temperature',
            'topP': 'top_p',
            'extraParams': 'extra_params',
            'isDefault': 'is_default',
        }

        for key, value in update_data.items():
            db_key = field_mapping.get(key, key)
            if hasattr(config, db_key):
                if db_key == "extra_params" and value:
                    value = json.dumps(value, ensure_ascii=False)
                setattr(config, db_key, value)

        await db.commit()
        await db.refresh(config)
        logger.info(f"更新LLM配置成功: {config.name} (ID: {config.id})")
        return config

    @staticmethod
    async def delete(db, config_id: int) -> None:
        """
        删除配置

        :param db: 数据库会话
        :param config_id: 配置ID
        :raises BusinessException: 配置不存在时抛出
        """
        config = await LLMConfigService.get_by_id(db, config_id)
        if not config:
            raise BusinessException(code=404, message="配置不存在")

        await db.delete(config)
        await db.commit()
        logger.info(f"删除LLM配置成功: {config.name} (ID: {config_id})")

    @staticmethod
    async def clear_default(db) -> None:
        """
        清除所有默认配置
        将所有is_default=True的配置设置为False

        :param db: 数据库会话
        """
        stmt = update(LLMConfig).where(LLMConfig.is_default == True).values(is_default=False)
        await db.execute(stmt)
        logger.debug("已清除所有默认配置")

    @staticmethod
    async def test_connection(config_data: dict) -> dict:
        """
        测试LLM配置连接
        根据模型类型发送不同的测试请求

        :param config_data: 配置数据字典，包含baseUrl、apiKey、modelName、modelType
        :return: 测试结果，包含success、message、model_type、response字段
        :raises BusinessException: 连接失败时抛出，包含详细错误信息
        """
        import httpx
        import json
        
        base_url = config_data.get('baseUrl', '')
        api_key = config_data.get('apiKey', '')
        model_name = config_data.get('modelName', '')
        model_type = config_data.get('modelType', 'llm')
        
        # 参数校验
        if not base_url:
            raise BusinessException(code=400, message="服务地址不能为空")
        if not model_name:
            raise BusinessException(code=400, message="模型名称不能为空")
        
        logger.debug(f"测试LLM连接: modelType={model_type}, baseUrl={base_url}, modelName={model_name}")
        
        try:
            base_url = base_url.strip().rstrip('/')
            
            if '/v1' not in base_url:
                base_url = f"{base_url}/v1"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 根据模型类型发送不同的测试请求
                if model_type == 'embedding':
                    # 向量化模型测试
                    response = await client.post(
                        f"{base_url}/embeddings",
                        headers={"Content-Type": "application/json"},
                        json={"model": model_name, "input": "test"},
                    )
                elif model_type == 'rerank':
                    # 重排模型测试
                    response = await client.post(
                        f"{base_url}/rerank",
                        headers={"Content-Type": "application/json"},
                        json={"model": model_name, "query": "test", "documents": ["test"]},
                    )
                else:
                    # 对话模型测试（默认）
                    response = await client.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key or 'not-needed'}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": "hello"}],
                            "max_tokens": 10,
                        },
                    )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"LLM连接测试成功: modelType={model_type}")
                return {
                    'success': True,
                    'message': '连接测试成功',
                    'model_type': model_type,
                    'response': result,
                }
        
        except httpx.HTTPStatusError as e:
            try:
                error_detail = e.response.json()
                error_msg = error_detail.get('error', {}).get('message', str(e))
            except:
                error_msg = e.response.text[:200] if e.response.text else str(e)
            logger.error(f"LLM连接测试HTTP错误: status={e.response.status_code}, error={error_msg}")
            raise BusinessException(code=400, message=f"连接测试失败(HTTP {e.response.status_code}): {error_msg}")
        except httpx.ConnectError as e:
            logger.error(f"LLM连接测试失败: 无法连接到服务 {base_url}")
            raise BusinessException(code=400, message=f"无法连接到服务: {base_url}")
        except httpx.TimeoutException as e:
            logger.error(f"LLM连接测试失败: 连接超时 {base_url}")
            raise BusinessException(code=400, message=f"连接超时: {base_url}")
        except Exception as e:
            logger.error(f"LLM连接测试失败: {e}")
            raise BusinessException(code=400, message=f"测试失败: {str(e)}")


# 服务实例
llm_config_service = LLMConfigService()
logger.info("LLM配置服务实例已创建")
