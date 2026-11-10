"""用户模块接口: 注册 / 两种登录 / 邮箱验证码 / 找回密码 / 个人信息 / 退出登录。

接口契约(保持前端现有调用不变):
    POST /api/user/register      201 + UserBrief
    POST /api/user/login         TokenOut
    GET  /api/user/me            UserOut
    PUT  /api/user/me            UserOut
    GET  /api/user/ping          模块自检

本次新增:
    POST /api/user/email-code    发送邮箱验证码(登录/找回密码)
    POST /api/user/login/email   邮箱验证码登录
    POST /api/user/password/reset   用验证码重置密码(未登录)
    POST /api/user/password/change  登录后修改密码
    POST /api/user/logout        退出登录(令牌立即吊销)
    GET  /api/user/permissions   当前用户的角色与权限(前端渲染菜单用)
"""

from __future__ import annotations

from fastapi import APIRouter, Request, status

from app.core.captcha import create_captcha
from app.core.deps import CurrentUser, DbSession
from app.modules.user.service import UserService
from app.schemas.user import (
    ChangePasswordRequest,
    EmailCodeLoginRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendEmailCodeRequest,
    TokenOut,
    UserBrief,
    UserOut,
    UserUpdateRequest,
)

router = APIRouter(prefix="/api/user", tags=["用户模块"])


def _token_out(service: UserService, user: object) -> TokenOut:
    data = service.build_token_payload(user)  # type: ignore[arg-type]
    return TokenOut(
        access_token=data["access_token"],
        expires_in=data["expires_in"],
        user=UserBrief.from_user(user),  # type: ignore[arg-type]
        roles=data["roles"],
        permissions=data["permissions"],
    )


@router.post(
    "/register",
    response_model=UserBrief,
    status_code=status.HTTP_201_CREATED,
    summary="注册账号",
)
def register(payload: RegisterRequest, db: DbSession) -> UserBrief:
    service = UserService(db)
    user = service.register(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        nickname=payload.nickname,
    )
    return UserBrief.from_user(user)


@router.post("/login", response_model=TokenOut, summary="用户名 + 密码登录")
def login(payload: LoginRequest, db: DbSession, request: Request) -> TokenOut:
    service = UserService(db)
    user = service.authenticate(
        payload.username,
        payload.password,
        request=request,
        captcha_id=payload.captcha_id,
        captcha_code=payload.captcha_code,
    )
    return _token_out(service, user)


@router.get("/captcha", summary="获取图形验证码(密码登录防机器人)")
def get_captcha() -> dict:
    """返回 {captcha_id, svg, expires_in}。svg 可直接 v-html 渲染, 点击刷新即重新调用。

    触发规则: 密码登录连续失败 CAPTCHA_AFTER_FAILURES 次(默认 2)后,
    登录请求必须带 captcha_id + captcha_code, 否则返回 code=40010。
    """
    return create_captcha()


@router.post("/login/email", response_model=TokenOut, summary="邮箱验证码登录")
def login_by_email(
    payload: EmailCodeLoginRequest, db: DbSession, request: Request
) -> TokenOut:
    service = UserService(db)
    user = service.login_by_email_code(payload.email, payload.code, request=request)
    return _token_out(service, user)


@router.post("/email-code", summary="发送邮箱验证码")
def send_email_code(payload: SendEmailCodeRequest, db: DbSession) -> dict:
    """发送 6 位验证码。

    返回里 channel=smtp 表示真实发信; channel=console 表示走了兜底通道,
    此时 dev_code 会带上验证码(仅非生产环境), 方便本地联调与答辩演示。
    """
    return UserService(db).send_email_code(payload.email, payload.purpose)


@router.post("/password/reset", summary="用邮箱验证码重置密码")
def reset_password(
    payload: ResetPasswordRequest, db: DbSession, request: Request
) -> dict[str, str]:
    UserService(db).reset_password(
        payload.email, payload.code, payload.new_password, request=request
    )
    return {"message": "密码已重置, 请用新密码登录"}


@router.post("/password/change", summary="修改密码")
def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, db: DbSession, request: Request
) -> dict[str, str]:
    UserService(db).change_password(
        user, payload.old_password, payload.new_password, request=request
    )
    return {"message": "密码已修改, 请重新登录"}


@router.post("/logout", summary="退出登录")
def logout(user: CurrentUser, db: DbSession, request: Request) -> dict[str, str]:
    """把当前令牌加入吊销名单, 之后的请求一律 401。"""
    token = getattr(request.state, "access_token", "")
    if token:
        UserService(db).logout(user, token, request=request)
    return {"message": "已退出登录"}


@router.get("/me", response_model=UserOut, summary="当前登录用户信息")
def read_me(user: CurrentUser, db: DbSession) -> UserOut:
    service = UserService(db)
    return UserOut.from_user(
        user, roles=service.role_names(user), permissions=service.permission_keys(user)
    )


@router.put("/me", response_model=UserOut, summary="修改个人信息")
def update_me(payload: UserUpdateRequest, user: CurrentUser, db: DbSession) -> UserOut:
    service = UserService(db)
    updated = service.update_profile(
        user,
        nickname=payload.nickname,
        undergraduate_major=payload.undergraduate_major,
        major=payload.major,
        target_area=payload.target_area,
        prep_stage=payload.prep_stage,
        target_score=payload.target_score,
    )
    return UserOut.from_user(
        updated, roles=service.role_names(updated), permissions=service.permission_keys(updated)
    )


@router.get("/permissions", summary="当前用户的角色与权限")
def read_permissions(user: CurrentUser, db: DbSession) -> dict[str, list[str]]:
    service = UserService(db)
    return {
        "roles": service.role_names(user),
        "permissions": service.permission_keys(user),
    }


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    """保留最早的占位接口, 便于快速确认服务是否可用。"""
    return {"module": "user", "message": "用户模块运行正常"}
