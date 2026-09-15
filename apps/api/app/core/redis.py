"""Redis 异步客户端 (缓存 / 限流 / Pub-Sub 广播)。"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings

_pool: ConnectionPool | None = None


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            health_check_interval=30,
        )
    return _pool


def get_redis() -> Redis:
    """返回共享连接池上的 Redis 客户端 (线程/任务安全)。"""
    return Redis(connection_pool=get_pool())


async def redis_dependency() -> AsyncGenerator[Redis, None]:
    client = get_redis()
    try:
        yield client
    finally:
        await client.aclose()


async def ping() -> bool:
    try:
        return bool(await get_redis().ping())
    except Exception:  # noqa: BLE001
        return False


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
