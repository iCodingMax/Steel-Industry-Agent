"""
全局异常处理中间件
"""
from typing import Any, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class BusinessException(Exception):
    """业务异常基类"""

    def __init__(self, code: int = 400, message: str = "业务异常", data: Any = None):
        self.code = code
        self.message = message
        self.data = data
        super().__init__(message)


async def custom_exception_handler(request: Request, exc: BusinessException) -> JSONResponse:
    """自定义业务异常处理"""
    return JSONResponse(
        status_code=200,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        },
    )


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全局异常处理"""
    logger.exception(f"未捕获的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "服务器内部错误",
            "data": None,
        },
    )


def success_response(data: Any = None, message: str = "success") -> Dict[str, Any]:
    """统一成功响应格式"""
    return {
        "code": 0,
        "message": message,
        "data": data,
    }


def error_response(code: int = 400, message: str = "error", data: Any = None) -> Dict[str, Any]:
    """统一错误响应格式"""
    return {
        "code": code,
        "message": message,
        "data": data,
    }
