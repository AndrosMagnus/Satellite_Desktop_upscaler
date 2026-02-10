# Satellite Desktop Upscaler

Cross-platform desktop app (Qt/PySide6) for satellite image super-resolution with:
- Guided workflow: `Import -> Review -> (Optional Stitch) -> Recommend -> Run -> Export`
- Metadata-aware processing for geospatial imagery
- Model manager with isolated per-model runtime environments
- CLI companion for dry-runs and batch automation

## Download and Run (Windows)
1. Open the latest GitHub Release.
2. Download `SatelliteUpscale-windows.zip`.
3. Extract it.
4. Run `SatelliteUpscale.exe` from the extracted `SatelliteUpscale` folder.

Notes:
- No global Python install is required for end users.
- SmartScreen reputation warnings can still appear without paid Authenticode certs.
- This project ships free Sigstore signatures and GitHub attestations for integrity verification.

## Hardware Targets
- Minimum RAM: 16 GB
- Minimum VRAM: 6 GB (NVIDIA CUDA recommended)
- CPU fallback: supported when CUDA is unavailable or user forces CPU

## Development Setup
1. Create and activate a virtual environment:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install app + dev dependencies:
```powershell
python -m pip install -U pip
python -m pip install -e .[dev]
```

3. Run tests:
```powershell
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -q
```

4. Run GUI or CLI:
```powershell
python -m app.ui
python -m backend.main --list-models
python -m backend.main --input C:\data\scene.tif --output-dir C:\data\out --dry-run
```

## Packaging
- Windows: `powershell -File scripts/package_windows.ps1`
- macOS: `bash scripts/package_macos.sh`
- Linux: `bash scripts/package_linux.sh`

See `docs/packaging.md` for release signing/attestation and verification steps.

## Documentation
- `docs/user_guide.md`
- `docs/model_comparison_notes.md`
- `docs/troubleshooting.md`
- `docs/gpl_optional_models.md`
- `docs/packaging.md`
- `docs/validation_baselines.md`
