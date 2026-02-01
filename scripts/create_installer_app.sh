#!/bin/bash
# Create "Install AI OS.app" - a downloader/installer for the DMG
# This app clones the repo and sets up everything

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "📦 Creating Install AI OS.app..."

APP_NAME="Install AI OS"
APP_BUNDLE="${APP_NAME}.app"

# Remove existing
rm -rf "$APP_BUNDLE"

# Create structure
mkdir -p "$APP_BUNDLE/Contents/MacOS"
mkdir -p "$APP_BUNDLE/Contents/Resources"

# Create Info.plist
cat > "$APP_BUNDLE/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDisplayName</key>
    <string>Install AI OS</string>
    <key>CFBundleExecutable</key>
    <string>install</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.aios.installer</string>
    <key>CFBundleName</key>
    <string>Install AI OS</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
EOF

# Create the main launcher that opens Terminal with the install script
cat > "$APP_BUNDLE/Contents/MacOS/install" << 'LAUNCHER'
#!/bin/bash
# AI OS Installer Launcher
# Opens Terminal and runs the installation

INSTALL_DIR="$HOME/AI_OS"
REPO_URL="https://github.com/allee-ai/AI_OS.git"

# Create a temporary install script
TEMP_SCRIPT=$(mktemp /tmp/aios_install.XXXXXX.sh)
chmod +x "$TEMP_SCRIPT"

cat > "$TEMP_SCRIPT" << 'INSTALLSCRIPT'
#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

INSTALL_DIR="$HOME/AI_OS"
REPO_URL="https://github.com/allee-ai/AI_OS.git"

clear
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              🧠 AI OS Installer                           ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check for existing installation
if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}⚠️  AI OS already exists at $INSTALL_DIR${NC}"
    echo ""
    read -p "Update existing installation? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}→ Updating...${NC}"
        cd "$INSTALL_DIR"
        git pull origin main 2>/dev/null || echo -e "${YELLOW}  (not a git repo, skipping update)${NC}"
    else
        echo -e "${YELLOW}→ Opening existing installation...${NC}"
        sleep 1
        open "$INSTALL_DIR/run.command"
        exit 0
    fi
else
    echo -e "${BLUE}📍 Installing to: $INSTALL_DIR${NC}"
    echo ""
    
    # Check for git
    if ! command -v git &> /dev/null; then
        echo -e "${RED}❌ Git not found.${NC}"
        echo -e "${YELLOW}   Installing Xcode Command Line Tools...${NC}"
        xcode-select --install 2>/dev/null || true
        echo ""
        echo -e "${YELLOW}   After installation completes, run this installer again.${NC}"
        read -n 1 -s -r -p "Press any key to exit..."
        exit 1
    fi
    
    # Clone
    echo -e "${YELLOW}→ Downloading AI OS...${NC}"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""

# Check for Ollama
if ! command -v ollama &> /dev/null; then
    echo -e "${YELLOW}⚠️  Ollama not found (required for local AI).${NC}"
    echo ""
    
    if command -v brew &> /dev/null; then
        read -p "Install Ollama via Homebrew? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${YELLOW}→ Installing Ollama...${NC}"
            brew install ollama
        fi
    else
        echo -e "${BLUE}   Download from: https://ollama.ai${NC}"
        echo ""
        read -p "Open Ollama download page? (y/n) " -n 1 -r
        echo ""
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            open "https://ollama.ai/download"
            echo ""
            echo -e "${YELLOW}   Install Ollama, then run this installer again.${NC}"
            read -n 1 -s -r -p "Press any key to exit..."
            exit 0
        fi
    fi
fi

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found.${NC}"
    echo -e "${YELLOW}   Download from: https://python.org${NC}"
    open "https://python.org/downloads/"
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi
echo -e "${GREEN}  ✓ Python 3${NC}"

# Check for Node
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js not found.${NC}"
    echo -e "${YELLOW}   Download from: https://nodejs.org${NC}"
    open "https://nodejs.org/"
    read -n 1 -s -r -p "Press any key to exit..."
    exit 1
fi
echo -e "${GREEN}  ✓ Node.js${NC}"

if command -v ollama &> /dev/null; then
    echo -e "${GREEN}  ✓ Ollama${NC}"
fi

echo ""

# Create app bundle pointing to install location
echo -e "${YELLOW}→ Creating application...${NC}"
cd "$INSTALL_DIR/scripts"
chmod +x *.sh 2>/dev/null || true

# Build the app bundle
./create_app_bundle.sh 2>/dev/null || true

# Create a proper AIOS.app in Applications with absolute path
rm -rf "/Applications/AIOS.app" 2>/dev/null || true
mkdir -p "/Applications/AIOS.app/Contents/MacOS"
mkdir -p "/Applications/AIOS.app/Contents/Resources"

# Copy Info.plist
if [ -f "$INSTALL_DIR/scripts/AIOS.app/Contents/Info.plist" ]; then
    cp "$INSTALL_DIR/scripts/AIOS.app/Contents/Info.plist" "/Applications/AIOS.app/Contents/Info.plist"
    sed -i "" "s/>Agent</>AIOS</g" "/Applications/AIOS.app/Contents/Info.plist"
else
    cat > "/Applications/AIOS.app/Contents/Info.plist" << 'INFOPLIST'
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
    <key>CFBundleVersion</key>
    <string>1</string>
</dict>
</plist>
INFOPLIST
fi

# Copy icon if exists
if [ -f "$INSTALL_DIR/scripts/AIOS.app/Contents/Resources/AppIcon.icns" ]; then
    cp "$INSTALL_DIR/scripts/AIOS.app/Contents/Resources/AppIcon.icns" "/Applications/AIOS.app/Contents/Resources/"
fi

# Create launcher with ABSOLUTE path to install location
cat > "/Applications/AIOS.app/Contents/MacOS/AIOS" << APPLAUNCHER
#!/bin/bash
open "$INSTALL_DIR/run.command"
APPLAUNCHER
chmod +x "/Applications/AIOS.app/Contents/MacOS/AIOS"

echo -e "${GREEN}  ✓ Created /Applications/AIOS.app${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  🎉 AI OS installed successfully!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Code location:${NC}  $INSTALL_DIR"
echo -e "  ${CYAN}Application:${NC}    /Applications/AIOS.app"
echo ""
echo -e "  ${BLUE}Tip:${NC} Drag AIOS from Applications to your Dock"
echo ""

read -p "🚀 Start AI OS now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}→ Starting AI OS (first run downloads AI models ~4GB)...${NC}"
    echo ""
    cd "$INSTALL_DIR"
    chmod +x run.command
    ./run.command
fi
INSTALLSCRIPT

# Open Terminal and run the install script
open -a Terminal "$TEMP_SCRIPT"
LAUNCHER

chmod +x "$APP_BUNDLE/Contents/MacOS/install"

# Copy icon if available
if [ -f "AIOSIcon.icns" ]; then
    cp "AIOSIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
elif [ -f "AIOS.app/Contents/Resources/AppIcon.icns" ]; then
    cp "AIOS.app/Contents/Resources/AppIcon.icns" "$APP_BUNDLE/Contents/Resources/AppIcon.icns"
fi

echo "✅ Created: $APP_BUNDLE"
echo ""
