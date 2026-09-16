"""用户模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """用户账号 + 考研画像字段。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # 画像信息(注册后可在个人中心补充)
    nickname: Mapped[str | None] = mapped_column(String(50))
    target_school: Mapped[str | None] = mapped_column(String(100), comment="目标院校")
    target_major: Mapped[str | None] = mapped_column(String(100), comment="目标专业")
    exam_year: Mapped[int | None] = mapped_column(Integer, comment="考试年份, 如 2027")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    @property
    def display_name(self) -> str:
        """优先展示昵称, 没有则用用户名。"""
        return self.nickname or self.username

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} username={self.username!r}>"
