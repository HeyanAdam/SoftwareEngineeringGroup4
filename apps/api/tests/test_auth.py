"""认证链路: 注册 / 登录 / me / 刷新旋转 / 登出失效 / 错误信封。"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from httpx import AsyncClient

PASSWORD = "Passw0rd!23"


def _unique(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


async def test_register_login_me(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
) -> None:
    username = _unique("newbie")
    email = f"{username}@example.com"

    response = await client.post(
        f"{api_prefix}/auth/register",
        json={"username": username, "email": email, "password": PASSWORD, "full_name": "New Bie"},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["username"] == username
    assert created["email"] == email
    assert created["roles"] == ["viewer"]  # 默认角色
    assert created["is_active"] is True

    response = await client.post(
        f"{api_prefix}/auth/login", json={"username": username, "password": PASSWORD}
    )
    assert response.status_code == 200, response.text
    tokens = response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["expires_in"] > 0
    assert tokens["access_token"] and tokens["refresh_token"]

    response = await client.get(f"{api_prefix}/auth/me", headers=bearer(tokens["access_token"]))
    assert response.status_code == 200
    me = response.json()
    assert me["username"] == username
    assert me["is_superuser"] is False
    assert me["last_login_at"] is not None
    assert "dashboard:read" in me["permissions"]  # viewer 的权限点

    # 也支持用邮箱登录
    response = await client.post(
        f"{api_prefix}/auth/login", json={"username": email, "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_register_duplicate_conflict(
    client: AsyncClient,
    api_prefix: str,
    seeded: dict[str, Any],
) -> None:
    response = await client.post(
        f"{api_prefix}/auth/register",
        json={
            "username": "root",  # 种子用户
            "email": "root-dup@example.com",
            "password": PASSWORD,
        },
    )
    assert response.status_code == 409
    assert response.json()["code"] == 40900


async def test_refresh_rotation_then_logout_invalidates(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    tokens = await login("admin1")

    refreshed = await client.post(
        f"{api_prefix}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()
    assert new_tokens["refresh_token"] != tokens["refresh_token"]
    assert new_tokens["access_token"] != tokens["access_token"]

    # 旋转后旧 refresh token 立即失效 (Redis 白名单已删除)
    reused = await client.post(
        f"{api_prefix}/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert reused.status_code == 401
    assert reused.json()["code"] == 40107

    logout = await client.post(
        f"{api_prefix}/auth/logout", headers=bearer(new_tokens["access_token"])
    )
    assert logout.status_code == 200
    assert logout.json()["message"]

    # 登出把 token_version +1, 新 refresh token 也随之失效
    after_logout = await client.post(
        f"{api_prefix}/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]}
    )
    assert after_logout.status_code == 401
    assert after_logout.json()["code"] == 40106


async def test_login_wrong_password_returns_envelope(client: AsyncClient, api_prefix: str) -> None:
    response = await client.post(
        f"{api_prefix}/auth/login", json={"username": "admin1", "password": "definitely-wrong"}
    )

    assert response.status_code == 401
    body = response.json()
    assert body["code"] == 40105
    assert body["message"]
    assert "access_token" not in body


async def test_missing_token_returns_401(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == 40100


async def test_validation_error_envelope(client: AsyncClient, api_prefix: str) -> None:
    response = await client.post(f"{api_prefix}/auth/login", json={"username": "ab"})

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == 42200
    assert isinstance(body["data"], list)
    assert body["data"][0]["field"]


async def test_change_password_rotates_token_version(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    username = _unique("pwd")
    new_password = "An0ther!Pass"
    registered = await client.post(
        f"{api_prefix}/auth/register",
        json={"username": username, "email": f"{username}@example.com", "password": PASSWORD},
    )
    assert registered.status_code == 201, registered.text

    tokens = await login(username)
    changed = await client.post(
        f"{api_prefix}/auth/change-password",
        json={"old_password": PASSWORD, "new_password": new_password},
        headers=bearer(tokens["access_token"]),
    )
    assert changed.status_code == 200, changed.text

    # 旧密码不再可用, 新密码可以
    assert (
        await client.post(
            f"{api_prefix}/auth/login", json={"username": username, "password": PASSWORD}
        )
    ).status_code == 401
    assert (
        await client.post(
            f"{api_prefix}/auth/login", json={"username": username, "password": new_password}
        )
    ).status_code == 200
