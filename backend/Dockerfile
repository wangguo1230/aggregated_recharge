# AskWhy 充值后端（FastAPI / askwhy-center）
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ASKWHY_HOST=0.0.0.0 \
    ASKWHY_PORT=18424

WORKDIR /app

# 先装依赖，利用层缓存
COPY pyproject.toml ./
COPY askwhy_recharge ./askwhy_recharge
RUN pip install --no-cache-dir .

EXPOSE 18424

CMD ["askwhy-center"]
