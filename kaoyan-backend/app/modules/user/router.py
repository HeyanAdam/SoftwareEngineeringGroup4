from fastapi import APIRouter

router = APIRouter(prefix="/api/user", tags=["用户模块"])

@router.get("/ping")
def ping():
    return {"module": "user", "message": "用户模块占位接口"}