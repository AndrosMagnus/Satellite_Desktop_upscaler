#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${PYTHON_EXE:-python}"
OUT_DIR="${OUT_DIR:-dist}"
SPEC_PATH="${SPEC_PATH:-packaging/pyinstaller/satellite_upscale.spec}"
APP_NAME="SatelliteUpscale"

echo "Building macOS app bundle..."
"$PYTHON_EXE" -m PyInstaller --noconfirm --distpath "$OUT_DIR" "$SPEC_PATH"

if ! command -v create-dmg >/dev/null 2>&1; then
  echo "create-dmg not found. Skipping DMG build."
  exit 0
fi

echo "Building DMG..."
create-dmg \
  --overwrite \
  "$OUT_DIR/${APP_NAME}.dmg" \
  "$OUT_DIR/${APP_NAME}.app"

echo "DMG build complete."
