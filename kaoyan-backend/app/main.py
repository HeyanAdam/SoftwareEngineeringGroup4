from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.user.router import router as user_router
from app.modules.ai_chat.router import router as ai_router
from app.modules.study_plan.router import router as plan_router

app = FastAPI(title="考研AI导学平台 - 后端")

# 允许前端跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册各模块路由
app.include_router(user_router)
app.include_router(ai_router)
app.include_router(plan_router)


@app.get("/")
def read_root():
    return {"message": "考研AI导学平台 - 后端启动成功"}


@app.get("/api/db-check")
def db_check(db: Session = Depends(get_db)):
    """测试数据库连接：返回当前 MySQL 版本"""
    try:
        result = db.execute(text("SELECT VERSION()"))
        version = result.scalar()
        return {
            "status": "ok",
            "message": "成功连接 MySQL",
            "mysql_version": version
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"连接失败: {str(e)}"
        }