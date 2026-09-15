"""聊天: HTTP 历史/房间 + WebSocket 收发 (welcome -> chat 往返)。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient
from httpx import AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import settings
from app.main import app
from app.services.chat import DEFAULT_ROOM


async def test_chat_rooms_and_history(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    tokens = await login("viewer1")
    headers = bearer(tokens["access_token"])

    rooms = await client.get(f"{api_prefix}/chat/rooms", headers=headers)
    assert rooms.status_code == 200, rooms.text
    payload = rooms.json()
    assert DEFAULT_ROOM in {room["code"] for room in payload}
    lobby = next(room for room in payload if room["code"] == DEFAULT_ROOM)
    assert lobby["is_default"] is True
    assert lobby["name"]

    history = await client.get(f"{api_prefix}/chat/rooms/{DEFAULT_ROOM}/messages", headers=headers)
    assert history.status_code == 200, history.text
    contents = [message["content"] for message in history.json()]
    assert "seeded message 1" in contents
    assert "seeded message 2" in contents
    # 历史按时间正序返回
    assert contents.index("seeded message 1") < contents.index("seeded message 2")

    limited = await client.get(
        f"{api_prefix}/chat/rooms/{DEFAULT_ROOM}/messages",
        params={"limit": 1},
        headers=headers,
    )
    assert limited.status_code == 200
    assert len(limited.json()) == 1

    unknown_room = await client.get(
        f"{api_prefix}/chat/rooms/does-not-exist/messages", headers=headers
    )
    assert unknown_room.status_code == 200
    assert unknown_room.json() == []

    online = await client.get(f"{api_prefix}/chat/online", headers=headers)
    assert online.status_code == 200
    assert isinstance(online.json()["connections"], int)


async def test_chat_requires_login(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/chat/rooms")

    assert response.status_code == 401


def _receive_until(
    websocket: Any,
    wanted: str,
    predicate: Callable[[dict[str, Any]], bool] | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    """读取消息直到出现期望类型 (welcome / presence / history 会先后到达)。"""
    seen: list[str] = []
    for _ in range(limit):
        payload = websocket.receive_json()
        seen.append(payload.get("type", "?"))
        if payload.get("type") == wanted and (predicate is None or predicate(payload)):
            return payload
    raise AssertionError(f"未收到 {wanted!r} 消息, 实际收到: {seen}")


def test_websocket_welcome_and_chat_roundtrip(seeded: dict[str, Any], test_password: str) -> None:
    """同步 TestClient: WS 连接 -> welcome -> chat 往返 -> ping/pong。"""
    with TestClient(app) as sync_client:
        login = sync_client.post(
            f"{settings.API_V1_PREFIX}/auth/login",
            json={"username": "root", "password": test_password},
        )
        assert login.status_code == 200, login.text
        access_token = login.json()["access_token"]

        with sync_client.websocket_connect(
            f"{settings.WS_PATH}?token={access_token}&room={DEFAULT_ROOM}"
        ) as websocket:
            welcome = _receive_until(websocket, "welcome")
            assert welcome["user"]["username"] == "root"
            assert welcome["user"]["id"] == seeded["users"]["root"]
            assert DEFAULT_ROOM in welcome["rooms"]

            content = f"ws-hello-{uuid.uuid4().hex[:8]}"
            websocket.send_json({"type": "chat", "room": DEFAULT_ROOM, "content": content})
            echoed = _receive_until(
                websocket,
                "chat",
                predicate=lambda payload: payload.get("message", {}).get("content") == content,
            )
            assert echoed["room"] == DEFAULT_ROOM
            assert echoed["message"]["sender_name"] == "root"
            assert echoed["message"]["kind"] == "text"
            assert echoed["message"]["id"]

            websocket.send_json({"type": "ping"})
            pong = _receive_until(websocket, "pong")
            assert isinstance(pong["ts"], int)

            # 非法消息体 -> error 消息, 连接不中断
            websocket.send_json({"type": "nope"})
            error = _receive_until(websocket, "error")
            assert error["content"]


def test_websocket_requires_valid_token() -> None:
    """token 非法 -> 服务端以 1008 关闭连接 (不同 starlette 版本抛出点不同)。"""
    with TestClient(app) as sync_client:
        try:
            with sync_client.websocket_connect(f"{settings.WS_PATH}?token=not-a-jwt") as ws:
                message = ws.receive()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008
        else:
            assert message["type"] == "websocket.close"
            assert message["code"] == 1008
