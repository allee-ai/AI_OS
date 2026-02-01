#!/bin/bash
# Create a distributable DMG installer for AI OS
# Creates an installer that downloads AI OS to ~/AI_OS

set -e

APP_NAME="AI OS"
DMG_NAME="AIOS-Installer"
DMG_VOLUME_NAME="AI OS"
VERSION="1.0.0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Creating AI OS DMG Installer..."

# Build the installer app
echo "🔨 Building Install AI OS.app..."
chmod +x create_installer_app.sh
./create_installer_app.sh

if [ ! -d "Install AI OS.app" ]; then
    echo "❌ Failed to create installer app"
    exit 1
fi

# Create a temporary directory for DMG contents
DMG_TEMP="dmg_staging"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# Copy the installer app
echo "📁 Copying Install AI OS.app..."
cp -R "Install AI OS.app" "$DMG_TEMP/"

# Create a README
cat > "$DMG_TEMP/README.txt" << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║              🧠 AI OS - Installation Guide                ║
╚═══════════════════════════════════════════════════════════╝

1. Double-click "Install AI OS" to begin installation

2. The installer will:
   - Download AI OS to your home folder (~/AI_OS)
   - Check for required software (Python, Node.js, Ollama)
   - Help you install anything missing
   - Create AIOS.app in your Applications folder

3. First run will download AI models (~4GB) - this only happens once

REQUIREMENTS:
- macOS 10.15 or later
- Internet connection (for download)
- ~8GB free disk space

WHAT GETS INSTALLED:
- ~/AI_OS/           - The AI OS code and data
- /Applications/AIOS.app - Easy launcher

NEED HELP?
- GitHub: https://github.com/allee-ai/AI_OS
- Issues: https://github.com/allee-ai/AI_OS/issues
EOF

# Remove old DMG if exists
rm -f "${DMG_NAME}.dmg"
rm -f "${DMG_NAME}-temp.dmg"

# Create temporary DMG (read-write)
echo "💿 Creating DMG..."
hdiutil create -volname "$DMG_VOLUME_NAME" \
    -srcfolder "$DMG_TEMP" \
    -ov -format UDRW \
    "${DMG_NAME}-temp.dmg"

# Mount the temporary DMG
echo "🔧 Configuring DMG appearance..."
MOUNT_DIR=$(hdiutil attach -readwrite -noverify "${DMG_NAME}-temp.dmg" | grep "/Volumes/" | sed 's/.*\/Volumes/\/Volumes/')

# Set DMG window properties using AppleScript
osascript << EOF
tell application "Finder"
    tell disk "$DMG_VOLUME_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {400, 100, 850, 380}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set position of item "Install AI OS.app" of container window to {225, 130}
        set position of item "README.txt" of container window to {380, 220}
        close
        open
        update without registering applications
        delay 2
    end tell
end tell
EOF

# Unmount
echo "📤 Finalizing..."
sync
hdiutil detach "$MOUNT_DIR" -quiet

# Convert to compressed read-only DMG
hdiutil convert "${DMG_NAME}-temp.dmg" \
    -format UDZO \
    -imagekey zlib-level=9 \
    -o "${DMG_NAME}.dmg"

# Clean up
rm -rf "$DMG_TEMP"
rm -f "${DMG_NAME}-temp.dmg"

echo ""
echo "🌀 Created: ${DMG_NAME}.dmg"
echo ""
echo "📋 What users see when they open it:"
echo "   ┌─────────────────────────────────┐"
echo "   │                                 │"
echo "   │        [Install AI OS.app]          │"
echo "   │                                     │"
echo "   │              README.txt             │"
echo "   │                                     │"
echo "   └─────────────────────────────────────┘"
echo ""
echo "📦 The installer will:"
echo "   1. Clone AI OS to ~/AI_OS"
echo "   2. Check/install dependencies"  
echo "   3. Create AIOS.app in /Applications"
echo ""
echo "🚀 Share ${DMG_NAME}.dmg - one double-click to install!"