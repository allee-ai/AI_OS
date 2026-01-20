#!/bin/bash
# Create a distributable DMG installer for Nola AI OS
# Creates the classic "drag to Applications" experience

set -e

APP_NAME="Nola AI OS"
DMG_NAME="Nola-AI-OS-Installer"
DMG_VOLUME_NAME="Nola AI OS"
VERSION="1.0.0"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Creating Nola AI OS DMG Installer..."

# Make sure Nola.app exists
if [ ! -d "Nola.app" ]; then
    echo "🔨 Building Nola.app first..."
    ./create_app_bundle.sh
fi

# Create a temporary directory for DMG contents
DMG_TEMP="dmg_staging"
rm -rf "$DMG_TEMP"
mkdir -p "$DMG_TEMP"

# Copy the app bundle
echo "📁 Copying Nola.app..."
cp -R "Nola.app" "$DMG_TEMP/"

# Create Applications symlink for drag-and-drop install
echo "🔗 Creating Applications shortcut..."
ln -s /Applications "$DMG_TEMP/Applications"

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
        set bounds of container window to {400, 100, 900, 400}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 100
        set position of item "Nola.app" of container window to {125, 150}
        set position of item "Applications" of container window to {375, 150}
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
echo "✅ Created: ${DMG_NAME}.dmg"
echo ""
echo "📋 What users see when they open it:"
echo "   ┌─────────────────────────────────┐"
echo "   │                                 │"
echo "   │    [Nola.app]  →  [Applications]│"
echo "   │                                 │"
echo "   └─────────────────────────────────┘"
echo ""
echo "🚀 Share ${DMG_NAME}.dmg - users just drag & drop to install!"