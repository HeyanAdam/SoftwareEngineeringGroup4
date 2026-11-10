"""用户业务档案表 user_account(权限表 ER 图中的业务主表)。

权限表把「登录账号」和「考研业务画像」拆成两张表:
    sys_user     只管登录凭证(user_id / login_name / password / account_status / create_time)
    user_account 管业务画像, 字段与 ER 图一一对应, 未做任何增删

原项目 users 表里的画像字段按下面的映射迁到这里(映射依据是你给的 ER 图):
    nickname      -> user_account.user_name      用户昵称
    target_major  -> user_account.major          报考专业名称
    target_school -> user_account.target_school_id   目标院校编号(院校主表属择校模块, 本次不建)

没有对应列的两个字段(考试年份、目标院校名称)已删除, 个人中心表单同步改为
ER 原生字段: 昵称 / 本科专业 / 报考专业 / 目标地区 / 备考阶段 / 目标分数。
"""


from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.types import BigIntPK

if TYPE_CHECKING:  # pragma: no cover
    from app.models.user import User


class UserAccount(Base):
    """业务档案: 与 sys_user 一对一(user_id 既是主键也是外键)。"""

    __tablename__ = "user_account"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("sys_user.user_id", ondelete="CASCADE"),
        primary_key=True,
        comment="学生业务主键, 关联 sys_user.user_id",
    )
    user_name: Mapped[str] = mapped_column(
        String(50), nullable=False, default="", comment="用户昵称(原 nickname)"
    )
    undergraduate_major: Mapped[str | None] = mapped_column(
        String(60), comment="本科专业"
    )
    target_area: Mapped[str | None] = mapped_column(String(30), comment="目标报考地区")
    target_school_id: Mapped[int | None] = mapped_column(
        BigIntPK, comment="目标院校编号, 由择校模块的院校主表提供"
    )
    prep_stage: Mapped[str | None] = mapped_column(String(20), comment="备考阶段")
    base_level: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, comment="各科目基础水平, 形如 {科目: 等级}"
    )
    remain_days: Mapped[int | None] = mapped_column(Integer, comment="备考剩余天数")
    target_score: Mapped[int | None] = mapped_column(Integer, comment="目标考试分数")
    digital_person_mode: Mapped[str | None] = mapped_column(
        String(20), comment="数字人教学模式"
    )
    create_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"), comment="账号创建时间"
    )

    major: Mapped[str | None] = mapped_column(String(100), comment="报考专业名称(原 target_major)")

    user: Mapped["User"] = relationship(back_populates="account")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserAccount user_id={self.user_id} user_name={self.user_name!r}>"
