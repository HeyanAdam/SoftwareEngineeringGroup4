"""HTTP 中间件: 请求 ID / 访问日志 / 耗时统计。"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import bind_request_id, get_logger

logger = get_logger("http")

SKIP_PATHS = ("/metrics", "/api/v1/health/live", "/api/v1/health/ready", "/favicon.ico")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        incoming = request.headers.get("x-request-id")
        request_id = bind_request_id(incoming)
        request.state.request_id = request_id

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            cost_ms = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
                cost_ms=cost_ms,
            )
            raise

        cost_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(cost_ms)

        if request.url.path not in SKIP_PATHS:
            logger.info(
                "request",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                cost_ms=cost_ms,
                client=request.client.host if request.client else "-",
            )
        return response
