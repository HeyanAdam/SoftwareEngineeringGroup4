"""审计日志模型: sys_audit_log。

《权限表》五张表里没有审计表, 这一张是按禅道「操作日志」补的,
用于回看角色、权限、用户与登录相关的变更(见 docs/改造说明.md 第 3 节扩展说明)。

只记录鉴权/授权相关的动作, 不记录业务读写 —— 否则数据量会失控。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.types import BigIntPK


class AuditLog(Base):
    """操作审计表 sys_audit_log。"""

    __tablename__ = "sys_audit_log"
    __table_args__ = (
        Index("ix_audit_action", "action"),
        Index("ix_audit_create_time", "create_time"),
    )

    id: Mapped[int] = mapped_column(BigIntPK, primary_key=True, autoincrement=True, comment="日志编号")
    user_id: Mapped[int | None] = mapped_column(BigInteger, comment="操作者 user_id, 登录失败等场景为空")
    login_name: Mapped[str | None] = mapped_column(String(50), comment="操作者登录名")
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="动作标识, 如 role.create / login.failure"
    )
    target_type: Mapped[str | None] = mapped_column(
        String(30), comment="目标类型, 如 role/user/session"
    )
    target_id: Mapped[str | None] = mapped_column(String(50), comment="目标编号")
    detail: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="变更详情, 只放前后差异, 不留密码等敏感值"
    )
    ip: Mapped[str | None] = mapped_column(String(64), comment="来源 IP")
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("1"), comment="是否成功"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
        comment="操作时间",
    )
