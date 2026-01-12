#!/bin/bash
# Quick Start Script for Wednesday Demo
# Run this to start everything you need

set -e  # Exit on error

echo "🎪 Starting Wednesday Demo Setup..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo "⚠️  IMPORTANT: Add your KERNEL_API_KEY to .env before running demo!"
    echo ""
fi

# Check for KERNEL_API_KEY
if ! grep -q "KERNEL_API_KEY=.*[a-zA-Z0-9]" .env 2>/dev/null; then
    echo "⚠️  KERNEL_API_KEY not set in .env"
    echo "   Get your key from: https://app.onkernel.com"
    echo "   Add it to .env: KERNEL_API_KEY=your_key_here"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
cd Nola/react-chat-app/backend

if ! python3 -c "import kernel" 2>/dev/null; then
    echo "📦 Installing Kernel SDK and Playwright..."
    pip install kernel playwright
    playwright install chromium
    echo "✅ Dependencies installed"
else
    echo "✅ Dependencies already installed"
fi

echo ""
echo "🚀 Starting backend server..."
echo "   (Press Ctrl+C to stop)"
echo ""

# Start the backend
python3 main.py
