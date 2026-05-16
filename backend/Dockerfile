# AI Marketing Platform v2.0 - Backend Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY dist/ /app/static/

RUN groupadd --gid 1000 aimp && \
    useradd --uid 1000 --gid aimp --shell /bin/false --create-home aimp
USER aimp

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v2/health/live || exit 1

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2
