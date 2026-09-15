"""Redis 计数限流 (滑动窗口)。"""

from __future__ import annotations

import time

from fastapi import Request

from app.core.config import settings
from app.core.exceptions import RateLimitError
from app.core.redis import get_redis


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def hit(key: str, limit: int, window_seconds: int = 60) -> tuple[int, int]:
    """返回 (当前计数, 剩余秒数); Redis 不可用时放行。"""
    redis = get_redis()
    bucket = f"rl:{key}:{int(time.time()) // window_seconds}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(bucket)
            pipe.expire(bucket, window_seconds + 1)
            count, _ = await pipe.execute()
        return int(count), window_seconds
    except Exception:  # noqa: BLE001  Redis 故障不应阻断业务
        return 0, 0


async def check_rate_limit(
    request: Request, *, limit: int | None = None, scope: str = "global"
) -> None:
    max_requests = limit or settings.RATE_LIMIT_PER_MINUTE
    count, _ = await hit(f"{scope}:{client_ip(request)}", max_requests)
    if count and count > max_requests:
        raise RateLimitError(f"每分钟最多 {max_requests} 次请求")
