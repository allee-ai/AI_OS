#!/bin/bash
# Nola AI OS - VM/Linux Installer
# Modified for VM deployment (removes Mac-specific parts)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            🧠 Nola AI OS - VM Setup                      ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/db
mkdir -p Nola/temp_memory
mkdir -p Nola/workspace

# Check/Install dependencies
echo ""
echo "🔍 Checking dependencies..."

# Update package lists
echo "📦 Updating package lists..."
apt update

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  ✅ Python: $PYTHON_VERSION"
    # Ensure python3-venv is installed
    apt install -y python3-venv python3-pip
else
    echo "  📦 Installing Python..."
    apt install -y python3 python3-pip python3-venv
fi

# Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "  ✅ Node.js: $NODE_VERSION"
else
    echo "  📦 Installing Node.js..."
    apt install -y nodejs npm
fi

# Git
if command -v git &> /dev/null; then
    echo "  ✅ Git: installed"
else
    echo "  📦 Installing Git..."
    apt install -y git
fi

# Install Ollama
echo ""
echo "🤖 Installing Ollama..."
if command -v ollama &> /dev/null; then
    echo "  ✅ Ollama: already installed"
else
    echo "  📦 Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh
    systemctl enable ollama
    systemctl start ollama
    
    echo "  ℹ️  Ollama installed. You can pull models manually with: ollama pull <model>"
fi

# Install Python dependencies
echo ""
echo "📦 Installing Python dependencies..."

if command -v uv &> /dev/null; then
    echo "  ⚡ Using uv for fast installation..."
    uv sync
else
    # Fallback to standard pip
    if [ ! -d ".venv" ]; then
        echo "  → Creating virtual environment (.venv)..."
        python3 -m venv .venv
    fi
    source .venv/bin/activate
    
    echo "  → Installing core requirements..."
    pip3 install -r requirements.txt
    if [ -f "Nola/react-chat-app/backend/requirements.txt" ]; then
        echo "  → Installing backend requirements..."
        pip3 install -r Nola/react-chat-app/backend/requirements.txt
    fi
fi

# Install Node dependencies for frontend
echo ""
echo "📦 Installing Node dependencies..."
if [ -d "Nola/react-chat-app/frontend" ]; then
    cd "Nola/react-chat-app/frontend"
    npm install
    echo "  → Building frontend..."
    npm run build
    cd "$SCRIPT_DIR"
fi

# Create systemd service
echo ""
echo "🔧 Creating systemd service..."

cat > /etc/systemd/system/nola.service << 'EOF'
[Unit]
Description=Nola AI Backend
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/AI_OS/Nola/react-chat-app/backend
Environment=PATH=/root/AI_OS/.venv/bin
Environment=PYTHONPATH=/root/AI_OS
Environment=NOLA_MODE=production
ExecStart=/root/AI_OS/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

# Enable and start service
systemctl daemon-reload
systemctl enable nola
systemctl start nola

# Create marker file
touch ".nola_installed"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                  ✅ VM Setup Complete!                    ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 Nola is now running as a service:"
echo "   • Backend: http://YOUR-VM-IP:8000"
echo "   • Status: systemctl status nola"
echo "   • Logs: journalctl -u nola -f"
echo ""
echo "🔗 From your Mac, create SSH tunnel:"
echo "   ssh -L 8000:localhost:8000 root@$(curl -s ifconfig.me)"
echo "   Then open: http://localhost:8000"
echo ""