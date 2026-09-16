"""密码哈希与 JWT 令牌。

选型说明:
    * 密码哈希用 argon2-cffi(而非 passlib+bcrypt): API 简单, 没有 72 字节截断问题,
      也不需要和 bcrypt 版本打交道。
    * JWT 用 PyJWT, 只做签发与校验, 不在令牌里放敏感信息。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_hasher = PasswordHasher()

TOKEN_TYPE = "bearer"


# ----------------------------- 密码 -----------------------------
def hash_password(raw_password: str) -> str:
    """生成密码哈希(每次结果都不同, 自带随机盐)。"""
    return _hasher.hash(raw_password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    """校验密码; 任何异常都视为校验失败。"""
    try:
        return _hasher.verify(password_hash, raw_password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False
    except Exception:  # noqa: BLE001  哈希串损坏等异常情况一律拒绝
        return False


# ----------------------------- JWT -----------------------------
def create_access_token(
    subject: str | int, expires_minutes: int | None = None, **extra: Any
) -> str:
    """签发访问令牌, subject 一般是用户 id。"""
    now = datetime.now(timezone.utc)
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload: dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes)).timestamp()),
        **extra,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """解析访问令牌; 过期或非法返回 None(由调用方决定如何响应)。"""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
