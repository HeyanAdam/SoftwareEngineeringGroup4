"""WebSocket 连接管理 + Redis Pub/Sub 跨实例广播。

单实例: 直接遍历本地连接推送。
多实例: publish 到 Redis channel, 每个实例订阅后只推给本地连接 (天然水平扩展)。
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket
from redis.asyncio.client import PubSub

from app.core.logging import get_logger
from app.core.redis import get_redis

logger = get_logger(__name__)

BROADCAST_CHANNEL = "ws:broadcast"
# 单实例标识, 用于避免自己发出的广播被自己重复消费
INSTANCE_ID = f"api-{uuid.uuid4().hex[:8]}"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[int, WebSocket] = {}
        self._rooms: dict[str, set[int]] = defaultdict(set)
        self._user_rooms: dict[int, set[str]] = defaultdict(set)
        self._meta: dict[int, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # ----------------------------- 生命周期 -----------------------------
    async def connect(
        self, user_id: int, websocket: WebSocket, meta: dict[str, Any] | None = None
    ) -> None:
        await websocket.accept()
        async with self._lock:
            previous = self._connections.get(user_id)
            self._connections[user_id] = websocket
            self._meta[user_id] = meta or {}
        if previous is not None:
            with contextlib.suppress(Exception):
                await previous.close(code=4001)

    async def disconnect(self, user_id: int) -> None:
        async with self._lock:
            self._connections.pop(user_id, None)
            self._meta.pop(user_id, None)
            for room in self._user_rooms.pop(user_id, set()):
                self._rooms.get(room, set()).discard(user_id)
                if not self._rooms.get(room):
                    self._rooms.pop(room, None)

    # ----------------------------- 房间 -----------------------------
    async def join(self, user_id: int, room: str) -> None:
        async with self._lock:
            self._rooms[room].add(user_id)
            self._user_rooms[user_id].add(room)

    async def leave(self, user_id: int, room: str) -> None:
        async with self._lock:
            self._rooms.get(room, set()).discard(user_id)
            self._user_rooms.get(user_id, set()).discard(room)

    def rooms_of(self, user_id: int) -> set[str]:
        return set(self._user_rooms.get(user_id, set()))

    def online_count(self, room: str | None = None) -> int:
        return len(self._rooms.get(room, set())) if room else len(self._connections)

    def online_users(self, room: str | None = None) -> list[str]:
        ids = self._rooms.get(room, set()) if room else set(self._connections.keys())
        return sorted({str(self._meta.get(uid, {}).get("username", uid)) for uid in ids})

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    # ----------------------------- 发送 -----------------------------
    async def send_personal(self, user_id: int, payload: dict[str, Any] | str) -> bool:
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False, default=str)
        )
        try:
            await ws.send_text(text)
            return True
        except Exception:  # noqa: BLE001
            await self.disconnect(user_id)
            return False

    async def send_local_room(self, room: str, payload: dict[str, Any] | str) -> int:
        members = list(self._rooms.get(room, set()))
        if not members:
            return 0
        text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False, default=str)
        )
        results = await asyncio.gather(
            *(self.send_personal(uid, text) for uid in members), return_exceptions=True
        )
        return sum(1 for r in results if r is True)

    # ----------------------------- 广播 -----------------------------
    async def broadcast(self, room: str | None, payload: dict[str, Any]) -> int:
        """跨实例广播: 先本地推, 再 publish 给其它实例。"""
        delivered = await self.send_local_room(room, payload) if room else 0
        if room is None:
            delivered = await self.send_local_room_all(payload)
        envelope = {"origin": INSTANCE_ID, "room": room, "payload": payload}
        try:
            await get_redis().publish(
                BROADCAST_CHANNEL, json.dumps(envelope, ensure_ascii=False, default=str)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws_publish_failed", error=str(exc))
        return delivered

    async def send_local_room_all(self, payload: dict[str, Any] | str) -> int:
        text = (
            payload
            if isinstance(payload, str)
            else json.dumps(payload, ensure_ascii=False, default=str)
        )
        results = await asyncio.gather(
            *(self.send_personal(uid, text) for uid in list(self._connections)),
            return_exceptions=True,
        )
        return sum(1 for r in results if r is True)

    async def apply_remote(self, envelope: dict[str, Any]) -> None:
        """处理其它实例发来的广播 (跳过自己的)。"""
        if envelope.get("origin") == INSTANCE_ID:
            return
        payload = envelope.get("payload") or {}
        room = envelope.get("room")
        if room:
            await self.send_local_room(room, payload)
        else:
            await self.send_local_room_all(payload)


manager = ConnectionManager()


async def pubsub_listener(stop_event: asyncio.Event) -> None:
    """后台任务: 订阅 Redis 广播频道, 直到 stop_event 被设置。"""
    redis = get_redis()
    pubsub: PubSub = redis.pubsub()
    try:
        await pubsub.subscribe(BROADCAST_CHANNEL)
        logger.info("ws_pubsub_subscribed", channel=BROADCAST_CHANNEL, instance=INSTANCE_ID)
        while not stop_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                await asyncio.sleep(0.05)
                continue
            data = message.get("data")
            if not data:
                continue
            try:
                await manager.apply_remote(json.loads(data))
            except json.JSONDecodeError:
                logger.warning("ws_pubsub_bad_payload")
    except asyncio.CancelledError:  # pragma: no cover
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error("ws_pubsub_error", error=str(exc))
    finally:
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(BROADCAST_CHANNEL)
            await pubsub.aclose()
