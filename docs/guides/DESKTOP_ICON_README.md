# 🧠 Agent AI OS - Desktop Icon Setup

## Quick Setup

### 1. Create Desktop Icon (macOS)
```bash
./create_app_bundle.sh
```
Then drag `Nola.app` to your:
- 🖥️ **Desktop** for easy access
- 📁 **Applications folder** for system integration  
- 🚀 **Dock** for quick launching

### 2. Create Cross-Platform Shortcuts
```bash
./create_desktop_shortcut.sh
```

## What You Get

🌀 **Modified start.sh** - Opens startup page at `http://localhost:3000/startup`  
🌀 **macOS App Bundle** - Professional app icon that launches Terminal + Agent  
🌀 **Startup Options Page** - Clean UI to select:
- 👤 **Personal** vs 🎭 **Demo** data mode
- 💻 **Local** vs 🐳 **Docker** build method  
- ⚙️ **Developer mode** toggle

## Usage

1. **Double-click** `Nola.app` (or desktop shortcut)
2. **Terminal opens** and starts services
3. **Browser opens** to startup page
4. **Select your options** and click "Start Nola"
5. **Redirects to Dashboard** in your chosen mode

## File Changes Made

- `start.sh` - Opens `/startup` instead of root path
- `run.command` - Unchanged (still works)  
- `Nola.app/` - New macOS app bundle created
- Startup page files created in frontend

## Customization

**Icon**: Replace `Nola.app/Contents/Resources/AppIcon.*` with custom icon  
**Name**: Edit `CFBundleDisplayName` in `Nola.app/Contents/Info.plist`  
**Startup URL**: Modify browser open command in `start.sh`