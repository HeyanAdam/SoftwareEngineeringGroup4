"""认证与用户相关 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field, field_validator

from app.core.config import settings
from app.schemas.common import ORMModel


class LoginRequest(ORMModel):
    username: str = Field(min_length=3, max_length=64, description="用户名或邮箱")
    password: str = Field(min_length=1, max_length=128)


class RegisterRequest(ORMModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=64)

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, value: str) -> str:
        if len(value) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"密码至少 {settings.PASSWORD_MIN_LENGTH} 位")
        if value.isdigit() or value.isalpha():
            raise ValueError("密码需同时包含字母和数字")
        return value


class RefreshRequest(ORMModel):
    refresh_token: str


class TokenPair(ORMModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="access_token 有效期(秒)")


class CurrentUserOut(ORMModel):
    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    avatar: str | None = None
    phone: str | None = None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)


class UserCreate(RegisterRequest):
    is_active: bool = True
    roles: list[str] = Field(default_factory=list, description="角色 code 列表")


class UserUpdate(ORMModel):
    email: EmailStr | None = None
    full_name: str | None = Field(default=None, max_length=64)
    phone: str | None = Field(default=None, max_length=32)
    is_active: bool | None = None
    remark: str | None = Field(default=None, max_length=255)


class UserAdminUpdate(UserUpdate):
    roles: list[str] | None = None


class PasswordChange(ORMModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=128)


class UserListItem(ORMModel):
    id: int
    username: str
    email: EmailStr
    full_name: str | None = None
    avatar: str | None = None
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime
    roles: list[str] = Field(default_factory=list)
