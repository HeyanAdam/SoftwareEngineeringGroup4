"""聊天室 / 消息持久化服务。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.chat import ChatMessage, ChatRoom
from app.schemas.ws import ChatMessageOut, RoomOut

DEFAULT_ROOM = "lobby"


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ----------------------------- 房间 -----------------------------
    async def list_rooms(self) -> list[RoomOut]:
        rows = (
            (
                await self.db.execute(
                    select(ChatRoom).order_by(ChatRoom.is_default.desc(), ChatRoom.id)
                )
            )
            .scalars()
            .all()
        )
        return [
            RoomOut(
                id=room.id,
                code=room.code,
                name=room.name,
                description=room.description,
                is_default=room.is_default,
            )
            for room in rows
        ]

    async def get_or_create_room(self, code: str) -> ChatRoom:
        room = (
            await self.db.execute(select(ChatRoom).where(ChatRoom.code == code))
        ).scalar_one_or_none()
        if room is not None:
            return room
        room = ChatRoom(code=code, name=code, is_default=code == DEFAULT_ROOM)
        self.db.add(room)
        await self.db.commit()
        await self.db.refresh(room)
        return room

    # ----------------------------- 消息 -----------------------------
    async def save_message(
        self,
        *,
        room_code: str,
        content: str,
        sender_id: int | None,
        sender_name: str,
        kind: str = "text",
        source: str | None = None,
    ) -> ChatMessageOut:
        room = await self.get_or_create_room(room_code)
        message = ChatMessage(
            room_id=room.id,
            sender_id=sender_id,
            sender_name=sender_name,
            kind=kind,
            content=content,
            source=source,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return self.to_out(message, room_code)

    async def history(
        self, room_code: str, *, limit: int = 50, before_id: int | None = None
    ) -> list[ChatMessageOut]:
        room = (
            await self.db.execute(select(ChatRoom).where(ChatRoom.code == room_code))
        ).scalar_one_or_none()
        if room is None:
            return []
        stmt = select(ChatMessage).where(ChatMessage.room_id == room.id)
        if before_id:
            stmt = stmt.where(ChatMessage.id < before_id)
        rows = (
            (await self.db.execute(stmt.order_by(ChatMessage.id.desc()).limit(limit)))
            .scalars()
            .all()
        )
        return [self.to_out(m, room_code) for m in reversed(rows)]

    async def message_count(self) -> int:
        return int(
            (await self.db.execute(select(func.count()).select_from(ChatMessage))).scalar_one() or 0
        )

    async def delete_message(self, message_id: int) -> None:
        message = await self.db.get(ChatMessage, message_id)
        if message is None:
            raise NotFoundError("消息不存在")
        await self.db.delete(message)
        await self.db.commit()

    @staticmethod
    def to_out(message: ChatMessage, room_code: str) -> ChatMessageOut:
        return ChatMessageOut(
            id=message.id,
            room=room_code,
            sender_id=message.sender_id,
            sender_name=message.sender_name,
            kind=message.kind,
            content=message.content,
            created_at=message.created_at,
            source=message.source,
        )
