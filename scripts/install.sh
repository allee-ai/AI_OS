#!/bin/bash
# AI OS - First Run Installer
# This script runs automatically on first launch to set up everything

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║            🧠 AI OS - First Time Setup               ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Make all scripts executable
echo "📝 Setting up permissions..."
chmod +x *.sh 2>/dev/null || true
chmod +x *.command 2>/dev/null || true

# Create data directories
echo "📁 Creating data directories..."
mkdir -p data/db
mkdir -p agent/temp_memory
mkdir -p agent/workspace

# Check for the spiral icon and create app bundle
echo "🎨 Setting up desktop icon..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [ -f "aios-spiral.png" ]; then
        ./create_icon_from_image.sh
    fi
    ./create_app_bundle.sh
else
    echo "   (Skipping macOS app bundle creation on non-Mac system)"
fi

# Check dependencies
echo ""
echo "🔍 Checking dependencies..."

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "  🌀 Python: $PYTHON_VERSION"
else
    echo "  ❌ Python 3 not found - please install from python.org"
fi

# Node.js
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "  🌀 Node.js: $NODE_VERSION"
else
    echo "  ❌ Node.js not found - please install from nodejs.org"
fi

# npm
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "  🌀 npm: $NPM_VERSION"
else
    echo "  ❌ npm not found"
fi

# Ollama (optional)
if command -v ollama &> /dev/null; then
    echo "  🌀 Ollama: installed"
else
    echo "  ⚠️ Ollama not found (optional - needed for local AI)"
    echo "     Install: brew install ollama"
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
    pip3 install -r requirements.txt --quiet
fi

# Install Node dependencies for frontend
echo "📦 Installing Node dependencies..."
if [ -d "frontend" ]; then
    cd "frontend"
    npm install --silent 2>/dev/null || echo "  ⚠️ Run 'npm install' in frontend directory"
    cd "$SCRIPT_DIR"
fi

# Create marker file so we don't run setup again
touch ".aios_installed"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                  🌀 Setup Complete!                       ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 To start AI OS:"
echo "   • Double-click AIOS.app"
echo "   • Or run: ./start.sh"
echo ""
echo "📍 App bundle created at: $SCRIPT_DIR/AIOS.app"
echo "   Drag to Applications folder or Dock for easy access"
echo ""
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "💡 To auto-start AI OS on login:"
    echo "   System Settings → General → Login Items → add AIOS.app"
    echo "   Or: drag AIOS.app to your Dock"
    echo ""
fi

# Ask if user wants to start now
read -p "🚀 Start the agent now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./start.sh
fi