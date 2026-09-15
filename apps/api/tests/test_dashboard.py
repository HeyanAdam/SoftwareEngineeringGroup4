"""仪表盘总览: stats / trend / categories / role_distribution 结构校验。"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from httpx import AsyncClient

STAT_KEYS = {
    "users",
    "active_users",
    "new_users_7d",
    "files",
    "storage",
    "messages",
    "trend_delta",
}


async def _overview(
    client: AsyncClient,
    api_prefix: str,
    headers: dict[str, str],
    *,
    refresh: bool = False,
    days: int = 30,
) -> dict[str, Any]:
    response = await client.get(
        f"{api_prefix}/dashboard/overview",
        params={"days": days, "refresh": refresh},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_dashboard_overview_shape(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    tokens = await login("viewer1")
    body = await _overview(client, api_prefix, bearer(tokens["access_token"]), refresh=True)

    assert set(body) >= {"stats", "trend", "categories", "role_distribution", "generated_at"}
    assert {item["key"] for item in body["stats"]} == STAT_KEYS
    for item in body["stats"]:
        assert item["label"]
        assert isinstance(item["value"], (int, float))

    assert body["extra"]["trend_metric"] == "active_users"
    assert body["extra"]["days"] == 30

    # 预置了 30 天 active_users 趋势
    assert len(body["trend"]) >= 20
    assert all(set(point) == {"label", "value"} for point in body["trend"])

    # 预置了 category 维度的分类数据
    assert body["categories"]
    assert all(point["value"] > 0 for point in body["categories"])

    # 角色分布 (种子角色都有用户)
    labels = {point["label"] for point in body["role_distribution"]}
    assert "超级管理员" in labels
    assert sum(point["value"] for point in body["role_distribution"]) >= 3


async def test_dashboard_overview_is_cached_then_invalidated(
    client: AsyncClient,
    api_prefix: str,
    bearer: Callable[[str], dict[str, str]],
    login: Callable[..., Any],
) -> None:
    tokens = await login("admin1")
    headers = bearer(tokens["access_token"])

    first = await _overview(client, api_prefix, headers, refresh=True)
    cached = await _overview(client, api_prefix, headers)  # 命中 Redis 缓存 (fakeredis)
    assert cached["stats"] == first["stats"]
    assert cached["trend"] == first["trend"]

    cleared = await client.post(f"{api_prefix}/dashboard/cache/refresh", headers=headers)
    assert cleared.status_code == 200
    assert "缓存" in cleared.json()["message"]


async def test_dashboard_requires_login(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/dashboard/overview")

    assert response.status_code == 401
    assert response.json()["code"] == 40100
