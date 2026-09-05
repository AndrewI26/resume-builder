#!/usr/bin/env bash
# Renders build/icon/icon.svg into the icon files electron-builder ships.
#
#   apps/desktop/scripts/build-icons.sh
#
# The outputs are committed, because CI has neither rsvg-convert nor iconutil
# and an icon changes about once a year. Run this after editing the SVG.
set -euo pipefail

cd "$(dirname "$0")/.."

svg="build/icon/icon.svg"
iconset="$(mktemp -d)/icon.iconset"
mkdir -p "$iconset"

render() { rsvg-convert -w "$1" -h "$1" "$svg" -o "$2"; }

# The sizes iconutil expects, each at 1x and 2x.
for size in 16 32 128 256 512; do
	render "$size" "$iconset/icon_${size}x${size}.png"
	render "$((size * 2))" "$iconset/icon_${size}x${size}@2x.png"
done

iconutil --convert icns "$iconset" --output build/icon.icns

# Windows wants one .ico carrying every size, and a 256x256 PNG is what
# electron-builder falls back to for Linux.
tmp="$(mktemp -d)"
for size in 16 24 32 48 64 128 256; do
	render "$size" "$tmp/$size.png"
done
magick "$tmp"/16.png "$tmp"/24.png "$tmp"/32.png "$tmp"/48.png \
	"$tmp"/64.png "$tmp"/128.png "$tmp"/256.png build/icon.ico

render 512 build/icon.png

echo "Wrote build/icon.icns, build/icon.ico and build/icon.png"
