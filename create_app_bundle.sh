#!/bin/bash
# Create Nola.app bundle for macOS desktop icon

echo "🧠 Creating Nola.app bundle..."

# Remove existing bundle if it exists
rm -rf "Nola.app"

# Create app bundle structure
mkdir -p "Nola.app/Contents/MacOS"
mkdir -p "Nola.app/Contents/Resources"

# Create Info.plist
cat > "Nola.app/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Nola AI OS</string>
    <key>CFBundleExecutable</key>
    <string>Nola</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.nola.ai-os</string>
    <key>CFBundleName</key>
    <string>Nola</string>
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

cat > "Nola.app/Contents/MacOS/Nola" << 'LAUNCHER'
#!/bin/bash
# macOS App Bundle Launcher for Nola AI OS
# This acts as a bridge to execute the run.command file in the actual repo

# Calculate repo path relative to this script: .../Nola.app/Contents/MacOS/Nola -> ../../../
# This allows the entire AI_OS folder to be moved or renamed without breaking the app
REPO_PATH="$(cd "$(dirname "$0")/../../.." && pwd)"
COMMAND_FILE="$REPO_PATH/run.command"

if [ -f "$COMMAND_FILE" ]; then
    # Opening a .command file forces macOS to open a new Terminal window and run it
    /usr/bin/open "$COMMAND_FILE"
else
    # Fallback error dialog
    osascript -e 'display dialog "Critical Error: Could not find run.command!\n\nExpected at: '"$REPO_PATH"'/run.command\n\nEnsure Nola.app is located inside the root of the Nola AI OS folder." buttons {"OK"} default button "OK" with icon stop'
fi
LAUNCHER

# Make launcher executable (IMPORTANT - must be executable for app to work)
chmod +x "Nola.app/Contents/MacOS/Nola"
chmod 755 "Nola.app/Contents/MacOS/Nola"

# Use the spiral icon if available, otherwise create a basic placeholder
if [ -f "NolaIcon.icns" ]; then
    cp "NolaIcon.icns" "Nola.app/Contents/Resources/AppIcon.icns"
    echo "🎨 Using purple spiral icon"
elif [ -f "nola-spiral.png" ]; then
    echo "🔄 Converting spiral image to icon..."
    ./create_icon_from_image.sh
else
    # Create a placeholder icon file
    echo "📝 Creating placeholder icon"
    echo "🧠" > "Nola.app/Contents/Resources/AppIcon.txt"
fi

echo "✅ Created Nola.app bundle"
echo ""
echo "🎯 Installation options:"
echo "  1. Drag 'Nola.app' to your Desktop"
echo "  2. Drag 'Nola.app' to Applications folder" 
echo "  3. Drag 'Nola.app' to Dock for quick access"
echo ""
echo "💡 Double-click Nola.app to launch Nola AI OS"
echo "📝 To customize icon: Replace AppIcon files in Nola.app/Contents/Resources/"