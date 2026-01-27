#!/bin/bash
# Create AIOS.app bundle for macOS desktop icon

echo "🧠 Creating AIOS.app bundle..."

# Remove existing bundle if it exists
rm -rf "AIOS.app"

# Create app bundle structure
mkdir -p "AIOS.app/Contents/MacOS"
mkdir -p "AIOS.app/Contents/Resources"

# Create Info.plist
cat > "AIOS.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>AI OS</string>
    <key>CFBundleExecutable</key>
    <string>AIOS</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.aios.ai-os</string>
    <key>CFBundleName</key>
    <string>AIOS</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.productivity</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>LSUIElement</key>
    <false/>
</dict>
</plist>
EOF

# Create launcher script that uses 'open' on run.command (most reliable method)
# Using relative path so the app works even if the folder is moved

cat > "AIOS.app/Contents/MacOS/Nola" << 'LAUNCHER'
#!/bin/bash
# macOS App Bundle Launcher for AI OS
# This acts as a bridge to execute the run.command file in the actual repo

# Calculate repo path relative to this script: .../AIOS.app/Contents/MacOS/Nola -> ../../../
# This allows the entire AI_OS folder to be moved or renamed without breaking the app
REPO_PATH="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMAND_FILE="$REPO_PATH/run.command"

if [ -f "$COMMAND_FILE" ]; then
    # Opening a .command file forces macOS to open a new Terminal window and run it
    /usr/bin/open "$COMMAND_FILE"
else
    # Fallback error dialog
    osascript -e 'display dialog "Critical Error: Could not find run.command!\n\nExpected at: '"$REPO_PATH"'/run.command\n\nEnsure AIOS.app is located inside the root of the AI OS folder." buttons {"OK"} default button "OK" with icon stop'
fi
LAUNCHER

# Make launcher executable (IMPORTANT - must be executable for app to work)
chmod +x "AIOS.app/Contents/MacOS/Nola"
chmod 755 "AIOS.app/Contents/MacOS/Nola"

# Use the spiral icon if available, otherwise create a basic placeholder
if [ -f "AIOSIcon.icns" ]; then
    cp "AIOSIcon.icns" "AIOS.app/Contents/Resources/AppIcon.icns"
    echo "🎨 Using purple spiral icon"
elif [ -f "aios-spiral.png" ]; then
    echo "🔄 Converting spiral image to icon..."
    ./create_icon_from_image.sh
else
    # Create a placeholder icon file
    echo "📝 Creating placeholder icon"
    echo "🧠" > "AIOS.app/Contents/Resources/AppIcon.txt"
fi

echo "🌀 Created AIOS.app bundle"
echo ""
echo "🎯 Installation options:"
echo "  1. Drag 'AIOS.app' to your Desktop"
echo "  2. Drag 'AIOS.app' to Applications folder" 
echo "  3. Drag 'AIOS.app' to Dock for quick access"
echo ""
echo "💡 Double-click AIOS.app to launch AI OS"
echo "📝 To customize icon: Replace AppIcon files in AIOS.app/Contents/Resources/"