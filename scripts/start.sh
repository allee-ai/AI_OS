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
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ── Help ─────────────────────────────────────────────────────────────────
show_help() {
    echo ""
    echo -e "${BOLD}AI_OS — Universal Launcher${NC}"
    echo ""
    echo -e "${BOLD}USAGE${NC}"
    echo -e "  bash scripts/start.sh ${DIM}[FLAG]${NC}"
    echo ""
    echo -e "${BOLD}LAUNCH MODES${NC}"
    echo -e "  ${CYAN}(no flag)${NC}          Auto-detect: GUI with frontend, or headless if no display"
    echo -e "  ${CYAN}--headless${NC}         Start backend API only (no frontend)"
    echo -e "  ${CYAN}--no-frontend${NC}      Alias for --headless"
    echo -e "  ${CYAN}--cli${NC}              Launch interactive CLI directly (no server, no frontend)"
    echo -e "  ${CYAN}--help${NC}             Show this help"
    echo ""
    echo -e "${BOLD}ENVIRONMENT VARIABLES${NC}"
    echo -e "  ${CYAN}AIOS_MODE${NC}              personal (default)"
    echo -e "  ${CYAN}AIOS_MODEL_PROVIDER${NC}    ollama (default) | openai"
    echo -e "  ${CYAN}AIOS_MODEL_NAME${NC}        qwen2.5:7b (default)"
    echo -e "  ${CYAN}AIOS_FEED_BRIDGE${NC}       0 (default) | 1"
    echo ""
    echo -e "${BOLD}ONCE RUNNING${NC}"
    echo -e "  Open a second terminal and run: ${CYAN}python cli.py${NC}"
    echo ""
    echo -e "${BOLD}CLI COMMANDS (inside python cli.py)${NC}"
    echo ""
    echo -e "  ${GREEN}Chat${NC}          Just type a message to talk to the agent"
    echo ""
    echo -e "  ${GREEN}System${NC}"
    echo -e "    /status                   Subconscious stats, loops, queue depth"
    echo -e "    /config                   Show current configuration"
    echo -e "    /config set <key> <val>    Set an env var for this session"
    echo ""
    echo -e "  ${GREEN}Memory${NC}"
    echo -e "    /memory                   List recent temp_memory facts"
    echo -e "    /memory approve <id>       Approve a pending fact"
    echo -e "    /memory reject <id>        Reject a pending fact"
    echo ""
    echo -e "  ${GREEN}Knowledge Graph${NC}"
    echo -e "    /graph <query>             Spread-activate concept graph"
    echo -e "    /mindmap                   Structural shape of the agent's mind"
    echo -e "    /mindmap links             Include cross-thread associative edges"
    echo -e "    /mindmap <thread>          Show one thread (identity, philosophy, ...)"
    echo ""
    echo -e "  ${GREEN}Background Loops${NC}"
    echo -e "    /loops                     Show all loop stats"
    echo -e "    /loops new                 Create a custom loop (interactive)"
    echo -e "    /loops custom              List custom loops"
    echo -e "    /loops delete <name>       Delete a custom loop"
    echo -e "    /loops pause <name>        Pause a running loop"
    echo -e "    /loops resume <name>       Resume a paused loop"
    echo -e "    /loops interval <n> <s>    Change loop interval (seconds)"
    echo -e "    /loops run memory          Run one extraction cycle"
    echo -e "    /loops run consolidation   Run one consolidation cycle"
    echo -e "    /loops extract <text>       Dry-run fact extraction"
    echo -e "    /loops model <name>         Change extraction model"
    echo -e "    /loops provider <name>      Change extraction provider"
    echo -e "    /loops context <name> on|off Toggle STATE injection"
    echo -e "    /loops prompts <name>       View/edit loop prompts"
    echo ""
    echo -e "  ${GREEN}Thoughts${NC}"
    echo -e "    /thoughts                  Show recent proactive thoughts"
    echo -e "    /thoughts think            Trigger one thought cycle now"
    echo -e "    /thoughts <category>       Filter: insight, alert, reminder, suggestion, question"
    echo ""
    echo -e "  ${GREEN}Tasks${NC}"
    echo -e "    /tasks                     List tasks"
    echo -e "    /tasks new <goal>           Create and execute a task now"
    echo -e "    /tasks queue <goal>         Queue for background execution"
    echo -e "    /tasks <id>                 Show task details"
    echo -e "    /tasks cancel <id>          Cancel a pending task"
    echo ""
    echo -e "  ${GREEN}Tools${NC}"
    echo -e "    /tools                     List all tools"
    echo -e "    /tools <name>              Show tool details"
    echo -e "    /tools run <name> <action>  Execute a tool action (+ JSON params)"
    echo -e "    /tools new                  Create a tool (interactive)"
    echo -e "    /tools code <name>          Show tool's executable code"
    echo -e "    /tools toggle <name>        Enable/disable a tool"
    echo -e "    /tools delete <name>        Delete a tool"
    echo -e "    /tools categories           List tool categories"
    echo ""
    echo -e "  ${GREEN}Identity${NC}"
    echo -e "    /identity                  List identity profiles"
    echo -e "    /identity <profile>         Show facts for a profile"
    echo -e "    /identity new               Create profile (interactive)"
    echo -e "    /identity fact <p> <k> <v>  Add/update a fact"
    echo -e "    /identity delete <profile>  Delete profile"
    echo ""
    echo -e "  ${GREEN}Philosophy${NC}"
    echo -e "    /philosophy                List philosophy profiles"
    echo -e "    /philosophy <profile>       Show stances for a profile"
    echo -e "    /philosophy new             Create profile (interactive)"
    echo -e "    /philosophy fact <p> <k> <v> Add/update a stance"
    echo -e "    /philosophy delete <profile> Delete profile"
    echo ""
    echo -e "  ${GREEN}Log / Timeline${NC}"
    echo -e "    /log                       Recent timeline"
    echo -e "    /log events [type]          Raw events (optionally filtered)"
    echo -e "    /log search <query>         Search events"
    echo -e "    /log types                  List event types"
    echo -e "    /log stats                  Log statistics"
    echo ""
    echo -e "  ${GREEN}Workspace / Files${NC}"
    echo -e "    /files [path]              List directory (default /)"
    echo -e "    /files read <path>          Show file content"
    echo -e "    /files search <query>       Search files"
    echo -e "    /files stats                Workspace statistics"
    echo ""
    echo -e "  ${GREEN}Conversations${NC}"
    echo -e "    /convos                    List recent conversations"
    echo -e "    /convos <id>                Show conversation turns"
    echo -e "    /convos search <query>      Search conversations"
    echo -e "    /convos new [name]          Create new conversation"
    echo -e "    /convos delete <id>         Delete conversation"
    echo ""
    echo -e "  ${GREEN}Feeds${NC}"
    echo -e "    /feeds                     List feed sources"
    echo -e "    /feeds templates            Available integrations"
    echo -e "    /feeds toggle <name>        Enable/disable a feed"
    echo -e "    /feeds test <name>          Test feed connection"
    echo ""
    echo -e "  ${GREEN}Reflexes${NC}"
    echo -e "    /triggers                  List reflex triggers"
    echo -e "    /triggers <id>              Show trigger details"
    echo -e "    /triggers new               Create trigger (interactive)"
    echo -e "    /triggers toggle <id>       Toggle a trigger on/off"
    echo -e "    /triggers delete <id>       Delete a trigger"
    echo -e "    /protocols                 List protocol templates"
    echo -e "    /protocols install <name>   Install a protocol bundle"
    echo ""
    echo -e "  ${GREEN}Testing${NC}"
    echo -e "    /test                      Run full test suite"
    echo -e "    /test flows                Run flow tests only"
    echo -e "    /test pure                 Run pure-function tests only"
    echo ""
    echo -e "  ${GREEN}Session${NC}"
    echo -e "    /clear                     Clear message history"
    echo -e "    /help                      Show help inside the CLI"
    echo -e "    /quit                      Exit"
    echo ""
    exit 0
}

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    show_help
fi

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

# Detect headless environment (no display / SSH session)
detect_headless() {
    # Explicit flag
    if [ "$1" = "--headless" ] || [ "$1" = "--no-frontend" ]; then
        return 0
    fi
    # SSH session without display forwarding
    if [ -n "$SSH_TTY" ] || [ -n "$SSH_CONNECTION" ]; then
        if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ]; then
            return 0
        fi
    fi
    # No display server at all
    if [ -z "$DISPLAY" ] && [ -z "$WAYLAND_DISPLAY" ] && [ "$(uname -s)" = "Linux" ]; then
        return 0
    fi
    return 1
}

OS=$(detect_os)
TERM_TYPE=$(detect_terminal)
HEADLESS=false
if detect_headless "$1"; then
    HEADLESS=true
fi

echo ""
echo -e "${CYAN}===============================================================${NC}"
echo -e "${CYAN}               AI_OS Universal Launcher                        ${NC}"
echo -e "${CYAN}===============================================================${NC}"
echo ""
echo -e "${BLUE}Operating System: ${NC}${OS}"
echo -e "${BLUE}Environment: ${NC}${TERM_TYPE}"
if [ "$HEADLESS" = true ]; then
    echo -e "${BLUE}Mode: ${NC}${YELLOW}headless (no frontend)${NC}"
fi
echo ""

# ============================================================================
# STARTUP CONFIGURATION
# ============================================================================

# Default settings (can be overridden by environment variables)
: "${AIOS_MODE:=personal}"

export AIOS_MODE

echo ""
echo -e "${GREEN}Configuration:${NC}"
echo -e "   Mode: ${CYAN}${AIOS_MODE}${NC}"
echo ""

# Check if we're on a supported platform
case "$OS" in
    "windows")
        if ! command -v bash >/dev/null 2>&1; then
            echo -e "${RED}Windows detected but Bash not available${NC}"
            echo -e "${YELLOW}Install Git Bash or WSL to run AI_OS${NC}"
            if [ "$TERM_TYPE" = "gui" ]; then
                echo ""
                read -n 1 -s -r -p "Press any key to close..."
            fi
            exit 1
        fi
        echo -e "${GREEN}Windows with Bash detected${NC}"
        ;;
    "macos"|"linux")
        echo -e "${GREEN}Unix-like system detected${NC}"
        ;;
    *)
        echo -e "${RED}Unsupported operating system: ${OS}${NC}"
        if [ "$TERM_TYPE" = "gui" ]; then
            echo ""
            read -n 1 -s -r -p "Press any key to close..."
        fi
        exit 1
        ;;
esac

# Get repo root (parent of scripts/ directory)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Load optional .env
if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    source "$REPO_ROOT/.env"
    set +a
fi

# Verify we're in the right place
if [ ! -d "$REPO_ROOT/agent" ]; then
    echo -e "${RED}the agent directory not found at $REPO_ROOT/agent${NC}"
    if [ "$TERM_TYPE" = "gui" ]; then
        echo ""
        read -n 1 -s -r -p "Press any key to close..."
    fi
    exit 1
fi

AIOS_DIR="$REPO_ROOT/agent"

# Frontend location (now at project root)
FRONTEND_DIR="$REPO_ROOT/frontend"
VENV_DIR="$REPO_ROOT/.venv"

# Helper functions
command_exists() { command -v "$1" >/dev/null 2>&1; }
port_in_use() {
    if command -v lsof >/dev/null 2>&1; then
        lsof -i:"$1" >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | grep -q ":$1 "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tln 2>/dev/null | grep -q ":$1 "
    else
        # Fallback: use Python to check the port
        python3 -c "import socket; s=socket.socket(); s.settimeout(0.5); exit(0 if s.connect_ex(('127.0.0.1',$1))==0 else 1); s.close()" 2>/dev/null
    fi
}


wait_for_service() {
    local url=$1 name=$2 max=30 attempt=1
    echo -e "${YELLOW}Waiting for $name...${NC}"
    while [ $attempt -le $max ]; do
        if curl -s "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}$name ready${NC}"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done
    echo -e "${RED}$name failed to start${NC}"
    return 1
}

# === PREREQUISITES ===
echo -e "${BLUE}Checking prerequisites...${NC}"

MODEL_PROVIDER="${AIOS_MODEL_PROVIDER:-ollama}"
MODEL_NAME="${AIOS_MODEL_NAME:-qwen2.5:7b}"

# Ollama (only when provider=ollama)
if [ "$MODEL_PROVIDER" = "ollama" ]; then
    if ! command_exists ollama; then
        echo -e "${RED}Ollama not found. Install from https://ollama.ai${NC}"
        exit 1
    fi
    echo -e "${GREEN}  Ollama${NC}"

    # Start Ollama if not running
    if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo -e "${YELLOW}  Starting Ollama...${NC}"
        ollama serve &>/dev/null &
        OLLAMA_PID=$!
        sleep 3
    fi

# Auto-pull configured model (show progress - first download is ~4GB)
    echo -e "${YELLOW}  Checking model '${MODEL_NAME}'...${NC}"
    if ! ollama list | grep -q "$MODEL_NAME"; then
        echo -e "${YELLOW}  Downloading '${MODEL_NAME}' (first run only, ~4GB)...${NC}"
        ollama pull "$MODEL_NAME"
    fi
     
    # Auto-pull embedding model (needed for memory consolidation)
    echo -e "${YELLOW}  Checking embedding model...${NC}"
    if ! ollama list | grep -q "nomic-embed-text"; then
        echo -e "${YELLOW}  Downloading 'nomic-embed-text' (first run only, ~275MB)...${NC}"
        ollama pull nomic-embed-text
    fi
    
    echo -e "${GREEN}  Ollama running (${MODEL_NAME} + embeddings)${NC}"
else
    echo -e "${YELLOW}Skipping Ollama (provider=${MODEL_PROVIDER})${NC}"
fi

# Python
if ! command_exists python3; then
    echo -e "${RED}Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}  Python 3${NC}"

# Node (only required for frontend)
if [ "$HEADLESS" = true ]; then
    if command_exists node; then
        echo -e "${GREEN}  Node.js (available, not needed in headless mode)${NC}"
    else
        echo -e "${YELLOW}  Node.js not found (not needed in headless mode)${NC}"
    fi
else
    if ! command_exists node; then
        echo -e "${RED}Node.js not found${NC}"
        exit 1
    fi
    echo -e "${GREEN}  Node.js${NC}"
fi

# === ENVIRONMENT SETUP ===
echo ""
echo -e "${BLUE}Setting up environment...${NC}"

# Create venv if needed
# We rely on uv to manage the environment now, but keep this check for non-uv fallback logic if needed later
# or just let uv handle it.

# Install/Sync dependencies logic
if command -v uv >/dev/null 2>&1; then
    echo -e "${YELLOW}  Syncing dependencies with uv...${NC}"
    # Ensure virtualenv execution
    uv sync
else
    # Fallback for systems without uv
    if [ ! -d "$VENV_DIR" ]; then
        echo -e "${YELLOW}  Creating virtual environment...${NC}"
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"
    
    echo -e "${YELLOW}  Installing backend dependencies (pip)...${NC}"
    pip install -q -r "$REPO_ROOT/requirements.txt"
fi

# Install frontend deps (skip in headless mode)
if [ "$HEADLESS" != true ]; then
    echo -e "${YELLOW}  Installing frontend dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install --silent 2>/dev/null
    cd "$REPO_ROOT"
fi

# === START SERVICES ===
echo ""
echo -e "${BLUE}Starting services...${NC}"

# Clear Python cache to avoid stale bytecode
echo -e "${YELLOW}  Clearing Python cache...${NC}"
find "$REPO_ROOT" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$REPO_ROOT" -name "*.pyc" -delete 2>/dev/null || true

# Clear ports if in use
kill_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
    elif command -v fuser >/dev/null 2>&1; then
        fuser -k "$port/tcp" 2>/dev/null || true
    elif command -v ss >/dev/null 2>&1; then
        ss -tlnp 2>/dev/null | grep ":$port " | grep -oP 'pid=\K[0-9]+' | xargs kill -9 2>/dev/null || true
    fi
}
if port_in_use 8000; then
    echo -e "${YELLOW}  Clearing port 8000...${NC}"
    kill_port 8000
    sleep 1
fi

if [ "$HEADLESS" != true ] && port_in_use 5173; then
    echo -e "${YELLOW}  Clearing port 5173...${NC}"
    kill_port 5173
    sleep 1
fi

# Start backend with mode env vars already set
echo -e "${YELLOW}  Starting backend (scripts.server)...${NC}"
export PYTHONDONTWRITEBYTECODE=1
export AIOS_MODE="${AIOS_MODE}"

# ── CLI-only mode (no server, no frontend) ────────────────────────────
if [ "$1" = "--cli" ]; then
    echo -e "${CYAN}  Launching CLI interface (no server, no frontend)...${NC}"
    if command -v uv >/dev/null 2>&1; then
        exec uv run python "$REPO_ROOT/cli.py" "${@:2}"
    else
        exec "$VENV_DIR/bin/python" "$REPO_ROOT/cli.py" "${@:2}"
    fi
fi
# ───────────────────────────────────────────────────────────────────────

# Use uv run if available (ensures correct venv), otherwise fallback to direct venv python
if command -v uv >/dev/null 2>&1; then
    uv run python -m uvicorn scripts.server:app --host 0.0.0.0 --port 8000 &
else
    "$VENV_DIR/bin/python" -m uvicorn scripts.server:app --host 0.0.0.0 --port 8000 &
fi
BACKEND_PID=$!

FRONTEND_PID=""

if [ "$HEADLESS" = true ]; then
    # Headless: backend only
    echo ""
    wait_for_service "http://localhost:8000/health" "Backend API"

    echo ""
    echo -e "${GREEN}===============================================================${NC}"
    echo -e "${GREEN}  the agent is ready! (headless mode)${NC}"
    echo -e "${GREEN}===============================================================${NC}"
    echo ""
    echo -e "  ${CYAN}API:${NC}       http://localhost:8000"
    echo -e "  ${CYAN}API Docs:${NC}  http://localhost:8000/docs"
    echo -e "  ${CYAN}CLI:${NC}       python cli.py"
    echo ""
    echo -e "  ${BLUE}Agent:${NC}      $AIOS_DIR"
    echo -e "  ${BLUE}Convos:${NC}    $AIOS_DIR/Feeds/conversations/"
    echo ""
    echo -e "${YELLOW}Tip:${NC} Open a second terminal and run ${CYAN}python cli.py${NC} to chat."
    echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
    echo ""
else
    # GUI: start frontend too
    echo -e "${YELLOW}  Starting frontend (React + Vite)...${NC}"
    (cd "$FRONTEND_DIR" && npm run dev) &>/dev/null &
    FRONTEND_PID=$!

    # Wait for services
    echo ""
    wait_for_service "http://localhost:8000/health" "Backend API"
    wait_for_service "http://localhost:5173" "Frontend App"

    echo ""
    echo -e "${GREEN}===============================================================${NC}"
    echo -e "${GREEN}  the agent is ready to chat!${NC}"
    echo -e "${GREEN}===============================================================${NC}"
    echo ""
    echo -e "  ${CYAN}Chat UI:${NC}   http://localhost:5173"
    echo -e "  ${CYAN}API:${NC}       http://localhost:8000"
    echo -e "  ${CYAN}API Docs:${NC}  http://localhost:8000/docs"
    echo ""
    echo -e "  ${BLUE}Agent:${NC}      $AIOS_DIR"
    echo -e "  ${BLUE}Convos:${NC}    $AIOS_DIR/Feeds/conversations/"
    echo ""
    echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
    echo ""

    # Open browser to dashboard
    if command_exists open; then
        open "http://localhost:5173/"
    elif command_exists xdg-open; then
        xdg-open "http://localhost:5173/"
    fi
fi

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null || true
    if [ -n "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    if [ -n "$OLLAMA_PID" ]; then
        kill $OLLAMA_PID 2>/dev/null || true
    fi
    
    # Clean up SQLite WAL files to prevent "database is locked" on next start
    sleep 0.5
    rm -f "$REPO_ROOT/data/db/state.db-shm" "$REPO_ROOT/data/db/state.db-wal" 2>/dev/null
    
    echo -e "${GREEN}Done${NC}"
    
    # Handle GUI vs terminal cleanup
    if [ "$TERM_TYPE" = "gui" ]; then
        echo ""
        read -n 1 -s -r -p "Press any key to close..."
    fi
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

wait
