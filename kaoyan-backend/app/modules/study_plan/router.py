from fastapi import APIRouter

router = APIRouter(prefix="/api/plan", tags=["学习规划模块"])

@router.get("/ping")
def ping():
    return {"module": "study_plan", "message": "学习规划模块占位接口"}