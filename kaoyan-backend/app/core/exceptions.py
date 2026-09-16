"""统一异常与全局异常处理。

约定: 出错时响应体固定为
    {"code": <业务码>, "message": "<给用户看的中文提示>", "data": null}
成功时直接返回数据本身(不包外壳), 前端拦截器据此处理。
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """业务异常基类。抛出后由下面的处理器转成统一响应。"""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: int = 40000
    message: str = "请求处理失败"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: int | None = None,
        status_code: int | None = None,
        data: Any = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.data = data
        super().__init__(self.message)


class BadRequestError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    code = 40000
    message = "请求参数不合法"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = 40100
    message = "未登录或登录状态已过期"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = 40300
    message = "没有权限执行该操作"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = 40400
    message = "资源不存在"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = 40900
    message = "资源冲突"


def _body(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}


def register_exception_handlers(app: FastAPI) -> None:
    """把各类异常统一成 {code, message, data} 结构。"""

    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.data),
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 把 pydantic 的字段错误拼成一句人话, 例如: "password: 密码长度至少 6 位"
        details = []
        for err in exc.errors():
            loc = [str(part) for part in err.get("loc", []) if part not in ("body", "query")]
            field = ".".join(loc) or "参数"
            details.append(f"{field}: {err.get('msg', '格式不正确')}")
        message = "; ".join(details) or "参数校验失败"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body(42200, message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.status_code * 100, str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _handle_unknown(_: Request, exc: Exception) -> JSONResponse:
        # 未预期异常: 开发期把原因带出来, 便于联调; 生产环境只给通用提示
        from app.core.config import settings

        message = f"服务器内部错误: {exc}" if settings.DEBUG else "服务器内部错误"
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body(50000, message),
        )
