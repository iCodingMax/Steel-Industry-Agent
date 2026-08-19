"""
全局异常处理中间件

职责：统一所有 API 的响应格式为 {code, message, data} 信封结构。
     业务异常用 HTTP 200 + 错误码（不中断连接），系统异常用 HTTP 500。

两层异常处理策略：
  1. BusinessException（业务异常）→ HTTP 200 + {code, message, data}
     前端通过 res.code !== 0 判断错误，可正常读取 message 展示给用户
     适用场景：参数校验失败、权限不足、资源不存在等可预期错误
  2. Exception（系统异常）→ HTTP 500 + {code: 500, message, data: null}
     记录完整异常堆栈，返回通用错误信息
     适用场景：数据库连接失败、代码 bug 等不可预期错误

统一响应格式：
  成功：{ "code": 0, "message": "success", "data": {...} }
  失败：{ "code": 404, "message": "会话不存在", "data": null }
"""
from typing import Any, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class BusinessException(Exception):
    """
    业务异常基类

    使用方式：raise BusinessException(code=404, message="会话不存在")
    被捕获后转换为 HTTP 200 响应，前端通过 code 字段判断是否成功。
    """

    def __init__(self, code: int = 400, message: str = "业务异常", data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


async def custom_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    """
    业务异常处理器

    注意：HTTP status_code 始终为 200，错误信息编码在响应体 code 字段中。
    这样设计是因为前端 axios 拦截器统一检查 res.code !== 0 判断错误，
    如果返回 4xx/5xx，axios 会直接进入 catch 分支，无法统一处理。
    """
    return JSONResponse(
        status_code=200,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    全局兜底异常处理器

    捕获所有未被 BusinessException 覆盖的异常（如 TypeError、KeyError 等）。
    记录完整堆栈日志（logger.exception 包含 traceback），便于排查。
    返回 HTTP 500 + 通用错误信息，不暴露内部细节给前端。
    """
    logger.exception(f"未捕获的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": f"服务器内部错误: {str(exc)}",
            "data": None,
        },
    )


def success_response(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """
    统一成功响应格式

    所有 API 路由成功时调用此函数返回：
      return success_response(data=sessions_list)
    """
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error_response(code: int = 400, message: str = "error", data: Any = None) -> Dict[str, Any]:
    """
    统一错误响应格式（与 success_response 对称，用于非异常场景的错误返回）
    """
    return {
        "code": code,
        "message": message,
        "data": data,
    }
