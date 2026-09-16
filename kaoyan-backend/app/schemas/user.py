"""用户模块的请求/响应模型。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import settings


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[A-Za-z0-9_]+$",
        description="用户名, 仅字母/数字/下划线, 3-50 位",
        examples=["xiaoming"],
    )
    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=6, max_length=64, description="密码, 至少 6 位")
    nickname: str | None = Field(default=None, max_length=50)
    password_confirm: str | None = Field(
        default=None, description="确认密码(可选, 传了就校验是否一致)"
    )

    @model_validator(mode="after")
    def _check(self) -> "RegisterRequest":
        if len(self.password) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"密码长度至少 {settings.PASSWORD_MIN_LENGTH} 位")
        if self.password.isdigit() or self.password.isalpha():
            raise ValueError("密码需要同时包含字母和数字")
        if self.password_confirm is not None and self.password_confirm != self.password:
            raise ValueError("两次输入的密码不一致")
        self.email = self.email.lower()
        return self


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120, description="用户名或邮箱")
    password: str = Field(min_length=1, max_length=64)


class UserBrief(BaseModel):
    """嵌在登录响应里的精简用户信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    nickname: str | None = None


class UserOut(BaseModel):
    """个人中心返回的完整信息。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    nickname: str | None = None
    target_school: str | None = None
    target_major: str | None = None
    exam_year: int | None = None
    created_at: datetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief


class UserUpdateRequest(BaseModel):
    nickname: str | None = Field(default=None, max_length=50)
    target_school: str | None = Field(default=None, max_length=100)
    target_major: str | None = Field(default=None, max_length=100)
    exam_year: int | None = Field(default=None, ge=2000, le=2100)
