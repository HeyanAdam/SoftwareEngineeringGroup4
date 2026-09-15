"""健康检查: /health/live 与 /health/ready (外部依赖已被替身, 无需 MySQL/Redis/MinIO)。"""

from __future__ import annotations

from httpx import AsyncClient


async def test_live(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/health/live")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["env"] == "test"
    assert body["instance"]
    assert isinstance(body["uptime_seconds"], (int, float))


async def test_ready(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["checks"]["mysql"] == "ok"  # 实际走 SQLite (SELECT 1)
    assert body["checks"]["redis"] == "ok"  # fakeredis ping
    assert body["checks"]["minio"] == "ok"  # ensure_bucket 被 patch
    assert isinstance(body["checks"]["websocket_connections"], int)
    assert body["status"] == "ok"


async def test_info(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/health/info")

    assert response.status_code == 200
    body = response.json()
    assert body["app"]
    assert body["version"]
    assert body["env"] == "test"
    assert body["ws_connections"] >= 0


async def test_metrics_exposed(client: AsyncClient, api_prefix: str) -> None:
    response = await client.get(f"{api_prefix}/metrics")

    assert response.status_code == 200
    assert "app_up" in response.text
