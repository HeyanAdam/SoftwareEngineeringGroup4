"""轻量键值存储: 优先 Redis, 连不上时退化为进程内字典。

四个用途:
    * 邮箱验证码      code:{purpose}:{email}      TTL 5 分钟, 一次性
    * 登录失败锁定    login:fail:{login_name}     计数 + TTL
    * 已吊销 token    auth:revoked:{sha256}       与原 token 同生命周期
    * 权限缓存版本    rbac:perm:version           自增即可整体失效

设计取舍:
    Redis 挂掉不该导致整个系统不可用, 因此降级为内存实现。
    内存实现只在单进程内有效(多 worker 部署必须让 Redis 真正可用), 会在日志里明确提示。
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Protocol, runtime_checkable

from app.core.config import settings

logger = logging.getLogger("kaoyan.store")


@runtime_checkable
class KVStore(Protocol):
    """存储接口。所有值都是字符串(复杂结构自行 JSON 序列化)。"""

    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttl: int | None = None) -> None: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def incr(self, key: str, ttl: int | None = None) -> int: ...

    def ttl(self, key: str) -> int: ...


class MemoryStore:
    """进程内实现: 带过期时间, 线程安全。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[str, float | None]] = {}
        self._lock = threading.Lock()

    def _read(self, key: str) -> str | None:
        item = self._data.get(key)
        if item is None:
            return None
        value, expire_at = item
        if expire_at is not None and expire_at <= time.time():
            self._data.pop(key, None)
            return None
        return value

    def get(self, key: str) -> str | None:
        with self._lock:
            return self._read(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        expire_at = time.time() + ttl if ttl else None
        with self._lock:
            self._data[key] = (value, expire_at)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def exists(self, key: str) -> bool:
        with self._lock:
            return self._read(key) is not None

    def incr(self, key: str, ttl: int | None = None) -> int:
        with self._lock:
            current = self._read(key)
            value = int(current) + 1 if current else 1
            # 第一次写入时才设置过期, 保证窗口固定(不会因为持续失败而无限延长)
            expire_at = time.time() + ttl if (ttl and not current) else None
            existing = self._data.get(key)
            if existing and existing[1] is not None:
                expire_at = existing[1]
            self._data[key] = (str(value), expire_at)
            return value

    def ttl(self, key: str) -> int:
        with self._lock:
            item = self._data.get(key)
            if item is None or item[1] is None:
                return -1
            return max(0, int(item[1] - time.time()))


class RedisStore:
    """Redis 实现。首次连接失败会抛异常, 由 get_store() 决定是否降级。"""

    def __init__(self, url: str) -> None:
        import redis  # 延迟导入: 没装 redis 时也能用内存实现跑起来

        self._client = redis.Redis.from_url(
            url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
        )
        self._client.ping()

    def get(self, key: str) -> str | None:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: int | None = None) -> None:
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def incr(self, key: str, ttl: int | None = None) -> int:
        value = int(self._client.incr(key))
        if value == 1 and ttl:
            self._client.expire(key, ttl)
        return value

    def ttl(self, key: str) -> int:
        return int(self._client.ttl(key))


_store: KVStore | None = None
_store_lock = threading.Lock()


def get_store() -> KVStore:
    """获取全局存储实例(懒加载, 首次调用时探测 Redis)。"""
    global _store
    if _store is not None:
        return _store
    with _store_lock:
        if _store is not None:
            return _store
        if settings.REDIS_ENABLED:
            try:
                _store = RedisStore(settings.redis_url)
                logger.info("缓存后端: Redis (%s)", settings.redis_url)
                return _store
            except Exception as exc:  # noqa: BLE001  Redis 没启动是常见情况
                logger.warning(
                    "Redis 不可用(%s), 降级为进程内存储; 多 worker 部署请修复 Redis", exc
                )
        _store = MemoryStore()
        logger.info("缓存后端: 进程内存储")
        return _store


def reset_store() -> None:
    """仅供测试使用: 清空单例, 让下一次调用重新探测。"""
    global _store
    with _store_lock:
        _store = None
