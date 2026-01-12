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

# Create launcher script that opens Terminal and runs start.sh
cat > "Nola.app/Contents/MacOS/Nola" << 'LAUNCHER'
#!/bin/bash
# macOS App Bundle Launcher for Nola AI OS

# Get the directory where this app bundle lives (escape spaces properly)
APP_DIR="$(cd "$(dirname "$0")/../../../" && pwd)"

# Open Terminal and run start.sh
osascript -e "tell application \"Terminal\"
    activate
    do script \"cd \\\"$APP_DIR\\\" && ./start.sh\"
end tell"
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