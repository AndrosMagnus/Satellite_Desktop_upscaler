# Main Tech Stack

This document captures the primary technical choices for the desktop satellite SR app and the reasoning
behind them. These are the default choices for v1 unless a specific component proves incompatible.

## Core Language and Runtime
- Python 3.11
  - Consistent with the current repo and ML ecosystem stability.

## Desktop UI
- PySide6 (Qt)
  - Cross-platform desktop UI toolkit that aligns with the PRD and supports native installers.

## ML and Model Execution
- PyTorch (CUDA when available, CPU fallback)
  - Primary runtime for SR model inference and model management.
- Model isolation via per-model virtual environments
  - Avoids dependency conflicts between research models.

## Geospatial and Image I/O
- Rasterio for GeoTIFF/JP2 I/O and metadata handling
- GDAL CLI for edge cases and large-file workflows
- NumPy for image array manipulation and tiling

## Local Services and Orchestration
- In-process Python workers (asyncio + concurrent.futures)
  - Keeps the GUI responsive while running compute-heavy SR jobs.
- Optional local API: FastAPI (if we need a process boundary later)
  - Deferred until multi-process isolation is needed.

## Packaging and Distribution
- PyInstaller-based app bundling
  - Provides a single-app bundle for Windows/macOS/Linux.
- Platform-specific installers
  - Windows MSI, macOS DMG, Linux AppImage built from the bundle.

## Persistence
- Local filesystem for project data and outputs
- SQLite (via stdlib sqlite3) for lightweight run history and settings

## Non-Goals for v1 Stack
- Cloud inference or managed backend services
- Electron-based UI
- Browser-hosted workflows
