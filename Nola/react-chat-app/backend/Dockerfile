# Backend Dockerfile - FastAPI with Ollama integration
#if youre new to coding this file is used to create a container for the backend of the chat application
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pinned requirements for reproducibility
COPY backend/requirements.lock .

# Install Python dependencies with hashes
RUN pip install --no-cache-dir -r requirements.lock

# Copy backend code
COPY backend/ .

# Copy Nola state for agent
COPY Nola/ /app/Nola/

# Copy entrypoint script
COPY backend/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
