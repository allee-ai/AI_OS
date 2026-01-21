#!/bin/bash
# start.sh - Universal AI_OS Launcher & Startup Script
# Cross-platform OS detection + service startup
# Usage: ./start.sh or double-click run.command

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos";;
        Linux*)     echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Detect if running from GUI or terminal
detect_terminal() {
    if [ -t 1 ]; then
        echo "terminal"
    else
        echo "gui"
    fi
}

OS=$(detect_os)
TERM_TYPE=$(detect_terminal)

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║               🧠 AI_OS Universal Launcher                 ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🖥️  Operating System: ${NC}${OS}"
echo -e "${BLUE}💻 Environment: ${NC}${TERM_TYPE}"
echo ""

# ============================================================================
# STARTUP MODE SELECTION (before starting any services)
# ============================================================================

# Allow override via environment variables
if [ -z "${NOLA_MODE:-}" ] || [ -z "${BUILD_METHOD:-}" ]; then
    if [ "$OS" = "macos" ]; then
        # macOS: Single dialog with buttons
        # Updated to include Dev Mode
        CHOICE=$(osascript <<'EOF'
tell application "System Events"
    activate
    set theResult to display dialog "🧠 Nola AI OS" & return & return & "Choose your configuration:" buttons {"Demo Mode", "Personal Mode", "Dev Mode"} default button "Dev Mode" with title "Nola Launcher" with icon note
    return button returned of theResult
end tell
EOF
        )
        if [ "$CHOICE" = "Demo Mode" ]; then
            export NOLA_MODE="demo"
            export DEV_MODE="false"
        elif [ "$CHOICE" = "Dev Mode" ]; then
            export NOLA_MODE="personal"
            export DEV_MODE="true"
        else
            export NOLA_MODE="personal"
            export DEV_MODE="false"
        fi
        export BUILD_METHOD="local"
    else
        # Linux/other: Terminal prompt
        echo -e "${BLUE}Select mode:${NC}"
        echo -e "  [1] Personal - Your private data"
        echo -e "  [2] Demo - Sample showcase data"
        echo -e "  [3] Dev Mode - Personal data + Dev tools"
        read -r -p "Choose 1, 2, or 3 [default: 3]: " MODE_CHOICE
        if [ "$MODE_CHOICE" = "2" ]; then
            export NOLA_MODE="demo"
            export DEV_MODE="false"
        elif [ "$MODE_CHOICE" = "1" ]; then
            export NOLA_MODE="personal"
            export DEV_MODE="false"
        else
            export NOLA_MODE="personal"
            export DEV_MODE="true"
        fi
        export BUILD_METHOD="local"
    fi
fi

echo ""
echo -e "${GREEN}📋 Configuration:${NC}"
echo -e "   Mode: ${CYAN}${NOLA_MODE}${NC}"
echo -e "   Build: ${CYAN}${BUILD_METHOD}${NC}"
echo ""

# Check if we're on a supported platform
case "$OS" in
    "windows")
        if ! command -v bash >/dev/null 2>&1; then
            echo -e "${RED}❌ Windows detected but Bash not available${NC}"
            echo -e "${YELLOW}💡 Install Git Bash or WSL to run AI_OS${NC}"
            if [ "$TERM_TYPE" = "gui" ]; then
                echo ""
                read -n 1 -s -r -p "Press any key to close..."
            fi
            exit 1
        fi
        echo -e "${GREEN}✅ Windows with Bash detected${NC}"
        ;;
    "macos"|"linux")
        echo -e "${GREEN}✅ Unix-like system detected${NC}"
        ;;
    *)
        echo -e "${RED}❌ Unsupported operating system: ${OS}${NC}"
        if [ "$TERM_TYPE" = "gui" ]; then
            echo ""
            read -n 1 -s -r -p "Press any key to close..."
        fi
        exit 1
        ;;
esac

# Get repo root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

# Load optional .env
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# Detect Nola directory
if [ -d "Nola" ]; then
    NOLA_DIR="$REPO_ROOT/Nola"
else
    echo -e "${RED}❌ Nola directory not found!${NC}"
    if [ "$TERM_TYPE" = "gui" ]; then
        echo ""
        read -n 1 -s -r -p "Press any key to close..."
    fi
    exit 1
fi

# Frontend location (now at project root)
FRONTEND_DIR="$REPO_ROOT/frontend"
VENV_DIR="$REPO_ROOT/.venv"

# Helper functions
command_exists() { command -v "$1" >/dev/null 2>&1; }
port_in_use() { lsof -i:"$1" >/dev/null 2>&1; }

install_docker_if_missing() {
    if command_exists docker; then
        return
    fi
    echo -e "${YELLOW}⚙️  Docker not found. Attempting install...${NC}"
    if [ "$OS" = "linux" ] && command_exists apt-get; then
        sudo apt-get update -y && sudo apt-get install -y docker.io docker-compose-plugin || {
            echo -e "${RED}❌ Docker install failed via apt-get${NC}"; exit 1; }
        if command_exists systemctl; then
            sudo systemctl enable docker >/dev/null 2>&1 || true
            sudo systemctl start docker >/dev/null 2>&1 || true
        fi
        echo -e "${GREEN}✅ Docker installed${NC}"
        echo -e "${YELLOW}ℹ️  If you see permission errors, add your user to the docker group and re-login:${NC}"
        echo -e "    sudo usermod -aG docker $USER && newgrp docker"
    elif [ "$OS" = "macos" ]; then
        # Try Homebrew auto-install if available (may require user interaction)
        if command_exists brew; then
            echo -e "${YELLOW}→ Homebrew found. Installing Docker Desktop via brew...${NC}"
            brew install --cask docker || {
                echo -e "${RED}❌ brew install failed. Please install Docker Desktop manually from https://www.docker.com/products/docker-desktop${NC}"
                exit 1
            }
            echo -e "${GREEN}✅ Docker Desktop installed via Homebrew.${NC}"
            echo -e "${YELLOW}ℹ️  Please start Docker Desktop (open /Applications/Docker.app) and wait until it's running. Press Enter to continue...${NC}"
            read -r
            return
        fi

        echo -e "${RED}❌ Docker not installed.${NC} Please install Docker Desktop from https://www.docker.com/products/docker-desktop and re-run."
        exit 1
    else
        echo -e "${RED}❌ Unsupported OS for auto-install. Install Docker manually and retry.${NC}"
        exit 1
    fi
}

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

# Mode selection now happens in the UI (StartupPage)
# Check if BUILD_METHOD requests Docker
if [ "${BUILD_METHOD}" = "docker" ]; then
    DOCKER_LAUNCH="$REPO_ROOT/Nola/react-chat-app/start-docker.sh"
    if [ ! -x "$DOCKER_LAUNCH" ]; then
        echo -e "${RED}❌ Docker launch script not found at $DOCKER_LAUNCH${NC}"
        exit 1
    fi
    install_docker_if_missing
    echo -e "${YELLOW}→ Starting Docker stack...${NC}"
    # Pass mode to docker environment
    export NOLA_MODE="${NOLA_MODE}"
    export DEV_MODE="${DEV_MODE}"
    exec "$DOCKER_LAUNCH"
fi

# === PREREQUISITES ===
echo -e "${BLUE}📋 Checking prerequisites...${NC}"

MODEL_PROVIDER="${NOLA_MODEL_PROVIDER:-ollama}"
MODEL_NAME="${NOLA_MODEL_NAME:-qwen2.5:7b}"

# Ollama (only when provider=ollama)
if [ "$MODEL_PROVIDER" = "ollama" ]; then
    if ! command_exists ollama; then
        echo -e "${RED}❌ Ollama not found. Install from https://ollama.ai${NC}"
        exit 1
    fi
    echo -e "${GREEN}  ✓ Ollama${NC}"

    # Start Ollama if not running
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo -e "${YELLOW}  → Starting Ollama...${NC}"
        ollama serve &>/dev/null &
        OLLAMA_PID=$!
        sleep 3
    fi

    # Auto-pull configured model
    echo -e "${YELLOW}  → Ensuring model '${MODEL_NAME}' is available...${NC}"
    ollama pull "$MODEL_NAME" >/dev/null 2>&1 || true
    
    # Auto-pull embedding model (needed for memory consolidation)
    echo -e "${YELLOW}  → Ensuring embedding model 'nomic-embed-text' is available...${NC}"
    ollama pull nomic-embed-text >/dev/null 2>&1 || true
    
    echo -e "${GREEN}  ✓ Ollama running (${MODEL_NAME} + embeddings)${NC}"
else
    echo -e "${YELLOW}⚡ Skipping Ollama (provider=${MODEL_PROVIDER})${NC}"
fi

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
# We rely on uv to manage the environment now, but keep this check for non-uv fallback logic if needed later
# or just let uv handle it.

# Install/Sync dependencies logic
if command -v uv >/dev/null 2>&1; then
    echo -e "${YELLOW}  → Syncing dependencies with uv...${NC}"
    # Ensure virtualenv execution
    uv sync
else
    # Fallback for systems without uv
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}  → Creating virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    
    echo -e "${YELLOW}  → Installing backend dependencies (pip)...${NC}"
    pip install -q -r "$REPO_ROOT/requirements.txt"
    pip install -q -r "$CHAT_APP/backend/requirements.txt"
fi

# Install frontend deps
echo -e "${YELLOW}  → Installing frontend dependencies...${NC}"
cd "$FRONTEND_DIR"
npm install --silent 2>/dev/null
cd "$REPO_ROOT"

# === START SERVICES ===
echo ""
echo -e "${BLUE}🚀 Starting services...${NC}"

# Clear Python cache to avoid stale bytecode
echo -e "${YELLOW}  → Clearing Python cache...${NC}"
find "$REPO_ROOT/Nola" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT/Nola" -name "*.pyc" -delete 2>/dev/null || true

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

# Start backend with mode env vars already set
echo -e "${YELLOW}  → Starting backend (Nola.server)...${NC}"
export PYTHONDONTWRITEBYTECODE=1
export NOLA_MODE="${NOLA_MODE}"
export DEV_MODE="${DEV_MODE}"
export BUILD_METHOD="${BUILD_METHOD}"

# Use uv run if available (ensures correct venv), otherwise fallback to direct venv python
if command -v uv >/dev/null 2>&1; then
    uv run python -m uvicorn Nola.server:app --host 0.0.0.0 --port 8000 &
else
    "$VENV_DIR/bin/python" -m uvicorn Nola.server:app --host 0.0.0.0 --port 8000 &
fi
BACKEND_PID=$!

# Start frontend
echo -e "${YELLOW}  → Starting frontend (React + Vite)...${NC}"
cd "$FRONTEND_DIR"
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

# Open browser to dashboard (mode already selected via dialogs)
if command_exists open; then
    open "http://localhost:5173/"
elif command_exists xdg-open; then
    xdg-open "http://localhost:5173/"
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}🛑 Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    if [ -n "$OLLAMA_PID" ]; then
        kill $OLLAMA_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}✅ Done${NC}"
    
    # Handle GUI vs terminal cleanup
    if [ "$TERM_TYPE" = "gui" ]; then
        echo ""
        read -n 1 -s -r -p "Press any key to close..."
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM

wait
