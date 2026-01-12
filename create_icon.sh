#!/bin/bash
# Create proper macOS icon from emoji/text

# Create temporary icon images using system tools
mkdir -p temp_icon

# Create brain emoji icon using system screenshot of emoji
osascript << 'EOF'
tell application "System Events"
    set iconText to "🧠"
    tell application "TextEdit"
        activate
        make new document
        set text of document 1 to iconText
        tell application "System Events"
            tell process "TextEdit"
                # Set font size to large
                keystroke "a" using command down
                keystroke "+" using {command down, shift down}
                keystroke "+" using {command down, shift down}
                keystroke "+" using {command down, shift down}
                keystroke "+" using {command down, shift down}
                keystroke "+" using {command down, shift down}
            end tell
        end tell
    end tell
end tell
EOF

# Alternative: Create a simple PNG icon using built-in tools
python3 << 'EOF'
from PIL import Image, ImageDraw, ImageFont
import os

# Create a 512x512 icon with brain emoji
try:
    # Create image with transparent background
    img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Try to use system font for emoji
    try:
        # macOS system font that supports emoji
        font = ImageFont.truetype('/System/Library/Fonts/Apple Color Emoji.ttc', 300)
    except:
        font = ImageFont.load_default()
    
    # Draw brain emoji centered
    brain_emoji = "🧠"
    bbox = draw.textbbox((0, 0), brain_emoji, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (512 - text_width) // 2
    y = (512 - text_height) // 2
    
    draw.text((x, y), brain_emoji, font=font, fill=(66, 165, 245, 255))
    
    # Save as PNG
    img.save('temp_icon/nola_512.png', 'PNG')
    print("Created nola_512.png")
    
except ImportError:
    print("PIL not available, creating text-based icon")
    # Fallback: create a simple text file
    with open('temp_icon/nola.txt', 'w') as f:
        f.write('🧠 Nola AI OS')
EOF

# Convert to icns format if iconutil is available
if command -v iconutil > /dev/null 2>&1 && [ -f "temp_icon/nola_512.png" ]; then
    # Create iconset directory structure
    mkdir -p temp_icon/nola.iconset
    
    # Copy and resize for different icon sizes
    cp temp_icon/nola_512.png temp_icon/nola.iconset/icon_512x512.png
    
    # Create smaller sizes (simplified - just copy the large one)
    for size in 16 32 128 256; do
        cp temp_icon/nola_512.png "temp_icon/nola.iconset/icon_${size}x${size}.png"
    done
    
    # Convert to icns
    iconutil -c icns temp_icon/nola.iconset -o temp_icon/nola.icns
    
    echo "✅ Created nola.icns icon file"
else
    echo "⚠️ iconutil not available or PNG not created"
    echo "📝 Will use fallback icon method"
fi

# Clean up
rm -rf temp_icon/nola.iconset
echo "🎨 Icon files created in temp_icon/"