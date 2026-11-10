"""业务模型占位: 上传文件记录。

说明: 业务模块(file)的完整实现不在鉴权交付包内。
这里提供最小表结构, 仅保证 app.models 包可导入、create_all 可执行;
接入真实业务代码时以业务模型为准替换。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import BigIntPK


class UploadFile(Base):
    """上传文件记录(占位表)。"""

    __tablename__ = "upload_file"

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigIntPK, ForeignKey("sys_user.user_id"), index=True, nullable=False
    )
    object_name: Mapped[str] = mapped_column(String(255), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
