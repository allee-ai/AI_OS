#!/bin/bash
# Instructions for using the purple spiral image as Nola icon

echo "🎨 Purple Spiral Icon Setup"
echo ""
echo "Steps to use the beautiful purple spiral as your Nola icon:"
echo ""
echo "1. 📥 Save the purple spiral image as 'nola-spiral.png' in this directory"
echo "   - Right-click the image and 'Save As...'"
echo "   - Or drag/drop the image file here"
echo "   - Make sure it's named exactly 'nola-spiral.png'"
echo ""
echo "2. 🔄 Convert to icon format:"
echo "   ./create_icon_from_image.sh"
echo ""
echo "3. 🚀 Recreate app bundle with new icon:"
echo "   ./create_app_bundle.sh"
echo ""
echo "4. ✨ Result:"
echo "   - Beautiful purple spiral icon on your Nola.app"
echo "   - Perfect brain/neural network theme"
echo "   - Professional look in Dock/Applications"
echo ""
echo "💡 The spiral pattern represents:"
echo "   - Neural networks and AI thinking"
echo "   - Infinite possibilities and growth"
echo "   - The complexity of consciousness"
echo ""

# Check if image already exists
if [ -f "nola-spiral.png" ]; then
    echo "✅ Found nola-spiral.png - ready to convert!"
    echo "   Run: ./create_icon_from_image.sh"
else
    echo "⏳ Waiting for nola-spiral.png to be saved..."
fi