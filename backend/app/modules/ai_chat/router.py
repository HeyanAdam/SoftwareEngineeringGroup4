"""AI 问答模块路由(占位)。

业务实现不在鉴权交付包内, 仅保留模块自检接口。
接入业务代码时按 seed.py 中的权限键(question:practice 等)挂
``Depends(require_permission(...))``。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/ai-chat", tags=["AI问答模块"])


@router.get("/ping", summary="模块自检")
def ping() -> dict[str, str]:
    return {"module": "ai_chat", "message": "AI 问答模块运行正常(占位)"}
