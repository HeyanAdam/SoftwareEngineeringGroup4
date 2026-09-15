from fastapi import APIRouter

router = APIRouter(prefix="/api/ai", tags=["AI对话模块"])

@router.get("/ping")
def ping():
    return {"module": "ai_chat", "message": "AI对话模块占位接口"}