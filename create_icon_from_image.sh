#!/bin/bash
# Convert the purple spiral image to macOS icon format

echo "🎨 Converting image to macOS icon format..."

# Check if the image exists (assuming you've saved it as nola-spiral.png)
if [ ! -f "nola-spiral.png" ]; then
    echo "⚠️ Please save the purple spiral image as 'nola-spiral.png' in this directory"
    exit 1
fi

# Create iconset directory
rm -rf nola-spiral.iconset
mkdir nola-spiral.iconset

# Use sips (built-in macOS tool) to create different icon sizes
echo "📐 Creating icon sizes..."

# Standard icon sizes for macOS
sips -z 16 16 nola-spiral.png --out nola-spiral.iconset/icon_16x16.png
sips -z 32 32 nola-spiral.png --out nola-spiral.iconset/icon_16x16@2x.png
sips -z 32 32 nola-spiral.png --out nola-spiral.iconset/icon_32x32.png
sips -z 64 64 nola-spiral.png --out nola-spiral.iconset/icon_32x32@2x.png
sips -z 128 128 nola-spiral.png --out nola-spiral.iconset/icon_128x128.png
sips -z 256 256 nola-spiral.png --out nola-spiral.iconset/icon_128x128@2x.png
sips -z 256 256 nola-spiral.png --out nola-spiral.iconset/icon_256x256.png
sips -z 512 512 nola-spiral.png --out nola-spiral.iconset/icon_256x256@2x.png
sips -z 512 512 nola-spiral.png --out nola-spiral.iconset/icon_512x512.png
sips -z 1024 1024 nola-spiral.png --out nola-spiral.iconset/icon_512x512@2x.png

# Convert to .icns format
echo "🔄 Converting to .icns format..."
iconutil -c icns nola-spiral.iconset -o NolaIcon.icns

if [ -f "NolaIcon.icns" ]; then
    echo "✅ Created NolaIcon.icns"
    
    # Copy to app bundle if it exists
    if [ -d "Nola.app/Contents/Resources" ]; then
        cp NolaIcon.icns Nola.app/Contents/Resources/AppIcon.icns
        echo "📱 Updated Nola.app with new icon"
    fi
    
    # Clean up
    rm -rf nola-spiral.iconset
    
    echo ""
    echo "🎯 Purple spiral icon created!"
    echo "💫 Your app now has a beautiful fractal brain icon"
else
    echo "❌ Failed to create icon file"
fi