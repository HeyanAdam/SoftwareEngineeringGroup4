"""Redis 缓存装饰器与失效助手。"""

from __future__ import annotations

import functools
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)
F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def cache_key(prefix: str, *parts: Any) -> str:
    raw = ":".join(str(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"cache:{prefix}:{digest}"


def cached(prefix: str, ttl: int | None = None, *, key_args: tuple[int, ...] | None = None):
    """异步函数结果缓存 (Redis 故障时自动降级为直连)。"""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            picked = args[1:] if key_args is None else tuple(args[i] for i in key_args)
            key = cache_key(prefix, *picked, *sorted(kwargs.items()))
            redis = get_redis()
            try:
                hit = await redis.get(key)
                if hit is not None:
                    return json.loads(hit)
            except Exception as exc:  # noqa: BLE001
                logger.debug("cache_read_skipped", error=str(exc))

            result = await func(*args, **kwargs)
            try:
                await redis.set(
                    key, json.dumps(result, default=str), ex=ttl or settings.CACHE_TTL_SECONDS
                )
            except Exception as exc:  # noqa: BLE001
                logger.debug("cache_write_skipped", error=str(exc))
            return result

        return wrapper  # type: ignore[return-value]

    return decorator


async def invalidate(prefix: str) -> int:
    """按前缀清理缓存 (SCAN, 避免 KEYS 阻塞)。"""
    redis = get_redis()
    removed = 0
    try:
        async for key in redis.scan_iter(match=f"cache:{prefix}:*", count=200):
            await redis.delete(key)
            removed += 1
    except Exception as exc:  # noqa: BLE001
        logger.warning("cache_invalidate_failed", prefix=prefix, error=str(exc))
    return removed
