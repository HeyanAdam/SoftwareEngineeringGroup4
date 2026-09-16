"""用户模块接口: 注册 / 登录 / 个人信息。"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.modules.user.service import UserService
from app.schemas.user import (
    LoginRequest,
    RegisterRequest,
    TokenOut,
    UserBrief,
    UserOut,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/user", tags=["用户模块"])


@router.post(
    "/register",
    response_model=UserBrief,
    status_code=status.HTTP_201_CREATED,
    summary="注册账号",
)
def register(payload: RegisterRequest, db: DbSession) -> UserBrief:
    user = UserService(db).register(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        nickname=payload.nickname,
    )
    return UserBrief.model_validate(user)


@router.post("/login", response_model=TokenOut, summary="登录")
def login(payload: LoginRequest, db: DbSession) -> TokenOut:
    user = UserService(db).authenticate(payload.username, payload.password)
    token = create_access_token(user.id, username=user.username)
    return TokenOut(access_token=token, user=UserBrief.model_validate(user))


@router.get("/me", response_model=UserOut, summary="当前登录用户信息")
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.put("/me", response_model=UserOut, summary="修改个人信息")
def update_me(payload: UserUpdateRequest, user: CurrentUser, db: DbSession) -> UserOut:
    updated = UserService(db).update_profile(
        user,
        nickname=payload.nickname,
        target_school=payload.target_school,
        target_major=payload.target_major,
        exam_year=payload.exam_year,
    )
    return UserOut.model_validate(updated)


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    """保留最早的占位接口, 便于快速确认服务是否可用。"""
    return {"module": "user", "message": "用户模块运行正常"}
