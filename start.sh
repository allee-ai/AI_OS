#!/bin/bash
# start.sh - 1-Click Start for Nola React Chat
# Run from repo root: ./start.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║          🧠 NOLA - Personal AI Chat Interface             ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Detect Nola directory (handle "Nola" or "Nola " with trailing space)
if [ -d "Nola" ]; then
    NOLA_DIR="$REPO_ROOT/Nola"
elif [ -d "Nola " ]; then
    NOLA_DIR="$REPO_ROOT/Nola "
    echo -e "${YELLOW}⚠️  Note: Nola directory has trailing space. Consider renaming.${NC}"
else
    echo -e "${RED}❌ Nola directory not found!${NC}"
    exit 1
fi

CHAT_APP="$REPO_ROOT/react-chat-app"
VENV_DIR="$REPO_ROOT/.venv"

# Helper functions
command_exists() { command -v "$1" >/dev/null 2>&1; }
port_in_use() { lsof -i:"$1" >/dev/null 2>&1; }

wait_for_service() {
    local url=$1 name=$2 max=30 attempt=1
    echo -e "${YELLOW}⏳ Waiting for $name...${NC}"
    while [ $attempt -le $max ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name ready${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e "${RED}❌ $name failed to start${NC}"
    return 1
}

# === PREREQUISITES ===
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Ollama
if ! command_exists ollama; then
    echo -e "${RED}❌ Ollama not found. Install from https://ollama.ai${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Ollama${NC}"

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}  → Starting Ollama...${NC}"
    ollama serve &>/dev/null &
    sleep 3
fi
echo -e "${GREEN}  ✓ Ollama running${NC}"

# Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Python 3${NC}"

# Node
if ! command_exists node; then
    echo -e "${RED}❌ Node.js not found${NC}"
    exit 1
fi
echo -e "${GREEN}  ✓ Node.js${NC}"

# === ENVIRONMENT SETUP ===
echo ""
echo -e "${BLUE}🔧 Setting up environment...${NC}"

# Create venv if needed
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}  → Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install backend deps
echo -e "${YELLOW}  → Installing backend dependencies...${NC}"
pip install -q -r "$CHAT_APP/backend/requirements.txt"

# Install frontend deps
echo -e "${YELLOW}  → Installing frontend dependencies...${NC}"
cd "$CHAT_APP/frontend"
npm install --silent 2>/dev/null
cd "$REPO_ROOT"

# === START SERVICES ===
echo ""
echo -e "${BLUE}🚀 Starting services...${NC}"

# Clear ports if in use
if port_in_use 8000; then
    echo -e "${YELLOW}  → Clearing port 8000...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

if port_in_use 5173; then
    echo -e "${YELLOW}  → Clearing port 5173...${NC}"
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Start backend
echo -e "${YELLOW}  → Starting backend (FastAPI + Nola)...${NC}"
cd "$CHAT_APP/backend"
"$VENV_DIR/bin/uvicorn" main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd "$REPO_ROOT"

# Start frontend
echo -e "${YELLOW}  → Starting frontend (React + Vite)...${NC}"
cd "$CHAT_APP/frontend"
npm run dev &>/dev/null &
FRONTEND_PID=$!
cd "$REPO_ROOT"

# Wait for services
echo ""
wait_for_service "http://localhost:8000/health" "Backend API"
wait_for_service "http://localhost:5173" "Frontend App"

# === SUCCESS ===
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎉 Nola is ready to chat!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Chat UI:${NC}   http://localhost:5173"
echo -e "  ${CYAN}API:${NC}       http://localhost:8000"
echo -e "  ${CYAN}API Docs:${NC}  http://localhost:8000/docs"
echo ""
echo -e "  ${BLUE}Nola:${NC}      $NOLA_DIR"
echo -e "  ${BLUE}Convos:${NC}    $NOLA_DIR/Stimuli/conversations/"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Open browser
if command_exists open; then
    open "http://localhost:5173"
elif command_exists xdg-open; then
    xdg-open "http://localhost:5173"
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Done${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
