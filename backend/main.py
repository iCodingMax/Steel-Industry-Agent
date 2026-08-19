"""
工业智能助手平台 - FastAPI 应用入口

职责：创建 FastAPI 应用实例，注册中间件/异常处理/路由，管理应用生命周期。

架构模式：
  1. 工厂模式 —— create_app() 构建并返回 FastAPI 实例
  2. 生命周期管理 —— lifespan 异步上下文管理器处理启动/关闭
  3. 延迟导入 —— lifespan 内部延迟导入 auth_service 和 seed_data，避免循环依赖

启动流程（按顺序执行）：
  init_db()                → 初始化 PostgreSQL 表结构 + 自动迁移缺失列
  init_default_admin()     → 创建默认管理员账号（首次启动）
  seed()                   → 填充种子数据（LLM配置、示例知识库等）
  yield                    → 交还控制权，FastAPI 开始接收 HTTP 请求
  engine.dispose()         → 应用关闭时释放数据库连接池
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.core.database import init_db
from app.api.v1 import api_router
from app.middlewares.exception_handler import (
    custom_exception_handler,
    global_exception_handler,
    BusinessException,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理（FastAPI 0.93+ 推荐方式，替代 @app.on_event）

    yield 之前 = 启动阶段：初始化数据库、创建管理员、填充种子数据
    yield 之后 = 关闭阶段：释放数据库连接池
    """
    logger.info("=" * 60)
    logger.info("工业智能助手平台启动中...")
    logger.info(f"运行环境: {settings.ENV}")
    logger.info("=" * 60)

    # 第一步：初始化数据库表结构（create_all + _auto_add_columns 增量迁移）
    await init_db()

    # 第二步：创建默认管理员账号（延迟导入避免循环依赖）
    from app.services.auth_service import auth_service
    from app.core.database import SystemAsyncSession
    async with SystemAsyncSession() as db:
        await auth_service.init_default_admin(db)

    # 第三步：填充种子数据（LLM配置、示例知识库等）
    from seed_data import seed
    await seed()

    logger.success("系统启动成功!")

    # ===== 启动阶段结束，交还控制权给 FastAPI =====
    yield
    # ===== 以下为关闭阶段 =====

    logger.info("系统正在关闭，释放数据库资源...")
    from app.core.database import engine
    await engine.dispose()  # 关闭 SQLAlchemy 异步引擎连接池，释放所有数据库连接
    logger.success("资源释放完成")

def create_app() -> FastAPI:
    """
    创建FastAPI应用实例（工厂模式）

    注册顺序很重要：
      1. CORS 中间件 —— 跨域资源共享，允许前端 http://localhost:5173 访问
      2. 异常处理器 —— BusinessException 用 HTTP 200 + code 封装，兜底 Exception 用 HTTP 500
      3. 路由注册 —— 所有 /api/v1 前缀的接口挂载到 app
      4. 健康检查 —— 独立于 /api/v1 的 /health 端点，用于容器编排探活
    """
    app = FastAPI(
        title="Industrial Intelligent Assistant Platform API",
        description="工业智能助手平台 - RAG + ChatBI 融合推理",
        version="0.1.0",
        lifespan=lifespan,
    )

    # 注册 CORS 中间件：允许前端开发服务器跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册两层异常处理器：
    #   BusinessException → HTTP 200 + {code, message, data}（业务错误不中断连接）
    #   Exception → HTTP 500（未捕获的异常，记录完整堆栈）
    app.add_exception_handler(BusinessException, custom_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)

    # 挂载所有 v1 API 路由（chat/knowledge/chatbi/tool/application 等）
    app.include_router(api_router, prefix=settings.API_PREFIX)

    # 健康检查端点（独立于 /api/v1，供 Docker/K8s 探活使用）
    @app.get("/health", summary="健康检查")
    async def health_check():
        return {"status": "ok", "service": "steel-industry-agent"}

    return app

# ===== 应用实例化与运行入口 =====
app = create_app()

if __name__ == "__main__":
    # 开发环境直接运行（生产环境用 uvicorn 命令行启动）
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        timeout_graceful_shutdown=3,
    )
