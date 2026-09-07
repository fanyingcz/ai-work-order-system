# 智能工单系统 ver1.1 —— 单容器：FastAPI 后端 + 两个已构建的前端
#
# 前端 dist 已在仓库中，因此镜像不需要 Node 环境，构建快、体积小。
# 路由：/ 报修端/管理端，/worker 工人端，/api/v1 接口，/docs Swagger

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# curl 仅用于容器健康检查
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

# FastAPI 必定有 /docs，用它做存活探针最稳
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://localhost:8000/docs > /dev/null || exit 1

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
