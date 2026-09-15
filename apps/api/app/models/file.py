"""对象存储文件元数据。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class StoredFile(Base, TimestampMixin):
    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # MinIO 中的对象 key
    object_name: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    bucket: Mapped[str] = mapped_column(String(96), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # 业务分类: avatar / report / attachment ...
    category: Mapped[str] = mapped_column(String(48), default="attachment", index=True)
    status: Mapped[str] = mapped_column(String(24), default="ready", index=True)
    etag: Mapped[str | None] = mapped_column(String(96))
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )

    owner: Mapped[User | None] = relationship(back_populates="files", lazy="noload")

    @property
    def human_size(self) -> str:
        size = float(self.size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
            size /= 1024
        return f"{size:.1f} TB"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StoredFile id={self.id} name={self.original_name!r}>"
