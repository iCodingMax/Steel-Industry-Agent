"""
健康检查API
"""
from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from loguru import logger

from app.core.database import SystemAsyncSession, PGVectorAsyncSession
from app.core.redis_client import redis_client
from app.models.user import User

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check():
    """健康检查"""
    checks = {
        "service": {"status": "healthy", "message": "Industrial Intelligent Assistant Platform"},
        "database": {"status": "unknown", "message": ""},
        "redis": {"status": "unknown", "message": ""},
        "postgres": {"status": "unknown", "message": ""},
    }

    try:
        async with SystemAsyncSession() as db:
            await db.execute(select(User).limit(1))
        checks["database"] = {"status": "healthy", "message": "PostgreSQL连接正常"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "message": str(e)}
        logger.error(f"PostgreSQL健康检查失败: {e}")

    try:
        if redis_client:
            await redis_client.ping()
            checks["redis"] = {"status": "healthy", "message": "Redis连接正常"}
        else:
            checks["redis"] = {"status": "unhealthy", "message": "Redis未初始化"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "message": str(e)}
        logger.error(f"Redis健康检查失败: {e}")

    try:
        async with PGVectorAsyncSession() as db:
            await db.execute(select(1))
        checks["postgres"] = {"status": "healthy", "message": "PostgreSQL向量库连接正常"}
    except Exception as e:
        checks["postgres"] = {"status": "unhealthy", "message": str(e)}
        logger.error(f"PostgreSQL向量库健康检查失败: {e}")

    overall_status = "healthy" if all(
        check["status"] == "healthy" for check in checks.values()
    ) else "unhealthy"

    return {
        "status": overall_status,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": checks,
    }


@router.get("/ready")
async def readiness_check():
    """就绪检查 - 用于K8s就绪探针"""
    result = await health_check()
    if result["status"] == "healthy":
        return {"status": "ready"}
    return {"status": "not_ready"}, 503


@router.get("/live")
async def liveness_check():
    """存活检查 - 用于K8s存活探针"""
    return {"status": "alive"}
