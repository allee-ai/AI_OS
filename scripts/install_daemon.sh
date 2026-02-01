#!/bin/bash
# install_daemon.sh - Install/uninstall AI_OS as a macOS LaunchAgent
# 
# Usage:
#   ./install_daemon.sh install   - Install and start the daemon
#   ./install_daemon.sh uninstall - Stop and remove the daemon
#   ./install_daemon.sh status    - Check if daemon is running
#   ./install_daemon.sh restart   - Restart the daemon
#   ./install_daemon.sh logs      - Tail the daemon logs

set -e

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIOS_PATH="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.aios.server"
PLIST_SOURCE="$SCRIPT_DIR/com.aios.server.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME.plist"
LOG_DIR="$AIOS_PATH/data/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_requirements() {
    # Check if venv exists
    if [ ! -f "$AIOS_PATH/.venv/bin/python" ]; then
        log_error "Virtual environment not found at $AIOS_PATH/.venv"
        log_error "Please run the install script first: ./scripts/install.sh"
        exit 1
    fi
    
    # Check if uvicorn is installed
    if ! "$AIOS_PATH/.venv/bin/python" -c "import uvicorn" 2>/dev/null; then
        log_error "uvicorn not installed in virtual environment"
        log_error "Install it with: ./.venv/bin/pip install uvicorn"
        exit 1
    fi
    
    # Check if plist source exists
    if [ ! -f "$PLIST_SOURCE" ]; then
        log_error "LaunchAgent plist not found at $PLIST_SOURCE"
        exit 1
    fi
}

create_log_dir() {
    if [ ! -d "$LOG_DIR" ]; then
        log_info "Creating log directory: $LOG_DIR"
        mkdir -p "$LOG_DIR"
    fi
}

install_daemon() {
    log_info "Installing AI_OS daemon..."
    
    check_requirements
    create_log_dir
    
    # Create LaunchAgents directory if it doesn't exist
    mkdir -p "$HOME/Library/LaunchAgents"
    
    # Stop existing daemon if running
    if launchctl list | grep -q "$PLIST_NAME"; then
        log_info "Stopping existing daemon..."
        launchctl unload "$PLIST_DEST" 2>/dev/null || true
    fi
    
    # Copy and customize plist
    log_info "Installing LaunchAgent plist..."
    sed "s|__AIOS_PATH__|$AIOS_PATH|g" "$PLIST_SOURCE" > "$PLIST_DEST"
    
    # Load and start the daemon
    log_info "Starting daemon..."
    launchctl load "$PLIST_DEST"
    
    # Wait a moment and check status
    sleep 2
    
    if launchctl list | grep -q "$PLIST_NAME"; then
        log_info "✅ AI_OS daemon installed and running!"
        log_info "Server should be available at: http://127.0.0.1:8000"
        log_info ""
        log_info "Commands:"
        log_info "  Status:    $0 status"
        log_info "  Logs:      $0 logs"
        log_info "  Restart:   $0 restart"
        log_info "  Uninstall: $0 uninstall"
    else
        log_error "Failed to start daemon. Check logs:"
        log_error "  $LOG_DIR/server_stderr.log"
    fi
}

uninstall_daemon() {
    log_info "Uninstalling AI_OS daemon..."
    
    if [ -f "$PLIST_DEST" ]; then
        # Stop the daemon
        if launchctl list | grep -q "$PLIST_NAME"; then
            log_info "Stopping daemon..."
            launchctl unload "$PLIST_DEST"
        fi
        
        # Remove the plist
        log_info "Removing LaunchAgent plist..."
        rm "$PLIST_DEST"
        
        log_info "✅ AI_OS daemon uninstalled!"
    else
        log_warn "Daemon not installed (plist not found)"
    fi
}

daemon_status() {
    echo "AI_OS Daemon Status"
    echo "==================="
    
    if [ -f "$PLIST_DEST" ]; then
        echo "Plist: Installed at $PLIST_DEST"
    else
        echo "Plist: Not installed"
        return 1
    fi
    
    if launchctl list | grep -q "$PLIST_NAME"; then
        PID=$(launchctl list | grep "$PLIST_NAME" | awk '{print $1}')
        echo "Status: Running (PID: $PID)"
        
        # Check if server is responding
        if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8200/health 2>/dev/null | grep -q "200"; then
            echo "Server: Healthy (responding on port 8200)"
        else
            echo "Server: Not responding (may still be starting)"
        fi
    else
        echo "Status: Not running"
    fi
    
    # Show recent log entries
    echo ""
    echo "Recent stderr (last 5 lines):"
    if [ -f "$LOG_DIR/server_stderr.log" ]; then
        tail -5 "$LOG_DIR/server_stderr.log" 2>/dev/null || echo "  (no logs yet)"
    else
        echo "  (no log file)"
    fi
}

restart_daemon() {
    log_info "Restarting AI_OS daemon..."
    
    if [ ! -f "$PLIST_DEST" ]; then
        log_error "Daemon not installed. Run: $0 install"
        exit 1
    fi
    
    launchctl unload "$PLIST_DEST" 2>/dev/null || true
    sleep 1
    launchctl load "$PLIST_DEST"
    
    sleep 2
    daemon_status
}

tail_logs() {
    log_info "Tailing daemon logs (Ctrl+C to stop)..."
    echo ""
    
    # Create log files if they don't exist
    touch "$LOG_DIR/server_stdout.log" 2>/dev/null || true
    touch "$LOG_DIR/server_stderr.log" 2>/dev/null || true
    
    # Tail both logs
    tail -f "$LOG_DIR/server_stdout.log" "$LOG_DIR/server_stderr.log"
}

# Main
case "${1:-}" in
    install)
        install_daemon
        ;;
    uninstall)
        uninstall_daemon
        ;;
    status)
        daemon_status
        ;;
    restart)
        restart_daemon
        ;;
    logs)
        tail_logs
        ;;
    *)
        echo "AI_OS Daemon Manager"
        echo ""
        echo "Usage: $0 {install|uninstall|status|restart|logs}"
        echo ""
        echo "Commands:"
        echo "  install   - Install and start the daemon"
        echo "  uninstall - Stop and remove the daemon"
        echo "  status    - Check daemon status"
        echo "  restart   - Restart the daemon"
        echo "  logs      - Tail the daemon logs"
        exit 1
        ;;
esac
