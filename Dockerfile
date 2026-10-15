# ==============================================================================
# TrafficPulse - All-in-One Multi-Stage Dockerfile
# Packages React Frontend + FastAPI Backend + PySpark Inference into a single image
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build React + Vite Frontend
# ------------------------------------------------------------------------------
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci || npm install

COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: PySpark + FastAPI Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JAVA_HOME=/usr/lib/jvm/default-java \
    PATH="/usr/lib/jvm/default-java/bin:${PATH}" \
    SPARK_DRIVER_MEMORY=2g

WORKDIR /app

# Install OpenJDK 17 runtime, curl, and process tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-jre-headless \
    curl \
    procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application directories
COPY backend/ ./backend/
COPY spark/ ./spark/
COPY config/ ./config/
COPY models/ ./models/
COPY data/ ./data/

# Copy compiled frontend assets to be served by FastAPI
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
