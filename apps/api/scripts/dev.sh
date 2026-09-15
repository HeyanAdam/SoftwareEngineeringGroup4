#!/usr/bin/env bash
# 本地开发一键启动 (宿主机直跑, 需要先起 infra: pnpm up:infra)
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "[dev] 创建虚拟环境 ..."
  python -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || source .venv/Scripts/activate

echo "[dev] 安装依赖 ..."
pip install -q -e ".[dev]"

echo "[dev] 迁移 + 初始化数据 ..."
alembic upgrade head || true
python -m app.initial_data || true

echo "[dev] uvicorn --reload http://127.0.0.1:8000/docs"
exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
