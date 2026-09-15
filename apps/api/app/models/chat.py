"""WebSocket 聊天/通知消息持久化模型。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ChatRoom(Base, TimestampMixin):
    __tablename__ = "chat_rooms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(96), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(default=False, nullable=False)

    messages: Mapped[list[ChatMessage]] = relationship(
        back_populates="room", lazy="noload", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatRoom code={self.code!r}>"


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_room_created", "room_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("chat_rooms.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    sender_name: Mapped[str] = mapped_column(String(64), default="system")
    # text / system / file / notify
    kind: Mapped[str] = mapped_column(String(24), default="text", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # 消息来源实例, 便于多副本排查
    source: Mapped[str | None] = mapped_column(String(64))

    room: Mapped[ChatRoom] = relationship(back_populates="messages", lazy="noload")
    sender: Mapped[User | None] = relationship(lazy="noload")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ChatMessage id={self.id} room={self.room_id}>"
