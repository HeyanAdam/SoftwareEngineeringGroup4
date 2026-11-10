"""用户模块请求/响应模型。

字段口径按《权限表》ER 图: 返回体里是 id / username / nickname / undergraduate_major /
major / target_area / prep_stage / target_score, 由 sys_user + user_account 两张表拼出来。
原先的 target_school / target_major / exam_year 已随 ER 图口径调整(详见 docs/改造说明.md)。

相比改造前新增:
    * 邮箱验证码登录 / 发码 / 找回密码 / 改密 / 退出登录的请求体;
    * TokenOut 里带上 roles 与 permissions, 前端据此渲染菜单(服务端仍逐接口校验)。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.user import User

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,50}$")
EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
CODE_PATTERN = re.compile(r"^\d{6}$")


def _check_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_PATTERN.match(value):
        raise ValueError("邮箱格式不正确")
    return value


# ----------------------------- 注册 / 登录 -----------------------------
class RegisterRequest(BaseModel):
    """注册: 用户名 + 邮箱 + 密码。"""

    username: str = Field(..., min_length=3, max_length=50, description="登录用户名, 字母/数字/下划线")
    email: str = Field(..., max_length=120, description="邮箱, 用于验证码登录与找回密码")
    password: str = Field(..., min_length=1, max_length=128, description="密码, 至少 8 位且含字母和数字")
    nickname: str | None = Field(default=None, max_length=50, description="昵称, 留空则用用户名")

    @field_validator("username")
    @classmethod
    def _validate_username(cls, value: str) -> str:
        if not USERNAME_PATTERN.match(value):
            raise ValueError("用户名只能包含字母、数字、下划线, 长度 3-50")
        return value

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _check_email(value)


class LoginRequest(BaseModel):
    """用户名 + 密码登录。username 允许填登录名或已绑定邮箱。

    captcha_id / captcha_code: 连续失败 CAPTCHA_AFTER_FAILURES 次后必填,
    缺省或错误时返回 code=40010。
    """

    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=128)
    captcha_id: str | None = Field(default=None, max_length=64, description="图形验证码 ID")
    captcha_code: str | None = Field(default=None, max_length=8, description="图形验证码答案")


class SendEmailCodeRequest(BaseModel):
    """发送邮箱验证码。"""

    email: str = Field(..., max_length=120)
    purpose: Literal["login", "reset", "register"] = Field(default="login", description="用途")

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _check_email(value)


class EmailCodeLoginRequest(BaseModel):
    """邮箱验证码登录。"""

    email: str = Field(..., max_length=120)
    code: str = Field(..., description="6 位数字验证码")

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _check_email(value)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        value = value.strip()
        if not CODE_PATTERN.match(value):
            raise ValueError("验证码为 6 位数字")
        return value


class ResetPasswordRequest(BaseModel):
    """邮箱验证码重置密码(未登录也能用)。"""

    email: str = Field(..., max_length=120)
    code: str = Field(..., description="6 位数字验证码")
    new_password: str = Field(..., min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        return _check_email(value)

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        value = value.strip()
        if not CODE_PATTERN.match(value):
            raise ValueError("验证码为 6 位数字")
        return value


class ChangePasswordRequest(BaseModel):
    """已登录状态下修改密码。"""

    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=1, max_length=128)


# ----------------------------- 个人信息 -----------------------------
class UserUpdateRequest(BaseModel):
    """修改个人资料。字段全部可选, 只更新传了的项(字段与 user_account 一一对应)。"""

    nickname: str | None = Field(default=None, max_length=50, description="昵称")
    undergraduate_major: str | None = Field(default=None, max_length=60, description="本科专业")
    major: str | None = Field(default=None, max_length=100, description="报考专业")
    target_area: str | None = Field(default=None, max_length=30, description="目标报考地区")
    prep_stage: str | None = Field(default=None, max_length=20, description="备考阶段")
    target_score: int | None = Field(default=None, ge=0, le=1000, description="目标考试分数")


class UserBrief(BaseModel):
    """登录 / 注册接口返回的精简用户信息。"""

    id: int
    username: str
    email: str
    nickname: str | None = None
    display_name: str

    @classmethod
    def from_user(cls, user: User) -> "UserBrief":
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            nickname=user.nickname,
            display_name=user.display_name,
        )


class UserOut(BaseModel):
    """个人中心完整信息。"""

    id: int
    username: str
    email: str
    nickname: str | None = None
    display_name: str
    undergraduate_major: str | None = None
    major: str | None = None
    target_area: str | None = None
    prep_stage: str | None = None
    target_score: int | None = None
    created_at: datetime
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    @classmethod
    def from_user(
        cls, user: User, roles: list[str] | None = None, permissions: list[str] | None = None
    ) -> "UserOut":
        account = user.account
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            nickname=user.nickname,
            display_name=user.display_name,
            undergraduate_major=account.undergraduate_major if account else None,
            major=account.major if account else None,
            target_area=account.target_area if account else None,
            prep_stage=account.prep_stage if account else None,
            target_score=account.target_score if account else None,
            created_at=user.created_at,
            roles=roles or [],
            permissions=permissions or [],
        )


class TokenOut(BaseModel):
    """登录成功的返回。roles / permissions 供前端渲染菜单。"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="有效期(秒)")
    user: UserBrief
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
