"""统一异常类型与全局异常处理。

约定: 所有错误响应统一返回 ``{code, message, data}`` 结构,
业务代码一律 raise 下面的异常, 不直接 return JSONResponse。

本文件属于 FastAPI 工程底座, 鉴权改造包未携带, 按调用方
(AppError / BadRequestError / UnauthorizedError / ForbiddenError /
NotFoundError / ConflictError / register_exception_handlers)补齐。
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("kaoyan.exceptions")


class AppError(Exception):
    """业务异常基类: status_code 决定 HTTP 状态码, message 面向用户。

    code 默认取 status_code, 需要细分业务错误码(如验证码 40010)时显式传入。
    """

    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(
        self,
        message: str = "请求失败",
        *,
        code: int | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code

    @property
    def error_code(self) -> int:
        return getattr(self, "code", None) or self.status_code


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str = "请求参数有误") -> None:
        super().__init__(message)


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, message: str = "请先登录") -> None:
        super().__init__(message)


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN

    def __init__(self, message: str = "没有权限执行该操作") -> None:
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND

    def __init__(self, message: str = "资源不存在") -> None:
        super().__init__(message)


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT

    def __init__(self, message: str = "资源冲突") -> None:
        super().__init__(message)


class CaptchaError(AppError):
    """图形验证码缺失 / 错误 / 过期。前端按 code=40010 弹出验证码输入框。"""

    status_code = status.HTTP_400_BAD_REQUEST
    code = 40010

    def __init__(self, message: str = "请先完成图形验证") -> None:
        super().__init__(message)


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器, 把异常统一翻译成 {code, message, data}。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.error_code, "message": exc.message, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 只取第一条错误, 拼成「字段: 原因」的友好提示
        message = "参数校验失败"
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
            msg = str(first.get("msg", ""))
            message = f"{loc}: {msg}" if loc else msg
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"code": 422, "message": message, "data": None},
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"code": 500, "message": "服务器内部错误", "data": None},
        )
