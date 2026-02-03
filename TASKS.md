# Project Task Breakdown (from PRD)

## 0. Project Foundations
- [x] Confirm repo structure and create baseline folders (`app/`, `backend/`, `models/`, `docs/`, `scripts/`, `tests/`).
- [x] Define OS targets in build tooling: Windows 10+, macOS 12+, Ubuntu 20.04+.
- [ ] Define hardware targets: 16 GB RAM, 6 GB VRAM; document CPU fallback expectations.
- [ ] Choose and document main tech stack:
  - UI: Qt (PySide6).
  - Model runtime: per-model venvs.
  - Geo I/O: Rasterio + GDAL CLI fallback.
  - CLI companion: Python entrypoint.
- [ ] Establish repository-wide conventions:
  - Logging format and file location.
  - Error handling and user-facing errors.
  - Config storage location and schema.

## 1. Licensing and Model Inventory
- [ ] Create a `models/registry.json` with fields: name, source URL, license, gpu_required, cpu_supported, bands_supported, scales, weights_url, checksum, default_options.
- [ ] Verify permissive licenses for bundled models (Real-ESRGAN, Satlas).
- [ ] Verify license status for SenGLEAN and SRGAN adapted to EO (block bundling until confirmed).
- [ ] Record non-permissive models as optional installs with explicit license acceptance: Swin2-MoSE (GPL-2.0), DSen2 (GPL-3.0).
- [ ] Map OpenSR into explicit sub-models: SEN2SR and LDSR-S2.

## 2. UX and UI Architecture
- [ ] Define the primary layout: two-pane UI (input list left, preview + metadata right).
- [ ] Implement the primary workflow stages: Import -> Review -> (Optional Stitch) -> Recommend -> Run -> Export.
- [ ] Add drag-and-drop and folder selection for input.
- [ ] Implement preview viewer with metadata panel.
- [ ] Implement before/after comparison (side-by-side + swipe).
- [ ] Add model manager panel (install/uninstall, versions, status).
- [ ] Add advanced options collapsible panel.
- [ ] Add model comparison mode (single-image, up to two models).
- [ ] Add export presets UI with recommended preset selection.
- [ ] Add About/System Info panel (GPU, CUDA, model versions).
- [ ] Add changelog view for app/model updates.
- [ ] Add keyboard shortcuts for primary actions.
- [ ] Add optional desktop completion notifications.

## 3. Input, Metadata, and Source Detection
- [ ] Implement metadata extraction for GeoTIFF/JP2/PNG/JPEG:
  - CRS, resolution, band count, acquisition timestamp, sensor/provider hints.
- [ ] Build provider detection heuristics (Sentinel-2, PlanetScope, Vantor, 21AT, Landsat).
- [ ] Add prompt for manual provider selection when ambiguous.
- [ ] Implement band-handling selection:
  - RGB only
  - RGB + all bands
  - All bands

## 4. Stitching (Mosaic)
- [ ] Detect adjacency/overlap and propose stitching when tiles form a mosaic.
- [ ] Preserve geospatial metadata and band alignment during stitch.
- [ ] Provide a preview of stitch extent and boundaries.
- [ ] Implement stitching using Rasterio (fallback to GDAL CLI for edge cases).

## 5. Model Recommendation Engine
- [ ] Implement rule-based mapping per provider/band/resolution/hardware.
- [ ] Encode initial provider mappings:
  - Sentinel-2 -> S2DR3 / SEN2SR / Satlas (S2-NAIP)
  - PlanetScope -> SRGAN-EO or SatelliteSR; SwinIR/Real-ESRGAN for RGB
  - Landsat -> SwinIR/Real-ESRGAN for RGB; multispectral experimental
  - Vantor (WorldView) -> SRGAN-EO or SatelliteSR
  - 21AT (TripleSat) -> SRGAN-EO or SatelliteSR
  - Meteorological clouds -> MRDAM
- [ ] Recommend model options (scale, tiling, precision) per model.
- [ ] Provide warnings when user overrides recommended model/options.

## 6. Processing Pipeline
- [ ] Implement job runner with progress, ETA, and logs.
- [ ] Implement single-job sequential queue (no parallelism).
- [ ] Add manual GPU/CPU override selector.
- [ ] Add Safe Mode (forces CPU, conservative defaults, disables advanced options).
- [ ] Implement dry-run estimator (runtime + VRAM estimate).
- [ ] Implement job cancellation (discard partial outputs).
- [ ] Implement error handling with friendly summary + suggested fixes + retry.
- [ ] Implement crash recovery (auto-reopen last session).
- [ ] Implement session auto-save (local, non-shareable).
- [ ] Implement processing report export (settings, model, timings).
- [ ] Ensure output metadata preservation and warnings for metadata loss.
- [ ] Enforce no reprojection in v1.
- [ ] Enforce no per-image overrides in batch mode.

## 7. Model Manager + One-Click Installs
- [ ] Build model registry UI (status: installed/available/updating).
- [ ] Implement one-click install flow:
  - Download weights and deps.
  - Create per-model venv.
  - Install pinned dependencies.
  - Verify checksums.
- [ ] Implement explicit license acceptance for non-permissive models.
- [ ] Add model health check after install or first launch.
- [ ] Add model uninstall (clean venv, weights, cached files).
- [ ] Add model cache location settings (visible default, user-changeable).

## 8. Model Integrations (validate before next model)
For each model, complete the following steps and validate before moving on:

### 8.1 Satlas
- [ ] Add model wrapper and inference adapter.
- [ ] Define supported inputs (Sentinel-2 / NAIP).
- [ ] Pin dependencies and add weights.
- [ ] Implement CPU fallback if possible.
- [ ] Validate on sample EO dataset (PSNR/SSIM + visual check).

### 8.2 EO-SR options (SatelliteSR + SRGAN adapted to EO)
- [ ] SatelliteSR: add wrapper, weights, dependencies.
- [ ] SRGAN-EO: add wrapper, weights, dependencies.
- [ ] Validate both on EO samples (PSNR/SSIM + visual).

### 8.3 S2DR3
- [ ] Add model wrapper and S2-specific preprocessing.
- [ ] Validate on Sentinel-2 samples (PSNR/SSIM + visual).

### 8.4 MRDAM
- [ ] Add model wrapper for cloud imagery.
- [ ] Validate on cloud imagery dataset (PSNR/SSIM + visual).

### 8.5 Additional models (after initial 5 validated)
- [ ] OpenSR (SEN2SR, LDSR-S2) integration.
- [ ] SwinIR integration.
- [ ] HAT integration.
- [ ] Swin2SR integration.
- [ ] SenGLEAN integration (pending license verification).
- [ ] EVOLAND Sentinel-2 SR integration.
- [ ] Swin2-MoSE integration (optional, GPL).
- [ ] DSen2 integration (optional, GPL).

## 9. Geo I/O and Metadata Preservation
- [ ] Implement metadata-preserving read/write for GeoTIFF/JP2.
- [ ] Ensure no loss of CRS, geotransform, and band metadata.
- [ ] Implement metadata loss warnings when output format changes.

## 10. CLI Companion
- [ ] Implement CLI to mirror GUI pipeline:
  - Input selection, model selection, options, output, batch.
- [ ] Ensure CLI respects model manager registry and venvs.
- [ ] Add CLI help and examples.

## 11. Updates and Versioning
- [ ] Implement opt-in update checks for app and models.
- [ ] Add changelog view for updates.
- [ ] Ensure updates are disabled by default until user enables.

## 12. QA and Validation
- [ ] Build validation datasets (Sentinel-2, PlanetScope, Landsat, WorldView, TripleSat, clouds).
- [ ] Define PSNR/SSIM thresholds and expected baselines.
- [ ] Run model validation for CPU and CUDA where applicable.
- [ ] Test stitching correctness and metadata preservation.
- [ ] Test batch processing (sequential queue).
- [ ] Test model install/uninstall flows.

## 13. Packaging and Distribution
- [ ] Bundle Python runtime(s) and Qt assets.
- [ ] Build Windows MSI installer (signed).
- [ ] Build macOS DMG installer (signed).
- [ ] Build Linux AppImage.
- [ ] Verify installer isolation (no global PATH/Python changes).

## 14. Documentation
- [ ] Add user guide: import, stitching, model selection, export.
- [ ] Add model comparison usage notes.
- [ ] Add troubleshooting guide (GPU, CUDA, memory).
- [ ] Add license notes for optional GPL models.
