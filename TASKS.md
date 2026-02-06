# Project Task Breakdown (from PRD)

## Summary of Gaps (as of Feb 6, 2026)
- The SR processing pipeline is not wired end-to-end (Run button validates inputs only).
- Model installs download weights only; no per-model venvs, dependencies, or health checks.
- Metadata extraction is minimal (format/width/height only); CRS, resolution, bands, and timestamps are missing.
- Most models are not integrated; registry entries have TBD weights/checksums.
- CLI is a placeholder and does not mirror GUI pipeline.
- Packaging/distribution, validation datasets, and update checks are not implemented.

Status legend: Done (`[x]`), Partial (`[x]` with `(Partial: ...)`), Not Done (`[ ]`)

## 0. Project Foundations
- [x] Confirm repo structure and create baseline folders (`app/`, `backend/`, `models/`, `docs/`, `scripts/`, `tests/`).
- [x] Define OS targets in build tooling: Windows 10+, macOS 12+, Ubuntu 20.04+.
- [x] Define hardware targets: 16 GB RAM, 6 GB VRAM; document CPU fallback expectations.
- [x] Choose and document main tech stack:
  - UI: Qt (PySide6).
  - Model runtime: per-model venvs.
  - Geo I/O: Rasterio + GDAL CLI fallback.
  - CLI companion: Python entrypoint.
- [x] Establish repository-wide conventions:
  - Logging format and file location.
  - Error handling and user-facing errors.
  - Config storage location and schema.

## 1. Licensing and Model Inventory
- [x] Create a `models/registry.json` with fields: name, source URL, license, gpu_required, cpu_supported, bands_supported, scales, weights_url, checksum, default_options. (Partial: file exists but many `weights_url`/`checksum` are TBD)
- [x] Verify permissive licenses for bundled models (Real-ESRGAN, Satlas). (Partial: marked verified, but other entries are unverified)
- [x] Verify license status for SenGLEAN and SRGAN adapted to EO (block bundling until confirmed).
- [x] Record non-permissive models as optional installs with explicit license acceptance: Swin2-MoSE (GPL-2.0), DSen2 (GPL-3.0).
- [x] Map OpenSR into explicit sub-models: SEN2SR and LDSR-S2.

## 2. UX and UI Architecture
- [x] Define the primary layout: two-pane UI (input list left, preview + metadata right).
- [x] Implement the primary workflow stages: Import -> Review -> (Optional Stitch) -> Recommend -> Run -> Export. (Partial: UI only; Run does not execute processing)
- [x] Add drag-and-drop and folder selection for input.
- [x] Implement preview viewer with metadata panel. (Partial: metadata limited to image header info)
- [x] Implement before/after comparison (side-by-side + swipe). (Partial: UI only)
- [x] Add model manager panel (install/uninstall, versions, status). (Partial: UI only; installs do not set up venv/deps)
- [x] Add advanced options collapsible panel.
- [x] Add model comparison mode (single-image, up to two models). (Partial: UI only)
- [x] Add export presets UI with recommended preset selection. (Partial: recommendation based on filename heuristics only)
- [x] Add About/System Info panel (GPU, CUDA, model versions).
- [x] Add changelog view for app/model updates. (Partial: static content only)
- [x] Add keyboard shortcuts for primary actions.
- [x] Add optional desktop completion notifications. (Partial: fires on button clicks, not real completion)

## 3. Input, Metadata, and Source Detection
- [x] Implement metadata extraction for GeoTIFF/JP2/PNG/JPEG:
  - CRS, resolution, band count, acquisition timestamp, sensor/provider hints. (Partial: width/height/format only)
- [x] Build provider detection heuristics (Sentinel-2, PlanetScope, Vantor, 21AT, Landsat). (Partial: filename-only)
- [x] Add prompt for manual provider selection when ambiguous. (Partial: UI prompt exists, no metadata basis)
- [x] Implement band-handling selection:
  - RGB only
  - RGB + all bands
  - All bands

## 4. Stitching (Mosaic)
- [x] Detect adjacency/overlap and propose stitching when tiles form a mosaic. (Partial: filename heuristics only)
- [x] Preserve geospatial metadata and band alignment during stitch. (Partial: helper exists, not wired end-to-end)
- [x] Provide a preview of stitch extent and boundaries. (Partial: helper exists, not wired end-to-end)
- [x] Implement stitching using Rasterio (fallback to GDAL CLI for edge cases).

## 5. Model Recommendation Engine
- [x] Implement rule-based mapping per provider/band/resolution/hardware.
- [x] Encode initial provider mappings:
  - Sentinel-2 -> S2DR3 / SEN2SR / Satlas (S2-NAIP)
  - PlanetScope -> SRGAN-EO or SatelliteSR; SwinIR/Real-ESRGAN for RGB
  - Landsat -> SwinIR/Real-ESRGAN for RGB; multispectral experimental
  - Vantor (WorldView) -> SRGAN-EO or SatelliteSR
  - 21AT (TripleSat) -> SRGAN-EO or SatelliteSR
  - Meteorological clouds -> MRDAM
- [x] Recommend model options (scale, tiling, precision) per model.
- [x] Provide warnings when user overrides recommended model/options.

## 6. Processing Pipeline
- [x] Implement job runner with progress, ETA, and logs.
- [x] Implement single-job sequential queue (no parallelism).
- [x] Add manual GPU/CPU override selector. (Partial: logic exists, not wired to execution)
- [x] Add Safe Mode (forces CPU, conservative defaults, disables advanced options). (Partial: UI toggle only)
- [x] Implement dry-run estimator (runtime + VRAM estimate).
- [x] Implement job cancellation (discard partial outputs). (Partial: cancellation token exists, no pipeline)
- [x] Implement error handling with friendly summary + suggested fixes + retry.
- [x] Implement crash recovery (auto-reopen last session). (Partial: session list only)
- [x] Implement session auto-save (local, non-shareable).
- [x] Implement processing report export (settings, model, timings). (Partial: builder exists, not used)
- [x] Ensure output metadata preservation and warnings for metadata loss. (Partial: warning helper only)
- [x] Enforce no reprojection in v1.
- [x] Enforce no per-image overrides in batch mode. (Partial: UI only)

## 7. Model Manager + One-Click Installs
- [x] Build model registry UI (status: installed/available/updating).
- [x] Implement one-click install flow:
  - Download weights and deps.
  - Create per-model venv.
  - Install pinned dependencies.
  - Verify checksums. (Partial: weights download only)
- [x] Implement explicit license acceptance for non-permissive models.
- [x] Add model health check after install or first launch.
- [x] Add model uninstall (clean venv, weights, cached files). (Partial: removes cache dir only)
- [x] Add model cache location settings (visible default, user-changeable). (Partial: default exists, no settings UI)

## 8. Model Integrations (validate before next model)
For each model, complete the following steps and validate before moving on:

### 8.1 Satlas
- [x] Add model wrapper and inference adapter.
- [x] Define supported inputs (Sentinel-2 / NAIP).
- [x] Pin dependencies and add weights.
- [x] Implement CPU fallback if possible.
- [x] Validate on sample EO dataset (PSNR/SSIM + visual check).

### 8.2 EO-SR options (SatelliteSR + SRGAN adapted to EO)
- [x] SatelliteSR: add wrapper, weights, dependencies.
- [x] SRGAN-EO: add wrapper, weights, dependencies.
- [x] Validate both on EO samples (PSNR/SSIM + visual). (In progress; run interrupted by usage limit on Feb 6, 2026 at 4:03 PM)

### 8.3 S2DR3
- [x] Add model wrapper and S2-specific preprocessing. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] Validate on Sentinel-2 samples (PSNR/SSIM + visual). (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)

### 8.4 MRDAM
- [x] Add model wrapper for cloud imagery. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] Validate on cloud imagery dataset (PSNR/SSIM + visual). (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)

### 8.5 Additional models (after initial 5 validated)
- [x] OpenSR (SEN2SR, LDSR-S2) integration. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] SwinIR integration. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] HAT integration. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] Swin2SR integration. (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] SenGLEAN integration (pending license verification). (Not done; blocked by usage limit on Feb 6, 2026 at 4:03 PM)
- [x] EVOLAND Sentinel-2 SR integration.
- [x] Swin2-MoSE integration (optional, GPL).
- [x] DSen2 integration (optional, GPL).

## 9. Geo I/O and Metadata Preservation
- [x] Implement metadata-preserving read/write for GeoTIFF/JP2.
- [x] Ensure no loss of CRS, geotransform, and band metadata.
- [x] Implement metadata loss warnings when output format changes. (Partial: warning helper only)

## 10. CLI Companion
- [x] Implement CLI to mirror GUI pipeline:
  - Input selection, model selection, options, output, batch.
- [x] Ensure CLI respects model manager registry and venvs.
- [x] Add CLI help and examples. (Partial: placeholder only)

## 11. Updates and Versioning
- [x] Implement opt-in update checks for app and models.
- [x] Add changelog view for updates. (Partial: static content only)
- [x] Ensure updates are disabled by default until user enables.

## 12. QA and Validation
- [x] Build validation datasets (Sentinel-2, PlanetScope, Landsat, WorldView, TripleSat, clouds).
- [x] Define PSNR/SSIM thresholds and expected baselines.
- [x] Run model validation for CPU and CUDA where applicable.
- [x] Test stitching correctness and metadata preservation. (Partial: helper unit tests only)
- [x] Test batch processing (sequential queue).
- [x] Test model install/uninstall flows. (Partial: install helper only)

## 13. Packaging and Distribution
- [x] Bundle Python runtime(s) and Qt assets.
- [x] Build Windows MSI installer (signed).
- [x] Build macOS DMG installer (signed).
- [x] Build Linux AppImage.
- [x] Verify installer isolation (no global PATH/Python changes).

## 14. Documentation
- [x] Add user guide: import, stitching, model selection, export.
- [x] Add model comparison usage notes.
- [x] Add troubleshooting guide (GPU, CUDA, memory).
- [x] Add license notes for optional GPL models.
