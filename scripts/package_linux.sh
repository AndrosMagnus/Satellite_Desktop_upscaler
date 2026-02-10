#!/usr/bin/env bash
set -euo pipefail

PYTHON_EXE="${PYTHON_EXE:-python}"
OUT_DIR="${OUT_DIR:-dist}"
SPEC_PATH="${SPEC_PATH:-packaging/pyinstaller/satellite_upscale.spec}"
APP_NAME="SatelliteUpscale"

echo "Building Linux app bundle..."
"$PYTHON_EXE" -m PyInstaller --noconfirm --distpath "$OUT_DIR" "$SPEC_PATH"

if ! command -v linuxdeploy >/dev/null 2>&1; then
  echo "linuxdeploy not found. Skipping AppImage build."
  exit 0
fi

echo "Building AppImage..."
linuxdeploy \
  --appdir "$OUT_DIR/${APP_NAME}.AppDir" \
  --executable "$OUT_DIR/${APP_NAME}/${APP_NAME}" \
  --output appimage

echo "AppImage build complete."
