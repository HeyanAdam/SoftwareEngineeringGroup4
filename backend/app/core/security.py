"""密码哈希与访问令牌签发。

选型说明(本次改造):
    * 密码哈希继续用 argon2-cffi: 参数化慢哈希 + 随机盐, 抗 GPU 暴力破解,
      单条哈希约 96 字符, 完全放得进 sys_user.password VARCHAR(128)。
    * 令牌签发/校验改由 **AuthX 1.7.1**(MIT 协议, 免费商用) 负责:
      JWT 编码、过期校验、header 解析、吊销名单回调都由框架提供,
      我们不再自己拼 payload、也不再用 PyJWT 直接 decode。
    * 吊销(退出登录/改密后立即失效)通过 AuthX 的 token blocklist 回调实现,
      名单存 Redis(不可用时降级为进程内存储), 键里放 token 的 sha256 摘要,
      避免把原始 token 明文写进缓存。
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import timedelta
from typing import Any

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from authx import AuthX, AuthXConfig, RequestToken, TokenPayload

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.core.store import get_store

logger = logging.getLogger("kaoyan.security")

_hasher = PasswordHasher()

TOKEN_TYPE = "bearer"

# 用于「账号不存在时也做一次等代价校验」的哑哈希, 防时序攻击/账号枚举
_DUMMY_HASH = _hasher.hash("dummy-password-for-timing-equalization")

REVOKED_PREFIX = "auth:revoked:"


# ----------------------------- 令牌 -----------------------------
authx_config = AuthXConfig(
    JWT_SECRET_KEY=settings.SECRET_KEY,
    JWT_ALGORITHM=settings.JWT_ALGORITHM,
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    JWT_TOKEN_LOCATION=["headers"],
    JWT_HEADER_NAME="Authorization",
    JWT_HEADER_TYPE="Bearer",
)

auth = AuthX(config=authx_config)


def _fingerprint(token: str) -> str:
    """token 摘要用作缓存键, 不把原始凭证落到存储里。"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _is_revoked(token: str | None, **_kwargs: Any) -> bool:
    """AuthX blocklist 回调: 命中即视为令牌已吊销。"""
    if not token:
        return False
    return get_store().exists(REVOKED_PREFIX + _fingerprint(token))


# 注册回调后, AuthX 自带的依赖(access_token_required)也会走吊销校验
auth.set_token_blocklist(_is_revoked)


def create_access_token(
    subject: str | int,
    *,
    expires_minutes: int | None = None,
    scopes: list[str] | None = None,
    **extra: Any,
) -> str:
    """签发访问令牌, subject 一般是用户 user_id。

    extra 里的键会作为自定义 claim 写进令牌; 不要放密码、邮箱验证码等敏感信息。
    """
    expiry = (
        timedelta(minutes=expires_minutes)
        if expires_minutes is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return auth.create_access_token(
        uid=str(subject), expiry=expiry, data=extra or None, scopes=scopes
    )


def verify_access_token(token: str) -> TokenPayload:
    """解析并校验令牌; 失败时抛 AuthX 的异常, 由调用方转成统一格式。"""
    request_token = RequestToken(token=token, type="access", location="headers")
    return auth.verify_token(request_token)


def is_token_revoked(token: str) -> bool:
    return _is_revoked(token)


def revoke_token(token: str) -> None:
    """把令牌加入吊销名单, 过期时间与令牌本身一致(过期后自然失效)。"""
    get_store().set(
        REVOKED_PREFIX + _fingerprint(token),
        "1",
        ttl=settings.token_expire_seconds,
    )


# ----------------------------- 密码版本 -----------------------------
# 令牌里带 pv(密码版本)声明; 改密/重置密码时版本 +1, 此前签发的所有令牌立即失效。
# 这样不需要在数据库加"密码修改时间"列, 也不依赖逐个吊销令牌。
PWD_VERSION_PREFIX = "auth:pwdver:"


def password_version(user_id: int | str) -> int:
    raw = get_store().get(PWD_VERSION_PREFIX + str(user_id))
    try:
        return int(raw) if raw else 0
    except (TypeError, ValueError):
        return 0


def bump_password_version(user_id: int | str) -> None:
    get_store().incr(PWD_VERSION_PREFIX + str(user_id))


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


def verify_password_dummy(raw_password: str) -> None:
    """账号不存在时调用: 消耗与真实校验相当的时间, 避免响应时间泄露账号是否存在。"""
    try:
        _hasher.verify(_DUMMY_HASH, raw_password)
    except Exception:  # noqa: BLE001  结果恒为失败, 只为耗时
        pass


_ALPHA_RE = re.compile(r"[A-Za-z]")
_DIGIT_RE = re.compile(r"\d")


def validate_password_strength(raw_password: str) -> None:
    """密码策略: 长度 + 字母与数字混合。

    原来 PASSWORD_MIN_LENGTH 是 6 且不检查组成, 这里提升到 8 位并要求字母+数字。
    """
    if len(raw_password) < settings.PASSWORD_MIN_LENGTH:
        raise BadRequestError(
            f"密码长度至少 {settings.PASSWORD_MIN_LENGTH} 位"
        )
    if len(raw_password) > settings.PASSWORD_MAX_LENGTH:
        raise BadRequestError(f"密码长度不能超过 {settings.PASSWORD_MAX_LENGTH} 位")
    if not (_ALPHA_RE.search(raw_password) and _DIGIT_RE.search(raw_password)):
        raise BadRequestError("密码必须同时包含字母和数字")


def mask_email(email: str) -> str:
    """日志与审计里的邮箱脱敏: zhangsan@qq.com -> z*******n@qq.com。"""
    name, _, domain = email.partition("@")
    if not domain:
        return "***"
    if len(name) <= 2:
        return f"{name[0]}***@{domain}"
    return f"{name[0]}{'*' * (len(name) - 2)}{name[-1]}@{domain}"
