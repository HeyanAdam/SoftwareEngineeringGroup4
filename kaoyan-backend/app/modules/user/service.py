"""用户模块业务逻辑。"""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models.user import User


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------
    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username_or_email(self, identity: str) -> User | None:
        stmt = select(User).where(
            or_(User.username == identity, User.email == identity.lower())
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def username_taken(self, username: str) -> bool:
        return (
            self.db.execute(select(User.id).where(User.username == username)).first()
            is not None
        )

    def email_taken(self, email: str) -> bool:
        return (
            self.db.execute(select(User.id).where(User.email == email.lower())).first()
            is not None
        )

    # ------------------------------------------------------------------
    def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        nickname: str | None = None,
    ) -> User:
        if self.username_taken(username):
            raise ConflictError("该用户名已被注册")
        if self.email_taken(email):
            raise ConflictError("该邮箱已被注册")

        user = User(
            username=username,
            email=email.lower(),
            password_hash=hash_password(password),
            nickname=nickname or username,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate(self, identity: str, password: str) -> User:
        """登录校验: 用户名或邮箱 + 密码。"""
        user = self.get_by_username_or_email(identity)
        # 用户不存在与密码错误返回同样的提示, 避免暴露账号是否注册
        if user is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("用户名或密码错误")
        if not user.is_active:
            raise UnauthorizedError("账号已被禁用, 请联系管理员")
        return user

    def update_profile(
        self,
        user: User,
        *,
        nickname: str | None = None,
        target_school: str | None = None,
        target_major: str | None = None,
        exam_year: int | None = None,
    ) -> User:
        """只更新传了的字段(None 表示不改)。"""
        if nickname is not None:
            user.nickname = nickname
        if target_school is not None:
            user.target_school = target_school
        if target_major is not None:
            user.target_major = target_major
        if exam_year is not None:
            user.exam_year = exam_year
        self.db.commit()
        self.db.refresh(user)
        return user
