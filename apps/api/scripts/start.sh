#!/usr/bin/env bash
# 容器启动入口: 等待依赖 -> 迁移 -> 启动 uvicorn
set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${UVICORN_WORKERS:-1}"

echo "[entrypoint] APP_ENV=${APP_ENV:-production} python=$(python -V 2>&1)"

echo "[entrypoint] 等待 MySQL 可连接..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.environ.get("DATABASE_URL", "")
sync_url = url.replace("+aiomysql", "+pymysql")
if not url:
    print("[entrypoint] 未配置 DATABASE_URL, 跳过等待")
    raise SystemExit(0)

for attempt in range(1, 61):
    try:
        engine = create_engine(sync_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"[entrypoint] MySQL 就绪 (第 {attempt} 次尝试)")
        break
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] 第 {attempt}/60 次等待 MySQL: {type(exc).__name__}")
        time.sleep(2)
else:
    raise SystemExit("[entrypoint] MySQL 等待超时")
PY

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] 执行 alembic upgrade head ..."
  alembic upgrade head || echo "[entrypoint] alembic 迁移失败 (可忽略, 继续启动)"
fi

if [ "${AUTO_CREATE_TABLES:-1}" = "1" ]; then
  echo "[entrypoint] 同步 ORM 建表 ..."
  python -m app.initial_data || echo "[entrypoint] 初始化数据失败 (可忽略)"
fi

echo "[entrypoint] 启动 uvicorn on ${HOST}:${PORT} (workers=${WORKERS})"
exec uvicorn app.main:app --host "${HOST}" --port "${PORT}" --workers "${WORKERS}" --proxy-headers --forwarded-allow-ips='*'
