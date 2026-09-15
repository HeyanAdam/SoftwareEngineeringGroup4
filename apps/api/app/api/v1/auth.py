"""认证接口: 注册 / 登录 / 刷新 / 登出 / 当前用户 / 改密。"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import BadRequestError
from app.core.logging import get_logger
from app.core.rate_limit import check_rate_limit
from app.schemas.auth import (
    CurrentUserOut,
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserUpdate,
)
from app.schemas.common import Msg
from app.services.auth import AuthService
from app.services.user import UserService

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])


def _to_current_user(user) -> CurrentUserOut:  # noqa: ANN001
    return CurrentUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        avatar=user.avatar,
        phone=user.phone,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        last_login_at=user.last_login_at,
        roles=user.role_codes,
        permissions=sorted(user.permissions),
    )


@router.post(
    "/register", response_model=CurrentUserOut, status_code=status.HTTP_201_CREATED, summary="注册"
)
async def register(payload: RegisterRequest, db: DbSession, request: Request) -> CurrentUserOut:
    await check_rate_limit(request, limit=20, scope="register")
    user = await AuthService(db).register(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )
    return _to_current_user(user)


@router.post("/login", response_model=TokenPair, summary="登录 (用户名或邮箱)")
async def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenPair:
    await check_rate_limit(request, limit=30, scope="login")
    service = AuthService(db)
    user = await service.authenticate(payload.username, payload.password)
    tokens = await service.issue_tokens(user)
    return TokenPair(**tokens)  # type: ignore[arg-type]


@router.post("/refresh", response_model=TokenPair, summary="刷新令牌 (旋转)")
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    tokens = await AuthService(db).refresh(payload.refresh_token)
    return TokenPair(**tokens)  # type: ignore[arg-type]


@router.post("/logout", response_model=Msg, summary="登出 (令牌版本 +1)")
async def logout(user: CurrentUser, db: DbSession) -> Msg:
    await AuthService(db).logout(user)
    return Msg(message="已登出")


@router.get("/me", response_model=CurrentUserOut, summary="当前登录用户")
async def me(user: CurrentUser) -> CurrentUserOut:
    return _to_current_user(user)


@router.patch("/me", response_model=CurrentUserOut, summary="更新个人资料")
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> CurrentUserOut:
    data = payload.model_dump(exclude_unset=True, exclude_none=True)
    if not data:
        raise BadRequestError("没有需要更新的字段")
    updated = await UserService(db).update(user.id, data)
    return _to_current_user(updated)


@router.post("/change-password", response_model=Msg, summary="修改密码")
async def change_password(payload: PasswordChange, user: CurrentUser, db: DbSession) -> Msg:
    await AuthService(db).change_password(user, payload.old_password, payload.new_password)
    return Msg(message="密码已更新, 请重新登录")


@router.get("/permissions", response_model=list[str], summary="当前用户权限点")
async def my_permissions(user: CurrentUser) -> list[str]:
    return sorted(user.permissions)
