#!/bin/bash
# start-docker.sh - Start with Docker Compose
# Requires: Docker Desktop with Ollama running on host

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🐳 React Chat App - Docker Mode${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load optional .env
if [ -f "$SCRIPT_DIR/.env" ]; then
    set -a
    source "$SCRIPT_DIR/.env"
    set +a
fi

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker Desktop${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Docker installed${NC}"

echo ""
echo -e "${BLUE}🔧 Building and starting containers...${NC}"

# Build and start
docker-compose up --build -d

# Ensure model is pulled into the Ollama container (default: llama3:8b or env override)
MODEL_NAME="${NOLA_MODEL_NAME:-llama3:8b}"
echo -e "${YELLOW}⏳ Ensuring model '${MODEL_NAME}' is available in Ollama...${NC}"
docker-compose exec -T ollama ollama pull "$MODEL_NAME" >/dev/null 2>&1 || true

echo ""
echo -e "${YELLOW}⏳ Waiting for services...${NC}"
sleep 10

# Check health
if curl -s http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Backend ready${NC}"
else
    echo -e "${RED}❌ Backend failed to start${NC}"
    docker-compose logs backend
    exit 1
fi

if curl -s http://localhost:5173 >/dev/null 2>&1; then
    echo -e "${GREEN}✅ Frontend ready${NC}"
else
    echo -e "${RED}❌ Frontend failed to start${NC}"
    docker-compose logs frontend
    exit 1
fi

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 React Chat App is running in Docker!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "   ${BLUE}Frontend:${NC}  http://localhost:5173"
echo -e "   ${BLUE}Backend:${NC}   http://localhost:8000"
echo -e "   ${BLUE}API Docs:${NC}  http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}To stop: docker-compose down${NC}"
echo -e "${YELLOW}To view logs: docker-compose logs -f${NC}"
echo ""

# Open browser
if command -v open &> /dev/null; then
    open "http://localhost:5173"
elif command -v xdg-open &> /dev/null; then
    xdg-open "http://localhost:5173"
fi
