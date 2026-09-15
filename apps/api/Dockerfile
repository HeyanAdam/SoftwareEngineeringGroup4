# syntax=docker/dockerfile:1
# =============================================================================
# FastAPI 后端镜像 (多阶段构建)
#   builder: pip wheel 出全部依赖 (国内可用 --build-arg PIP_INDEX_URL 换源)
#   runtime: 只装 wheel + 源码, 非 root 用户运行, 带健康检查
# =============================================================================

ARG PYTHON_VERSION=3.12
ARG PIP_INDEX_URL=https://pypi.org/simple

# ---------- builder ----------
FROM python:${PYTHON_VERSION}-slim AS builder
ARG PIP_INDEX_URL

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY pyproject.toml README.md ./
# 生成 requirements 并构建 wheel, 依赖层可被 Docker 缓存
RUN pip install --index-url "${PIP_INDEX_URL}" --upgrade pip setuptools wheel \
    && mkdir -p /wheels/src \
    && cp pyproject.toml /wheels/src/ \
    && pip wheel --index-url "${PIP_INDEX_URL}" --wheel-dir /wheels/dist .

# ---------- runtime ----------
FROM python:${PYTHON_VERSION}-slim AS runtime
ARG PIP_INDEX_URL

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home app

COPY --from=builder /wheels/dist /wheels/dist
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --index-url "${PIP_INDEX_URL}" --no-cache-dir /wheels/dist/*.whl \
    && rm -rf /wheels

WORKDIR /app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app
COPY --chown=app:app scripts ./scripts
RUN chmod +x ./scripts/*.sh

USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health/live || exit 1

CMD ["./scripts/start.sh"]
