#!/bin/bash

# Image Generation Script for CloudWaste
# This script generates all required favicon and OG images from SVG placeholders
# Requires: ImageMagick (brew install imagemagick)

set -e

echo "🎨 CloudWaste Image Generation Script"
echo "======================================="
echo ""

# Check if ImageMagick is installed
if ! command -v convert &> /dev/null; then
    echo "❌ Error: ImageMagick is not installed"
    echo ""
    echo "Install it with:"
    echo "  macOS:   brew install imagemagick"
    echo "  Ubuntu:  sudo apt-get install imagemagick"
    echo "  Windows: Download from https://imagemagick.org/script/download.php"
    echo ""
    exit 1
fi

echo "✅ ImageMagick detected"
echo ""

# Navigate to public directory
cd "$(dirname "$0")"

# Generate favicons
echo "🖼️  Generating favicons..."
convert favicon-placeholder.svg -resize 32x32 -background none -flatten favicon.ico
echo "  ✓ favicon.ico (32x32)"

convert favicon-placeholder.svg -resize 180x180 -background none -flatten apple-touch-icon.png
echo "  ✓ apple-touch-icon.png (180x180)"

convert favicon-placeholder.svg -resize 192x192 -background none -flatten icon-192.png
echo "  ✓ icon-192.png (192x192)"

convert favicon-placeholder.svg -resize 512x512 -background none -flatten icon-512.png
echo "  ✓ icon-512.png (512x512)"

# Generate OG image
echo ""
echo "🖼️  Generating Open Graph image..."
convert og-image-placeholder.svg -resize 1200x630 og-image.png
echo "  ✓ og-image.png (1200x630)"

echo ""
echo "✅ All images generated successfully!"
echo ""
echo "📝 Next steps:"
echo "  1. Review the generated images"
echo "  2. Replace placeholder SVGs with your actual CloudWaste logo"
echo "  3. Re-run this script to regenerate with the new logo"
echo "  4. Commit the generated images to git"
echo ""
