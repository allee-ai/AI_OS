#!/bin/bash
# start.sh - Quick start script for React Chat App (macOS/Linux)
# This script starts all services and opens the browser

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 React Chat App - Starting...${NC}"
echo ""

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    lsof -i:"$1" >/dev/null 2>&1
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for $name...${NC}"
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $name is ready!${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e "${RED}❌ $name failed to start${NC}"
    return 1
}

# Check prerequisites
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

# Check for Ollama
if ! command_exists ollama; then
    echo -e "${RED}❌ Ollama not found. Please install from https://ollama.ai${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Ollama installed${NC}"

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Ollama not running. Starting...${NC}"
    ollama serve &
    sleep 3
fi
echo -e "${GREEN}✅ Ollama running${NC}"

# Check for Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 installed${NC}"

# Check for Node.js
if ! command_exists node; then
    echo -e "${RED}❌ Node.js not found. Please install Node.js 18+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Node.js installed${NC}"

echo ""
echo -e "${BLUE}🔧 Setting up environment...${NC}"

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating Python virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install backend dependencies
echo -e "${YELLOW}Installing backend dependencies...${NC}"
pip install -q -r backend/requirements.txt

# Install frontend dependencies
echo -e "${YELLOW}Installing frontend dependencies...${NC}"
cd frontend
npm install --silent
cd ..

echo ""
echo -e "${BLUE}🚀 Starting services...${NC}"

# Kill any existing processes on our ports
if port_in_use 8000; then
    echo -e "${YELLOW}Stopping existing backend on port 8000...${NC}"
    lsof -ti:8000 | xargs kill -9 2>/dev/null || true
fi

if port_in_use 5173; then
    echo -e "${YELLOW}Stopping existing frontend on port 5173...${NC}"
    lsof -ti:5173 | xargs kill -9 2>/dev/null || true
fi

# Start backend
echo -e "${YELLOW}Starting backend server...${NC}"
cd backend
../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo -e "${YELLOW}Starting frontend server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for services to be ready
echo ""
wait_for_service "http://localhost:8000/health" "Backend API"
wait_for_service "http://localhost:5173" "Frontend App"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🎉 React Chat App is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "   ${BLUE}Frontend:${NC}  http://localhost:5173"
echo -e "   ${BLUE}Backend:${NC}   http://localhost:8000"
echo -e "   ${BLUE}API Docs:${NC}  http://localhost:8000/docs"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
echo ""

# Open browser
if command_exists open; then
    open "http://localhost:5173"
elif command_exists xdg-open; then
    xdg-open "http://localhost:5173"
fi

# Trap to cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down services...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    echo -e "${GREEN}✅ Cleanup complete${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Wait for processes
wait
