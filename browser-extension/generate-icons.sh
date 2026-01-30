#!/bin/bash
# Generate PNG icons from SVG for the browser extension
# Requires ImageMagick or librsvg

cd "$(dirname "$0")"

if command -v rsvg-convert &> /dev/null; then
    rsvg-convert -w 16 -h 16 icons/icon.svg > icons/icon16.png
    rsvg-convert -w 48 -h 48 icons/icon.svg > icons/icon48.png
    rsvg-convert -w 128 -h 128 icons/icon.svg > icons/icon128.png
    echo "Icons generated with rsvg-convert"
elif command -v convert &> /dev/null; then
    convert -background none -resize 16x16 icons/icon.svg icons/icon16.png
    convert -background none -resize 48x48 icons/icon.svg icons/icon48.png
    convert -background none -resize 128x128 icons/icon.svg icons/icon128.png
    echo "Icons generated with ImageMagick"
else
    echo "Please install ImageMagick or librsvg to generate PNG icons"
    echo "  macOS: brew install librsvg"
    echo "  Ubuntu: apt install librsvg2-bin"
    exit 1
fi
