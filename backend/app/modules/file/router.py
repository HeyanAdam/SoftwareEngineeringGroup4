"""文件模块路由(占位)。

业务实现不在鉴权交付包内, 仅保留模块自检接口。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/file", tags=["文件模块"])


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    return {"module": "file", "message": "文件模块运行正常(占位)"}
