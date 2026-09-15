"""用户列表分页 + RBAC 拒绝 + 角色/权限列表。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient


async def test_users_list_pagination(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
    seeded: dict[str, Any],
) -> None:
    tokens = await login("root")  # 超管
    headers = bearer(tokens["access_token"])

    first = await client.get(
        f"{api_prefix}/users", params={"page": 1, "page_size": 2}, headers=headers
    )
    assert first.status_code == 200, first.text
    page1 = first.json()
    assert page1["meta"]["page"] == 1
    assert page1["meta"]["page_size"] == 2
    assert page1["meta"]["total"] >= len(seeded["users"])
    assert len(page1["items"]) == 2
    assert all(item["roles"] for item in page1["items"])

    second = await client.get(
        f"{api_prefix}/users", params={"page": 2, "page_size": 2}, headers=headers
    )
    assert second.status_code == 200
    page2 = second.json()
    assert {item["id"] for item in page2["items"]}.isdisjoint(
        {item["id"] for item in page1["items"]}
    )

    filtered = await client.get(
        f"{api_prefix}/users", params={"keyword": "viewer", "page_size": 5}, headers=headers
    )
    assert filtered.status_code == 200
    assert any("viewer" in item["username"] for item in filtered.json()["items"])

    stats = await client.get(f"{api_prefix}/users/stats", headers=headers)
    assert stats.status_code == 200
    assert stats.json()["total"] >= len(seeded["users"])

    detail = await client.get(f"{api_prefix}/users/{seeded['users']['root']}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["username"] == "root"


async def test_users_list_requires_permission(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    # viewer 没有 users:read -> 403
    viewer = await login("viewer1")
    forbidden = await client.get(f"{api_prefix}/users", headers=bearer(viewer["access_token"]))
    assert forbidden.status_code == 403
    body = forbidden.json()
    assert body["code"] == 40300
    assert body["message"]

    # admin 有 users:read -> 200
    admin = await login("admin1")
    allowed = await client.get(f"{api_prefix}/users", headers=bearer(admin["access_token"]))
    assert allowed.status_code == 200


async def test_user_write_endpoints_require_superuser(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    admin = await login("admin1")  # 有 users:write 但不是超管
    response = await client.post(
        f"{api_prefix}/users",
        json={
            "username": "not-allowed",
            "email": "not-allowed@example.com",
            "password": "Passw0rd!23",
        },
        headers=bearer(admin["access_token"]),
    )
    assert response.status_code == 403
    assert response.json()["code"] == 40300


async def test_invalid_pagination_is_rejected(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    tokens = await login("root")
    response = await client.get(
        f"{api_prefix}/users",
        params={"page": 0, "page_size": 1000},
        headers=bearer(tokens["access_token"]),
    )
    assert response.status_code == 422
    assert response.json()["code"] == 42200


async def test_roles_and_permissions_lists(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/roles")
    assert response.status_code == 200, response.text
    roles = response.json()
    codes = {role["code"] for role in roles}
    assert {"super_admin", "admin", "viewer"} <= codes

    super_admin = next(role for role in roles if role["code"] == "super_admin")
    assert super_admin["is_builtin"] is True
    assert "users:read" in super_admin["permissions"]
    assert super_admin["created_at"] and super_admin["updated_at"]

    permissions = await client.get(f"{api_prefix}/roles/permissions")
    assert permissions.status_code == 200
    payload = permissions.json()
    assert {"users:read", "dashboard:read", "chat:read"} <= {item["code"] for item in payload}
    assert all(item["module"] for item in payload)
