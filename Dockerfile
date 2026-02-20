# AI_OS Docker Configuration
# ==========================
# Multi-stage build: Node.js for frontend, Python for backend

# -----------------------------------------------------------------------------
# Stage 1: Build Frontend
# -----------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Install dependencies first (better caching)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Build frontend
COPY frontend/ ./
RUN npm run build

# -----------------------------------------------------------------------------
# Stage 2: Python Runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY agent/ ./agent/
COPY chat/ ./chat/
COPY data/ ./data/
COPY docs/ ./docs/
COPY eval/ ./eval/
COPY Feeds/ ./Feeds/
COPY finetune/ ./finetune/
COPY scripts/ ./scripts/
COPY workspace/ ./workspace/
COPY pyproject.toml ./

# Copy built frontend from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directories (will be mounted as volumes in production)
RUN mkdir -p /app/data/db /app/data/logs

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV AIOS_MODE=personal

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run the server
CMD ["python", "-m", "uvicorn", "scripts.server:app", "--host", "0.0.0.0", "--port", "8000"]
