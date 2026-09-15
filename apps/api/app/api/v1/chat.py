"""聊天室历史与广播接口 (WebSocket 的 HTTP 补充)。"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.ws import ChatMessageOut, RoomOut, ServerMessage
from app.services.chat import ChatService
from app.ws.manager import manager

router = APIRouter(prefix="/chat", tags=["聊天/通知"])


@router.get("/rooms", response_model=list[RoomOut], summary="聊天室列表")
async def list_rooms(db: DbSession, _: CurrentUser) -> list[RoomOut]:
    return await ChatService(db).list_rooms()


@router.get("/rooms/{room_code}/messages", response_model=list[ChatMessageOut], summary="历史消息")
async def history(
    room_code: str,
    db: DbSession,
    _: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    before_id: int | None = Query(default=None, description="游标: 返回该 id 之前的消息"),
) -> list[ChatMessageOut]:
    return await ChatService(db).history(room_code, limit=limit, before_id=before_id)


@router.get("/online", summary="在线状态 (本实例视角)")
async def online(_: CurrentUser) -> dict[str, object]:
    return {
        "connections": manager.connection_count,
        "rooms": {room: manager.online_count(room) for room in list(manager._rooms)},  # noqa: SLF001
    }


@router.post("/broadcast", summary="向全站推送通知 (需登录)")
async def broadcast(
    _: CurrentUser,
    title: str = Query(min_length=1, max_length=96),
    content: str = Query(default="", max_length=500),
    level: str = Query(default="info", pattern="^(info|success|warning|error)$"),
) -> dict[str, int]:
    payload = ServerMessage(
        type="notification", level=level, title=title, content=content
    ).model_dump(exclude_none=True)
    delivered = await manager.broadcast(None, payload)
    return {"delivered": delivered}
