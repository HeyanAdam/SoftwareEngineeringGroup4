"""WebSocket 端点: /ws?token=<access_token>

支持的消息类型见 app.schemas.ws 顶部注释 (前后端共享契约)。
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.exceptions import AppError
from app.core.logging import bind_request_id, get_logger
from app.core.security import decode_token
from app.schemas.ws import ChatMessageOut, ClientMessage, ServerMessage
from app.services.auth import AuthService
from app.services.chat import DEFAULT_ROOM, ChatService
from app.ws.manager import INSTANCE_ID, manager

logger = get_logger("ws")
router = APIRouter()


async def _authenticate(token: str | None) -> dict[str, Any]:
    if not token:
        raise AppError("缺少 token 参数", code=40100, status_code=status.WS_1008_POLICY_VIOLATION)
    payload = decode_token(token, expected_type="access")
    async with AsyncSessionLocal() as db:
        user = await AuthService(db).get_active_user(int(payload["sub"]))
        return {"id": user.id, "username": user.username, "is_superuser": user.is_superuser}


@router.websocket(settings.WS_PATH)
async def websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None, description="访问令牌"),
    room: str = Query(default=DEFAULT_ROOM, max_length=64),
) -> None:
    bind_request_id()
    try:
        user = await _authenticate(token)
    except AppError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=exc.message)
        return
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws_auth_failed", error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="认证失败")
        return

    user_id: int = user["id"]
    username: str = user["username"]
    await manager.connect(user_id, websocket, meta=user)

    async with AsyncSessionLocal() as db:
        chat = ChatService(db)
        rooms = await chat.list_rooms()
        history = await chat.history(room, limit=30)

    await manager.join(user_id, room)
    await manager.send_personal(
        user_id,
        ServerMessage(
            type="welcome",
            ts=int(time.time()),
            user=user,
            rooms=[r.code for r in rooms] or [DEFAULT_ROOM],
            message=None,
        ).dump(),
    )
    for item in history:
        await manager.send_personal(
            user_id, ServerMessage(type="chat", room=room, message=item).dump()
        )
    await _broadcast_presence(room)

    idle_timeout = settings.WS_HEARTBEAT_SECONDS * 2
    try:
        while True:
            try:
                raw = await asyncio.wait_for(websocket.receive_text(), timeout=idle_timeout)
            except TimeoutError:
                # 客户端静默过久: 主动 ping 探活
                await websocket.send_text(ServerMessage(type="pong", ts=int(time.time())).dump())
                continue

            if len(raw) > settings.WS_MAX_MESSAGE_BYTES:
                await manager.send_personal(
                    user_id, ServerMessage(type="error", content="消息体过大").dump()
                )
                continue

            try:
                message = ClientMessage.model_validate_json(raw)
            except ValidationError as exc:
                await manager.send_personal(
                    user_id,
                    ServerMessage(
                        type="error", content=f"消息格式错误: {exc.error_count()} 处"
                    ).dump(),
                )
                continue

            await _handle(user_id, username, message, room)

    except WebSocketDisconnect:
        logger.info("ws_disconnected", user_id=user_id, username=username)
    except Exception as exc:  # noqa: BLE001
        logger.warning("ws_error", user_id=user_id, error=str(exc))
    finally:
        rooms_of_user = manager.rooms_of(user_id)
        await manager.disconnect(user_id)
        for code in rooms_of_user or {room}:
            await _broadcast_presence(code)


async def _handle(user_id: int, username: str, message: ClientMessage, default_room: str) -> None:
    match message.type:
        case "ping":
            await manager.send_personal(
                user_id, ServerMessage(type="pong", ts=int(time.time())).dump()
            )

        case "join":
            target = message.room or default_room
            await manager.join(user_id, target)
            await manager.send_personal(
                user_id, ServerMessage(type="joined", room=target, ts=int(time.time())).dump()
            )
            await _broadcast_presence(target)

        case "leave":
            target = message.room or default_room
            await manager.leave(user_id, target)
            await manager.send_personal(
                user_id, ServerMessage(type="left", room=target, ts=int(time.time())).dump()
            )
            await _broadcast_presence(target)

        case "typing":
            target = message.room or default_room
            await manager.broadcast(
                target,
                {
                    "type": "notification",
                    "level": "info",
                    "title": "typing",
                    "content": f"{username} 正在输入...",
                    "room": target,
                },
            )

        case "chat":
            content = (message.content or "").strip()
            if not content:
                await manager.send_personal(
                    user_id, ServerMessage(type="error", content="消息内容不能为空").dump()
                )
                return
            target = message.room or default_room
            if target not in manager.rooms_of(user_id):
                await manager.join(user_id, target)
            async with AsyncSessionLocal() as db:
                saved: ChatMessageOut = await ChatService(db).save_message(
                    room_code=target,
                    content=content[:4000],
                    sender_id=user_id,
                    sender_name=username,
                    kind="text",
                    source=INSTANCE_ID,
                )
            await manager.broadcast(
                target, {"type": "chat", "room": target, "message": saved.model_dump(mode="json")}
            )


async def _broadcast_presence(room: str) -> None:
    payload = {
        "type": "presence",
        "room": room,
        "online": manager.online_count(room),
        "users": manager.online_users(room),
    }
    await manager.broadcast(room, payload)


@contextlib.asynccontextmanager
async def lifespan_ws():
    """预留给需要独立生命周期的场景 (当前由 main.lifespan 管理)。"""
    yield
