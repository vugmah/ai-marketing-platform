# AI Marketing Platform v2.0 - Backend Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies + Node.js for frontend build
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Cache bust arg - change to force rebuild
ARG CACHEBUST=5

# Install Python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node.js dependencies for frontend
COPY package*.json .
RUN npm install 2>&1 || echo "No package.json, skipping npm install"

# Copy backend source first
COPY backend/ .

# Copy all source code (frontend overrides backend copy)
COPY . .

# Build frontend if it exists (with cache clean)
RUN if [ -f package.json ] && [ -d frontend ]; then \
        rm -rf /app/node_modules/.vite /app/node_modules/.cache /.cache && \
        npx vite build 2>&1 && \
        rm -rf /app/static && \
        cp -r /app/dist /app/static && \
        sed -i 's/mockSocialAccounts/window.mockSocialAccounts/g' /app/static/assets/*.js 2>/dev/null && \
        sed -i 's/mockCampaigns/window.mockCampaigns/g' /app/static/assets/*.js 2>/dev/null && \
        sed -i 's/mockPosts/window.mockPosts/g' /app/static/assets/*.js 2>/dev/null && \
        echo "Frontend built and patched"; \
    else \
        mkdir -p /app/static; \
    fi

EXPOSE 8000

# ONE-TIME MIGRATION: Run alembic upgrade before app start
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2 --proxy-headers --forwarded-allow-ips "*"
