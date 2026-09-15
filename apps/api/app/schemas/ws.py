"""WebSocket 消息协议 Schema (前后端共享契约)。

客户端 -> 服务端
    {"type": "ping"}
    {"type": "join",  "room": "lobby"}
    {"type": "leave", "room": "lobby"}
    {"type": "chat",  "room": "lobby", "content": "hi"}
    {"type": "typing","room": "lobby"}

服务端 -> 客户端
    {"type": "pong",      "ts": 1710000000}
    {"type": "welcome",   "user": {...}, "rooms": [...]}
    {"type": "joined",    "room": "lobby"}
    {"type": "chat",      "room": "lobby", "message": {...}}
    {"type": "presence",  "room": "lobby", "online": 3, "users": [...]}
    {"type": "notification", "level": "info", "title": "...", "content": "..."}
    {"type": "error",     "message": "..."}
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ClientMessageType = Literal["ping", "join", "leave", "chat", "typing"]
ServerMessageType = Literal[
    "pong", "welcome", "joined", "left", "chat", "presence", "notification", "error"
]


class ClientMessage(BaseModel):
    type: ClientMessageType
    room: str | None = Field(default=None, max_length=64)
    content: str | None = Field(default=None, max_length=4000)


class ChatMessageOut(BaseModel):
    id: int | None = None
    room: str
    sender_id: int | None = None
    sender_name: str
    kind: str = "text"
    content: str
    created_at: datetime
    source: str | None = None


class ServerMessage(BaseModel):
    type: ServerMessageType
    ts: int | None = None
    room: str | None = None
    message: ChatMessageOut | None = None
    online: int | None = None
    users: list[str] | None = None
    level: Literal["info", "success", "warning", "error"] | None = None
    title: str | None = None
    content: str | None = None
    user: dict[str, Any] | None = None
    rooms: list[str] | None = None

    def dump(self) -> str:
        return self.model_dump_json(exclude_none=True, by_alias=True)


class RoomOut(BaseModel):
    id: int
    code: str
    name: str
    description: str | None = None
    is_default: bool = False
