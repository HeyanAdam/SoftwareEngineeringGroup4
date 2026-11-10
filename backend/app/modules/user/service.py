"""用户模块业务逻辑: 注册、双通道登录、找回密码、修改密码、退出登录。

对齐《明文密文说明》里的几条硬要求:
    1. 密码只存 argon2 慢哈希, 不落明文(见 security.py);
    2. 登录失败统一提示「账号或密码错误」, 账号不存在时也做一次等代价哑哈希,
       防止通过响应时间做账号枚举;
    3. 邮箱验证码 5 分钟、一次性、错 5 次作废;
    4. 连续失败 5 次锁定 10 分钟(Redis 计数);
    5. 改密 / 重置密码后, 旧的令牌立即失效(令牌里带密码版本号, 改密即 +1)。

新增(相对改造前):
    * 邮箱验证码登录;
    * 退出登录(把令牌写进吊销名单), 解决原来「JWT 签发后无法吊销」的问题;
    * 普通用户只能看到 / 修改自己的资料, 管理员的用户管理在 rbac 模块。
"""

from __future__ import annotations

import hmac
import json
import logging
import secrets
from typing import Any

from fastapi import Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.audit import AuditAction, write_audit
from app.core.captcha import verify_captcha
from app.core.exceptions import (
    BadRequestError,
    CaptchaError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.core.mailer import send_verification_code
from app.core.rbac import (
    is_super_admin,
    user_permission_keys,
    user_role_names,
)
from app.core.security import (
    bump_password_version,
    create_access_token,
    hash_password,
    mask_email,
    revoke_token,
    validate_password_strength,
    verify_password,
    verify_password_dummy,
)
from app.core.store import get_store
from app.models.account import UserAccount
from app.models.rbac import Permission, Role, UserRole
from app.models.user import User

logger = logging.getLogger("kaoyan.user")

CODE_KEY = "email:code:{purpose}:{email}"
CODE_COOLDOWN_KEY = "email:code:cooldown:{purpose}:{email}"
LOGIN_FAIL_KEY = "login:fail:{account}"


class UserService:
    """用户相关业务逻辑。所有方法都在传入的 db 会话上操作。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    # ----------------------------- 查询 -----------------------------
    def get_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def get_by_username_or_email(self, identity: str) -> User | None:
        """按登录名或邮箱查账号(登录接口用, 两种写法都能登)。"""
        identity = identity.strip()
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

    # ----------------------------- 注册 -----------------------------
    def register(
        self,
        *,
        username: str,
        email: str,
        password: str,
        nickname: str | None = None,
    ) -> User:
        validate_password_strength(password)

        if self.username_taken(username):
            raise ConflictError("该用户名已被占用")
        if self.email_taken(email):
            raise ConflictError("该邮箱已被注册")

        user = User(
            username=username,
            email=email.lower(),
            password_hash=hash_password(password),
            account_status=1,
        )
        self.db.add(user)
        self.db.flush()  # 拿到 user_id

        self.db.add(UserAccount(user_id=user.id, user_name=nickname or username))

        # 新用户默认「考研学生」角色; 管理员角色只能由后台分配
        student_role = self.db.scalar(
            select(Role).where(Role.role_id == settings.DEFAULT_STUDENT_ROLE_ID)
        )
        if student_role is not None:
            self.db.add(UserRole(user_id=user.id, role_id=student_role.role_id))

        self.db.commit()
        self.db.refresh(user)
        write_audit(
            self.db,
            action=AuditAction.USER_REGISTER,
            user=user,
            target_type="user",
            target_id=user.id,
            detail={"login_name": user.username, "roles": [student_role.role_id] if student_role else []},
        )
        logger.info("新用户注册: %s (%s)", username, mask_email(email))
        return user

    # ----------------------------- 登录 -----------------------------
    def authenticate(
        self,
        identity: str,
        password: str,
        request: Request | None = None,
        captcha_id: str | None = None,
        captcha_code: str | None = None,
    ) -> User:
        """用户名或邮箱 + 密码登录; 失败提示统一, 不暴露账号是否存在。"""
        self._assert_not_locked(identity)

        user = self.get_by_username_or_email(identity)
        if user is not None:
            # 两种标识共享同一额度: 用户名试满 5 次后, 换邮箱也继续锁
            self._assert_not_locked(identity, user)

        # 防机器人: 该账号失败满 CAPTCHA_AFTER_FAILURES 次后强制图形验证码。
        # 在哑哈希/验密之前拦截, 验证码不过就不消耗密码校验成本。
        if self._captcha_required(identity, user) and not (captcha_id and captcha_code):
            raise CaptchaError("登录失败次数较多, 请先完成图形验证")
        if captcha_id or captcha_code:
            # 客户端一旦提交验证码就必须校验(前端首次失败即展示验证码框,
            # 此时计数未必到阈值; 不校验等于形同虚设)
            if not verify_captcha(captcha_id, captcha_code):
                raise CaptchaError("图形验证码错误或已过期, 请点击图片刷新后重试")

        if user is None:
            # 等代价哑哈希: 账号不存在时也花掉一次校验时间, 防账号枚举
            verify_password_dummy(password)
            write_audit(
                self.db,
                action=AuditAction.LOGIN_FAILURE,
                login_name=mask_email(str(identity)) if "@" in str(identity) else str(identity)[:50],
                target_type="session",
                detail={"reason": "unknown_account"},
                request=request,
                success=False,
            )
            self._record_failure(identity, user)
            raise UnauthorizedError("账号或密码错误")

        if not verify_password(password, user.password_hash):
            write_audit(
                self.db,
                action=AuditAction.LOGIN_FAILURE,
                user=user,
                target_type="session",
                detail={"reason": "bad_password"},
                request=request,
                success=False,
            )
            self._record_failure(identity, user)
            raise UnauthorizedError("账号或密码错误")

        if user.account_status != 1:
            raise ForbiddenError("账号已被禁用, 请联系管理员")

        self._clear_failures(identity, user)
        write_audit(
            self.db,
            action=AuditAction.LOGIN_SUCCESS,
            user=user,
            target_type="session",
            detail={"method": "password"},
            request=request,
        )
        return user

    def login_by_email_code(
        self, email: str, code: str, request: Request | None = None
    ) -> User:
        """邮箱 + 验证码登录。"""
        self._consume_code(email, "login", code)

        user = self.db.scalar(select(User).where(User.email == email))
        if user is not None:
            self._assert_not_locked(email, user)
        if user is None:
            # 验证码已经消费掉, 这里仍然不区分「邮箱不存在」与「验证码错误」的细节
            write_audit(
                self.db,
                action=AuditAction.LOGIN_FAILURE,
                login_name=mask_email(email),
                target_type="session",
                detail={"reason": "unknown_email", "method": "email_code"},
                request=request,
                success=False,
            )
            self._record_failure(email)
            raise UnauthorizedError("邮箱或验证码错误")

        if user.account_status != 1:
            raise ForbiddenError("账号已被禁用, 请联系管理员")

        self._clear_failures(email, user)
        write_audit(
            self.db,
            action=AuditAction.LOGIN_SUCCESS,
            user=user,
            target_type="session",
            detail={"method": "email_code"},
            request=request,
        )
        return user

    # ----------------------------- 邮箱验证码 -----------------------------
    def send_email_code(self, email: str, purpose: str) -> dict[str, Any]:
        """发送验证码。无论邮箱是否注册都返回同样的提示, 避免账号枚举。"""
        store = get_store()
        cooldown_key = CODE_COOLDOWN_KEY.format(purpose=purpose, email=email)
        if store.exists(cooldown_key):
            remain = max(1, store.ttl(cooldown_key))
            raise BadRequestError(f"发送太频繁, 请 {remain} 秒后再试")

        code = f"{secrets.randbelow(1_000_000):06d}"
        store.set(
            CODE_KEY.format(purpose=purpose, email=email),
            json.dumps({"code": code, "attempts": 0}),
            ttl=settings.EMAIL_CODE_TTL_SECONDS,
        )
        store.set(cooldown_key, "1", ttl=settings.EMAIL_CODE_RESEND_SECONDS)

        result = send_verification_code(
            to_email=email, code=code, purpose=purpose, ttl_seconds=settings.EMAIL_CODE_TTL_SECONDS
        )
        return {
            "channel": result["channel"],
            "expires_in": settings.EMAIL_CODE_TTL_SECONDS,
            "resend_after": settings.EMAIL_CODE_RESEND_SECONDS,
            # 只有开发期兜底通道才会带上验证码, 生产环境恒为 None
            "dev_code": result["dev_code"],
            "email": mask_email(email),
        }

    def _consume_code(self, email: str, purpose: str, code: str) -> None:
        store = get_store()
        key = CODE_KEY.format(purpose=purpose, email=email)
        raw = store.get(key)
        if not raw:
            raise BadRequestError("验证码已过期, 请重新获取")

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            store.delete(key)
            raise BadRequestError("验证码已失效, 请重新获取")

        if int(data.get("attempts", 0)) >= settings.EMAIL_CODE_MAX_ATTEMPTS:
            store.delete(key)
            raise BadRequestError("验证码错误次数过多, 请重新获取")

        if not hmac.compare_digest(str(data.get("code", "")), code):
            data["attempts"] = int(data.get("attempts", 0)) + 1
            store.set(key, json.dumps(data), ttl=max(1, store.ttl(key)))
            raise BadRequestError("验证码不正确")

        # 一次性: 校验通过立即删除, 重放无效
        store.delete(key)

    # ----------------------------- 密码 -----------------------------
    def reset_password(
        self, email: str, code: str, new_password: str, request: Request | None = None
    ) -> None:
        """未登录状态下的找回密码。"""
        validate_password_strength(new_password)
        self._consume_code(email, "reset", code)

        user = self.db.scalar(select(User).where(User.email == email))
        if user is None:
            # 验证码已消费, 不额外泄露邮箱是否注册
            raise UnauthorizedError("邮箱或验证码错误")

        user.password_hash = hash_password(new_password)
        self.db.commit()

        # 密码版本 +1: 该账号此前签发的所有令牌立即失效
        bump_password_version(user.id)

        # 重置成功后清空登录失败计数, 否则账号仍会被之前的 10 分钟锁定拦住
        self._clear_failures(email, user)

        write_audit(
            self.db,
            action=AuditAction.PASSWORD_RESET,
            user=user,
            target_type="user",
            target_id=user.id,
            detail={"method": "email_code"},
            request=request,
        )

    def change_password(
        self,
        user: User,
        old_password: str,
        new_password: str,
        request: Request | None = None,
    ) -> None:
        """已登录状态下的修改密码。"""
        if not verify_password(old_password, user.password_hash):
            raise BadRequestError("原密码不正确")
        validate_password_strength(new_password)
        if verify_password(new_password, user.password_hash):
            raise BadRequestError("新密码不能与原密码相同")

        user.password_hash = hash_password(new_password)
        self.db.commit()
        bump_password_version(user.id)

        write_audit(
            self.db,
            action=AuditAction.PASSWORD_CHANGE,
            user=user,
            target_type="user",
            target_id=user.id,
            request=request,
        )

        # 当前令牌也一并吊销, 前端需要重新登录
        token = getattr(request.state, "access_token", None) if request else None
        if token:
            revoke_token(token)

    # ----------------------------- 资料 -----------------------------
    def update_profile(
        self,
        user: User,
        *,
        nickname: str | None = None,
        undergraduate_major: str | None = None,
        major: str | None = None,
        target_area: str | None = None,
        prep_stage: str | None = None,
        target_score: int | None = None,
    ) -> User:
        """只更新传了的字段(None 表示不改), 字段与 user_account 一一对应。"""
        account = user.account
        if account is None:
            account = UserAccount(user_id=user.id, user_name=nickname or user.username)
            self.db.add(account)

        if nickname is not None:
            account.user_name = nickname
        if undergraduate_major is not None:
            account.undergraduate_major = undergraduate_major
        if major is not None:
            account.major = major
        if target_area is not None:
            account.target_area = target_area
        if prep_stage is not None:
            account.prep_stage = prep_stage
        if target_score is not None:
            account.target_score = target_score

        self.db.commit()
        self.db.refresh(user)
        return user

    # ----------------------------- 登录态 -----------------------------
    def logout(self, user: User, token: str, request: Request | None = None) -> None:
        revoke_token(token)
        write_audit(
            self.db,
            action=AuditAction.LOGOUT,
            user=user,
            target_type="session",
            request=request,
        )

    def permission_keys(self, user: User) -> list[str]:
        """返回该用户的全部权限标识; 管理员返回全部(与放行逻辑保持一致)。"""
        if is_super_admin(user):
            return list(self.db.scalars(select(Permission.perm_key)).all())
        return sorted(user_permission_keys(self.db, user))

    def role_names(self, user: User) -> list[str]:
        return user_role_names(user)

    def build_token_payload(self, user: User) -> dict[str, Any]:
        """登录成功后一次性把前端需要的上下文都返回, 省一次额外请求。"""
        return {
            "access_token": create_access_token(
                user.id, login_name=user.username, pv=self._password_version(user.id)
            ),
            "token_type": "bearer",
            "expires_in": settings.token_expire_seconds,
            "roles": self.role_names(user),
            "permissions": self.permission_keys(user),
        }

    @staticmethod
    def _password_version(user_id: int) -> int:
        from app.core.security import password_version

        return password_version(user_id)

    # ----------------------------- 登录失败计数 -----------------------------
    @staticmethod
    def _lock_keys(account: str, user: User | None = None) -> list[str]:
        """锁定键: 输入标识一份, 解析到账号后再挂一份 user_id。

        只按输入字符串计数时, 同一个账号用用户名和邮箱各试 5 次就能绕过锁定;
        补一个 user_id 维度后, 两种标识共享同一额度。
        """
        keys = [LOGIN_FAIL_KEY.format(account=account.strip().lower())]
        if user is not None:
            keys.append(LOGIN_FAIL_KEY.format(account=f"user:{user.id}"))
        return keys

    def _assert_not_locked(self, account: str, user: User | None = None) -> None:
        store = get_store()
        for key in self._lock_keys(account, user):
            raw = store.get(key)
            if raw and int(raw) >= settings.LOGIN_FAIL_LIMIT:
                remain = max(1, store.ttl(key))
                raise BadRequestError(
                    f"登录失败次数过多, 请 {max(1, remain // 60)} 分钟后再试"
                )

    def _captcha_required(self, account: str, user: User | None = None) -> bool:
        """是否强制图形验证码: 任一锁定维度的失败计数达到阈值。

        与登录锁定共用计数键, 因此「用户名失败 2 次再换邮箱」同样需要验证码。
        """
        store = get_store()
        for key in self._lock_keys(account, user):
            raw = store.get(key)
            if raw and int(raw) >= settings.CAPTCHA_AFTER_FAILURES:
                return True
        return False

    def _record_failure(self, account: str, user: User | None = None) -> None:
        """记录一次失败; 达到阈值后直接抛锁定提示(而不是继续返回"密码错误")。"""
        store = get_store()
        count = 0
        for key in self._lock_keys(account, user):
            count = max(count, store.incr(key, ttl=settings.LOGIN_LOCK_SECONDS))
        if count >= settings.LOGIN_FAIL_LIMIT:
            logger.warning("账号 %s 连续登录失败 %d 次, 已锁定", account, count)
            raise BadRequestError(
                f"登录失败次数过多, 请 {max(1, settings.LOGIN_LOCK_SECONDS // 60)} 分钟后再试"
            )

    def _clear_failures(self, account: str, user: User | None = None) -> None:
        """清理失败计数; 有 user 时把用户名、邮箱、user_id 三个维度一起清掉。

        否则「邮箱登录成功」只清了邮箱与 user_id, 用户名维度的旧计数还在,
        下次按用户名登录仍可能被误判为锁定。
        """
        store = get_store()
        keys = set(self._lock_keys(account, user))
        if user is not None:
            keys.add(LOGIN_FAIL_KEY.format(account=user.username.strip().lower()))
            keys.add(LOGIN_FAIL_KEY.format(account=user.email.strip().lower()))
        for key in keys:
            store.delete(key)
