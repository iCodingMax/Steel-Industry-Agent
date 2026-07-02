"""
Redis 连接管理
"""
from typing import Optional
import redis.asyncio as redis
from loguru import logger

from app.core.config import settings

_redis_client: Optional[redis.Redis] = None
redis_client = None  # 兼容直接导入


async def get_redis_client() -> redis.Redis:
    """获取Redis客户端（单例模式）"""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await _redis_client.ping()
            logger.success("Redis 连接成功")
        except Exception as e:
            logger.warning(f"Redis 连接失败（首次启动可忽略）: {e}")
    return _redis_client


async def close_redis() -> None:
    """关闭Redis连接"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis 连接已关闭")
