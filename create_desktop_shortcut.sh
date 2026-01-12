#!/bin/bash
# Create desktop shortcuts for Nola AI OS (cross-platform)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Creating desktop shortcuts for Nola AI OS..."

# macOS - Create app bundle
if [[ "$OSTYPE" == "darwin"* ]]; then
    ./create_app_bundle.sh
    echo ""
    echo "🍎 macOS: Use Nola.app bundle created in current directory"
    
# Linux - Create .desktop file
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    cat > "$HOME/Desktop/nola-ai-os.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Nola AI OS
Comment=Local AI Operating System
Exec=$SCRIPT_DIR/start.sh
Icon=$SCRIPT_DIR/nola-icon.png
Terminal=true
Categories=Development;Utility;
StartupNotify=true
EOF
    
    chmod +x "$HOME/Desktop/nola-ai-os.desktop"
    echo "✅ Created desktop shortcut: ~/Desktop/nola-ai-os.desktop"
    
# Windows (Git Bash/WSL) - Create batch file
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    cat > "$HOME/Desktop/Nola AI OS.bat" << EOF
@echo off
cd /d "$SCRIPT_DIR"
start cmd /k "./start.sh"
EOF
    echo "✅ Created desktop shortcut: ~/Desktop/Nola AI OS.bat"
    
else
    echo "⚠️ Unsupported OS type: $OSTYPE"
    echo "💡 You can manually create a shortcut to: $SCRIPT_DIR/start.sh"
fi

echo ""
echo "🎯 Desktop shortcut created!"
echo "💫 Double-click to launch Nola AI OS"