# Project Task Breakdown (from PRD)

## Current Reality Check (as of Feb 10, 2026)
- The UI run path now executes a local processing pipeline with recommendation-driven model/runtime planning, optional stitch-then-run execution, comparison-mode model execution, and output writing; model wrappers still rely on fallback behavior when runtimes are unavailable.
- The model install backend now supports per-model venv creation, pinned dependency install, checksum validation, and health checks.
- Metadata extraction now surfaces provider/sensor/band/CRS/pixel-size plus acquisition-time and scene-ID fields in UI via tag/filename heuristics, but deeper provider-specific scene metadata is still incomplete.
- Provider detection and mosaic detection are heuristic and filename-driven.
- The backend CLI now supports input/output/model validation/dry-run/report flows plus recommendation-driven model/runtime planning, but full parity with every GUI interaction is still incomplete.
- Packaging/distribution now includes cross-platform script templates plus CI-based free signing/provenance (Sigstore + GitHub attestations), while native platform trust signing workflows remain incomplete.
- Validation scripts now include baseline threshold definitions and fail-on-threshold mode for local sample manifests, but full CPU/CUDA validation coverage is still incomplete.
- Changelog UI includes opt-in update checks and manual status flow; production update feed/version wiring is still incomplete.

Status legend: Done (`[x]`), Partial (`[~]`), Not Done (`[ ]`)

## Locked Product Decisions (Feb 7, 2026)
- [x] Use dual output for geospatial inputs: preservation-safe master + optional visual export.
- [x] Enforce strict multispectral model compatibility (no RGB-only fallback for multispectral runs).
- [x] Treat core geo + band + radiometry fields as mandatory preservation targets.
- [x] On grid mismatch, prompt user to choose auto-reproject or split-by-grid.
- [x] For auto-reproject, target the first selected input grid.
- [x] Use per-band resampling policy (continuous vs categorical/QA).
- [x] If preservation cannot be fully guaranteed, continue with output and show critical warning.
- [x] Use provider-aware RGB defaults for optional visual exports.
- [x] For split-by-grid, preview groups and require confirmation before execution.
- [x] If band semantics are ambiguous, prompt with mapping wizard.
- [x] Save band-role mappings as provider+sensor profiles for reuse.

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
- [~] Create a `models/registry.json` with fields: name, source URL, license, gpu_required, cpu_supported, bands_supported, scales, weights_url, checksum, default_options.
  - Partial: schema exists, but many entries still use `TBD`/`TODO`/dummy weights.
- [x] Verify permissive licenses for bundled models (Real-ESRGAN, Satlas).
- [~] Verify license status for SenGLEAN and SRGAN adapted to EO (block bundling until confirmed).
  - Partial: SRGAN-EO is now verified Apache-2.0 from upstream; SenGLEAN is recorded as Etalab Open License 2.0 for open-source distribution, but upstream code/weights publication is still pending.
- [~] Record non-permissive models as optional installs with explicit license acceptance: Swin2-MoSE (GPL-2.0), DSen2 (GPL-3.0).
  - Partial: explicit acceptance is implemented in Model Manager install flow; legal review status still determines bundling policy.
- [x] Map OpenSR into explicit sub-models: SEN2SR and LDSR-S2.

## 2. UX and UI Architecture
- [x] Define the primary layout: two-pane UI (input list left, preview + metadata right).
- [~] Implement the primary workflow stages: Import -> Review -> (Optional Stitch) -> Recommend -> Run -> Export.
  - Partial: stage UI and run execution exist with recommendation-driven model execution paths and stitch-then-run wiring; model/runtime availability still determines fallback behavior.
- [x] Add drag-and-drop and folder selection for input.
- [~] Implement preview viewer with metadata panel.
  - Partial: metadata panel now shows provider/sensor/band/CRS/pixel-size/acquisition-time/scene-ID where available; richer provider-specific metadata remains limited.
- [~] Implement before/after comparison (side-by-side + swipe).
  - Partial: viewer now supports model-comparison run outputs (single image, up to two models); output quality still depends on installed model runtimes.
- [x] Add model manager panel (install/uninstall, versions, status).
- [x] Add advanced options collapsible panel.
- [~] Add model comparison mode (single-image, up to two models).
  - Partial: mode selection, compatibility checks, and dual-model execution flow now exist; wrapper/runtime availability still gates true model inference.
- [~] Add export presets UI with recommended preset selection.
  - Partial: recommendation path is provider/preset-based and heuristic.
- [x] Add run output directory picker with auto-default fallback.
- [x] Add About/System Info panel (GPU, CUDA, model versions).
- [~] Add changelog view for app/model updates.
  - Partial: includes opt-in update-check controls, manual check status, and feed-driven changelog entry updates when provided; production feed wiring remains pending.
- [x] Add keyboard shortcuts for primary actions.
- [x] Add optional desktop completion notifications.

## 3. Input, Metadata, and Source Detection
- [~] Implement metadata extraction for GeoTIFF/JP2/PNG/JPEG:
  - CRS, resolution, band count, acquisition timestamp, sensor/provider hints.
  - Partial: format/dimensions/provider/sensor/band count/CRS/pixel-size plus acquisition timestamp and scene-ID extraction now exist (tags + filename heuristics); richer provider-specific metadata is still limited.
- [~] Build provider detection heuristics (Sentinel-2, PlanetScope, Vantor, 21AT, Landsat).
  - Partial: filename-token heuristics only.
- [~] Add prompt for manual provider selection when ambiguous.
  - Partial: UI prompt exists; ambiguity is still filename-based.
- [x] Implement band-handling selection:
  - RGB only
  - RGB + all bands
  - All bands

## 4. Stitching (Mosaic)
- [~] Detect adjacency/overlap and propose stitching when tiles form a mosaic.
  - Partial: filename-based spatial hints only.
- [x] Preserve geospatial metadata and band alignment during stitch.
- [x] Provide a preview of stitch extent and boundaries.
- [x] Implement stitching using Rasterio (fallback to GDAL CLI for edge cases).

## 5. Model Recommendation Engine
- [~] Implement rule-based mapping per provider/band/resolution/hardware.
  - Partial: engine now drives run planning in UI/CLI; edge-case scene metadata and hardware detection heuristics still need refinement.
- [x] Encode initial provider mappings:
  - Sentinel-2 -> S2DR3 / SEN2SR / Satlas (S2-NAIP)
  - PlanetScope -> SRGAN-EO or SatelliteSR; SwinIR/Real-ESRGAN for RGB
  - Landsat -> SwinIR/Real-ESRGAN for RGB; multispectral experimental
  - Vantor (WorldView) -> SRGAN-EO or SatelliteSR
  - 21AT (TripleSat) -> SRGAN-EO or SatelliteSR
  - Meteorological clouds -> MRDAM
- [~] Recommend model options (scale, tiling, precision) per model.
  - Partial: recommendation options are now wired into UI/CLI run request planning; final quality still depends on installed model wrappers.
- [~] Provide warnings when user overrides recommended model/options.
  - Partial: override warnings are surfaced in run status summaries; dedicated warning UX remains limited.

## 6. Processing Pipeline
- [x] Implement job runner with progress, ETA, and logs.
- [x] Implement single-job sequential queue (no parallelism).
- [~] Add manual GPU/CPU override selector.
  - Partial: selectors/parsers now feed run request planning; inference impact still depends on model wrapper/runtime behavior.
- [~] Add Safe Mode (forces CPU, conservative defaults, disables advanced options).
  - Partial: safe mode now feeds run request planning (CPU + conservative options); wrapper/runtime behavior still governs final inference path.
- [x] Implement dry-run estimator (runtime + VRAM estimate).
- [~] Implement job cancellation (discard partial outputs).
  - Partial: cancellation now discards outputs already created in the current run; mid-file interruption remains limited to between-file boundaries.
- [x] Implement error handling with friendly summary + suggested fixes + retry.
- [~] Implement crash recovery (auto-reopen last session).
  - Partial: dirty-session restore exists; no explicit crash detection workflow.
- [x] Implement session auto-save (local, non-shareable).
- [x] Implement processing report export (settings, model, timings).
- [~] Ensure output metadata preservation and warnings for metadata loss.
  - Partial: run path now writes preservation-first master outputs with metadata-copy behavior and warnings; full model-driven export coverage remains incomplete.
- [x] Enforce no reprojection in v1.
- [~] Enforce no per-image overrides in batch mode.
  - Partial: UI-level restrictions exist.

## 7. Model Manager + One-Click Installs
- [x] Build model registry UI (status: installed/available/updating).
- [~] Implement one-click install flow:
  - Download weights and deps.
  - Create per-model venv.
  - Install pinned dependencies.
  - Verify checksums.
  - Partial: backend/UI flow is implemented end-to-end; per-model availability still depends on registry weights/checksums.
- [x] Implement explicit license acceptance for non-permissive models.
- [x] Add model health check after install or first launch.
- [x] Add model uninstall (clean venv, weights, cached files).
- [x] Add model cache location settings (visible default, user-changeable).

## 8. Model Integrations (validate before next model)
For each model, complete the following steps and validate before moving on:

### 8.1 Satlas
- [~] Add model wrapper and inference adapter.
  - Partial: Satlas wrapper + entrypoint registration added; full model-output validation remains pending.
- [x] Define supported inputs (Sentinel-2 / NAIP).
- [~] Pin dependencies and add weights.
  - Partial: dependencies/weights are present in registry, but checksums are still placeholder.
- [x] Implement CPU fallback if possible.
- [ ] Validate on sample EO dataset (PSNR/SSIM + visual check).

### 8.2 EO-SR options (SatelliteSR + SRGAN adapted to EO)
- [~] SatelliteSR: add wrapper, weights, dependencies.
- [~] SRGAN-EO: add wrapper, weights, dependencies.
- [~] Validate both on EO samples (PSNR/SSIM + visual).
  - Partial: validation scripts run on sample arrays; not full model-output validation.

### 8.3 S2DR3
- [~] Add model wrapper and S2-specific preprocessing.
- [~] Validate on Sentinel-2 samples (PSNR/SSIM + visual).
  - Partial: script-level sample validation exists; full integration remains incomplete.

### 8.4 MRDAM
- [~] Add model wrapper for cloud imagery.
- [~] Validate on cloud imagery dataset (PSNR/SSIM + visual).
  - Partial: script-level sample validation exists; full integration remains incomplete.

### 8.5 Additional models (after initial 5 validated)
- [~] OpenSR (SEN2SR, LDSR-S2) integration.
  - Partial: registry/entrypoint mapping exists via shared wrapper path.
- [~] SwinIR integration.
- [~] HAT integration.
- [~] Swin2SR integration.
- [~] SenGLEAN integration (pending public code/weights publication).
- [~] EVOLAND Sentinel-2 SR integration.
- [~] Swin2-MoSE integration (optional, GPL).
- [~] DSen2 integration (optional, GPL).
  - Partial: registry entries + entrypoint wrappers are now present; full model-weight/runtime validation remains pending.

## 9. Geo I/O and Metadata Preservation
- [~] Implement metadata-preserving read/write for GeoTIFF/JP2.
  - Partial: implemented in stitching and run master-output path, with fallback handling when driver/runtime constraints occur.
- [~] Ensure no loss of CRS, geotransform, and band metadata.
  - Partial: covered in stitch and run master-output paths; not yet guaranteed across all model wrappers/formats.
- [x] Implement metadata loss warnings when output format changes.

## 10. CLI Companion
- [~] Implement CLI to mirror GUI pipeline:
  - Input selection, model selection, options, output, batch.
  - Partial: backend CLI now supports input selection, optional stitch-then-run, recommendation-driven model/runtime planning, output options, dry-run, model runtime validation, and batch.
- [~] Ensure CLI respects model manager registry and venvs.
  - Partial: CLI validates model entrypoints and installed wrapper runtime via model cache and passes model/runtime options into execution requests; full GUI parity is pending.
- [x] Add CLI help and examples.

## 11. Updates and Versioning
- [~] Implement opt-in update checks for app and models.
  - Partial: update-check preferences + manual check flow are implemented; production feed wiring remains pending.
- [~] Add changelog view for updates.
  - Partial: changelog UI now includes update-check controls/status and can apply feed-provided entries; production update feed/version wiring remains pending.
- [x] Ensure updates are disabled by default until user enables.

## 12. QA and Validation
- [~] Build validation datasets (Sentinel-2, PlanetScope, Landsat, WorldView, TripleSat, clouds).
  - Partial: local sample datasets exist for EO/Sentinel-2/clouds only.
- [x] Define PSNR/SSIM thresholds and expected baselines.
- [~] Run model validation for CPU and CUDA where applicable.
  - Partial: CPU sample baseline validations run locally for EO/Sentinel-2/clouds; CUDA validation remains pending on CUDA hardware.
- [~] Test stitching correctness and metadata preservation.
  - Partial: unit tests plus stitched-run workflow tests exist; full geospatial end-to-end dataset validation remains pending.
- [x] Test batch processing (sequential queue).
- [~] Test model install/uninstall flows.
  - Partial: installation and health checks are tested; full UI flow coverage is limited.

## 13. Packaging and Distribution
- [~] Bundle Python runtime(s) and Qt assets.
  - Partial: PyInstaller spec and platform packaging scripts added; runtime QA is pending.
- [~] Build Windows MSI installer (signed).
  - Partial: WiX template + build script added; free CI signing/provenance is in place for release artifacts, but Authenticode MSI signing still requires a code-signing certificate.
- [~] Build macOS DMG installer (signed).
  - Partial: DMG script template added; free CI signing/provenance is in place for release artifacts, but Apple codesign/notarization is still pending.
- [~] Build Linux AppImage.
  - Partial: AppImage script template added; CI release build/sign/attest workflow is added, but AppImage tooling validation remains pending.
- [~] Verify installer isolation (no global PATH/Python changes).
  - Partial: scripts target app-local/per-user paths; full installer isolation QA is pending.

## 14. Documentation
- [x] Add user guide: import, stitching, model selection, export.
- [x] Add model comparison usage notes.
- [x] Add troubleshooting guide (GPU, CUDA, memory).
- [x] Add license notes for optional GPL models.
