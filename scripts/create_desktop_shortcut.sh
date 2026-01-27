#!/bin/bash
# Create desktop shortcuts for AI OS (cross-platform)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Creating desktop shortcuts for AI OS..."

# macOS - Create app bundle
if [[ "$OSTYPE" == "darwin"* ]]; then
    ./create_app_bundle.sh
    echo ""
    echo "🍎 macOS: Use AIOS.app bundle created in current directory"
    
# Linux - Create .desktop file
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    cat > "$HOME/Desktop/aios.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=AI OS
Comment=Local AI Operating System
Exec=$SCRIPT_DIR/start.sh
Icon=$SCRIPT_DIR/aios-icon.png
Terminal=true
Categories=Development;Utility;
StartupNotify=true
EOF
    
    chmod +x "$HOME/Desktop/aios.desktop"
    echo "🌀 Created desktop shortcut: ~/Desktop/aios.desktop"
    
# Windows (Git Bash/WSL) - Create batch file
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    cat > "$HOME/Desktop/AI OS.bat" << EOF
@echo off
cd /d "$SCRIPT_DIR"
start cmd /k "./start.sh"
EOF
    echo "🌀 Created desktop shortcut: ~/Desktop/AI OS.bat"
    
else
    echo "⚠️ Unsupported OS type: $OSTYPE"
    echo "💡 You can manually create a shortcut to: $SCRIPT_DIR/start.sh"
fi

echo ""
echo "🎯 Desktop shortcut created!"
echo "💫 Double-click to launch AI OS"