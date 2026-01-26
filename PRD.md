# Product Requirements Document (PRD)

## 1. Overview
Build a cross-platform desktop application (Windows, macOS, Linux) that provides an intuitive, modern GUI for satellite image super-resolution (SR). The app supports single images or multiple tiles, can optionally stitch tiles while preserving metadata, and recommends the best SR model and options based on detected source metadata (e.g., Sentinel, Planet, or other).

## 2. Goals
- Provide a simple, explicit, and guided workflow for SR on satellite imagery.
- Automatically detect image source and metadata to recommend the best SR model and options.
- Support batch processing and optional tile stitching without metadata loss.
- Offer a robust installer that does not break or alter other system components.
- Integrate multiple SR models with isolated, reproducible dependencies.

## 3. Non-Goals
- Creating or training new SR models in v1.
- Cloud processing (v1 is local/offline processing unless explicitly enabled later).
- Photorealistic enhancement for non-satellite imagery outside EO use cases.

## 4. Target Users
- Remote sensing analysts
- GIS professionals
- Researchers working with EO datasets
- GIS students needing a simple workflow

## 5. User Stories
- As a user, I can drag and drop a folder of satellite images into the app.
- As a user, I can open a folder to add images and immediately see thumbnails and metadata.
- As a user, I can choose to stitch tiles into a single image while preserving metadata.
- As a user, I can see a recommended SR model and options based on the source metadata.
- As a user, I can override the recommendation and select a model and its options.
- As a user, I can run SR on a single image or batch and export the results with metadata intact.

## 6. Functional Requirements

### 6.1 Input and Metadata
- Support drag-and-drop and folder selection for input.
- Support common satellite image formats (TIFF/GeoTIFF, JP2, PNG, JPEG) and preserve geospatial metadata.
- Automatically read metadata (sensor, resolution, bands, CRS, acquisition time, tile/scene id, etc.).
- Detect source (Sentinel, Planet, or other) using metadata heuristics.
- Allow user to choose band handling: RGB only, RGB + all bands, or all bands.
- If source detection is ambiguous or missing, prompt the user to select the source.

### 6.2 Stitching
- If multiple images form a contiguous mosaic, prompt the user to stitch into one image.
- Maintain geospatial metadata and band alignment during stitching.
- Provide a preview of stitching boundaries and the resulting image extent.
- Stitching trigger: auto-detect adjacency/overlap and prompt.

### 6.3 Model Recommendation
- Recommend the best SR model based on:
  - Source/sensor type
  - Resolution and band count
  - Image size and hardware availability
- Recommend model options (scale factor, tiling strategy, precision, etc.).
- Allow user override with clear warnings when the choice is suboptimal.
- Recommendation engine: rule-based mapping in v1.

### 6.3.1 Provider-to-Model Mapping (Initial, subject to validation)
- Sentinel-2: S2DR3 (multi-band, 1m), OpenSR/SEN2SR, Satlas (S2-NAIP).
- PlanetScope: no provider-specific model found; default to SRGAN adapted to EO or SatelliteSR; fallback to SwinIR/Real-ESRGAN for RGB-only.
- Landsat: no provider-specific model found; default to SwinIR/Real-ESRGAN for RGB-only; treat multispectral SR as experimental.
- Vantor (WorldView): SRGAN adapted to EO (shown effective on WorldView-2); optional SatelliteSR.
- 21AT (TripleSat): SRGAN adapted to EO or SatelliteSR; caution because imagery is already high resolution.
- Meteorological cloud imagery (any provider): MRDAM.

### 6.4 Model Support (Initial List)
All models must be available via one-click install; bundling vs optional depends on license:
- Bundled (permissive): Real-ESRGAN, Satlas.
- Available one-click (permissive): SwinIR, HAT (Hybrid Attention Transformer), Swin2SR, OpenSR (SEN2SR, LDSR-S2), S2DR3, MRDAM, SatelliteSR (kmalhan/SatelliteSR), SRGAN adapted to EO, SenGLEAN (license TBD; optional until verified), EVOLAND Sentinel-2 SR.
- Available one-click (non-permissive; user accepts license; not bundled): Swin2-MoSE (GPL-2.0), DSen2 (GPL-3.0).
- EO-SR category: v1 implements EO-SR via SatelliteSR + SRGAN adapted to EO (no separate ambiguous EO-SR placeholder).
- Licensing policy (v1): only permissive licenses (MIT/BSD/Apache) can be bundled/distributed; non-permissive models are optional user-initiated installs with explicit license acceptance.
- License-unknown models are treated as optional and cannot be bundled until confirmed permissive.
- v1 integration priority: Satlas, EO-SR options (SatelliteSR + SRGAN adapted to EO), S2DR3, MRDAM.

### 6.5 Processing and Export
- Run SR locally with progress reporting, ETA, and logs.
- Export results in the same format as input by default, preserving metadata.
- Allow output format selection and output location selection.
- When a user selects a different output format, preserve metadata where possible and warn on any metadata loss.
- Large image handling: try full-image processing first, then fall back to tiling on out-of-memory.
- Scale factors: model-specific only (expose the scales each model supports).
- Batch processing: single-job sequential queue in v1.
- Batch runs: one config per batch (no per-image overrides in v1).
- Project management: simple run history with a re-run button.
- Error handling: show error summary with suggested fixes and a retry option.
- Session persistence: auto-save local session state (not shareable project files).
- Notifications: in-app progress with optional desktop notification on completion.
- Job cancellation: allow cancel and discard partial outputs.
- Provide a dry-run mode that estimates runtime and VRAM usage.
- Compute selection: allow manual GPU/CPU override.
- Safe mode: force CPU, disable advanced options, and use conservative defaults.
- Model health check: run after model install or on first launch to verify dependencies.
- Crash recovery: auto-reopen the last session after a crash.
- Processing report: optional export of settings, model versions, and timings per run.
- Reprojection: not supported in v1.
- Model comparison runs are single-image only (no batch comparison in v1).

## 7. UX Requirements
- Modern, clean, minimal UI with large, clear actions.
- Single primary workflow: Import -> Review -> (Optional Stitch) -> Recommend -> Run -> Export.
- Show detected metadata and source in a readable summary panel.
- Provide presets for common datasets (Sentinel-2, PlanetScope, Vantor, 21AT, Landsat).
- Allow users to select band handling: RGB only, RGB + all bands, or all bands.
- Default home screen: two-pane layout with input list on the left and preview + metadata on the right.
- Advanced model options: simple defaults with an "Advanced" collapsible panel.
- Include a basic model manager UI for install/uninstall and version visibility.
- Model installs must be one-click; the app handles all downloads, dependencies, and setup automatically.
- Include a before/after comparison viewer with side-by-side and swipe.
- Provide export presets and recommend the best preset for the current use case.
- Include an About/System Info panel with GPU, CUDA, and model version details.
- Provide sample datasets via on-demand download for first-run demo/testing.
- Model comparison: allow side-by-side comparison by running up to two models on the same input.
- Accessibility: provide keyboard shortcuts for primary actions.
- Include a simple changelog view for app/model updates.

## 8. Technical Requirements

### 8.1 Architecture
- UI framework: Qt (PySide6).
- Modular model runner interface (plugin-style) to support multiple SR models.
- Isolated runtime environments per model where necessary (virtual env/conda/docker-lite). Recommended: embedded Python runtimes or per-model venvs managed by the app.
- Per-model virtual environments (venvs) for dependency isolation.
- NVIDIA CUDA acceleration baseline with CPU fallback where possible.
- Geospatial I/O: hybrid approach using Rasterio for most operations and GDAL CLI for edge cases.
- Settings persistence: local settings file in app data (global preferences).
- GPU support (v1): NVIDIA CUDA + CPU fallback only.
- Minimum OS support: Windows 10+, macOS 12+, Ubuntu 20.04+.
- Minimum hardware: 16 GB RAM, 6 GB VRAM.
- Provide a minimal CLI companion that mirrors the GUI pipeline for batch automation.

### 8.2 Dependency Management
- Pin all model dependencies, including CUDA/CPU variants.
- Avoid system-wide dependency installation. No changes to global Python or system libraries.
- Provide model downloads in a controlled cache managed by the app.
- Hybrid model weights strategy: bundle 1-2 default models in the installer; download other models on demand.
- Model cache: provide a visible default cache location that users can change.
- Model installation must be fully automated (no manual steps, no CLI) after a single user click.

### 8.3 Installer
- Provide signed installers for Windows (.msi), macOS (.dmg), Linux (.AppImage).
- Installer must not alter system PATH, global Python, or global libraries unless user opts in.
- Include all required runtimes or provide guided download within the app.

## 9. Performance Requirements
- Handle large GeoTIFFs and JP2 files (multi-GB) with tiling/streaming.
- Support batch processing with queue management.
- Provide memory-safe operations with bounded RAM usage.

## 10. Security and Privacy
- Default to offline processing.
- No telemetry by default. If analytics are added later, require explicit opt-in.
- All files remain local; no uploads unless the user configures cloud features.
- Logging: basic logs with an exportable log file for support/debugging.
- Updates: automatic checks for app and model updates (opt-in).
- Network usage: no explicit offline toggle; only access the network when needed for model downloads or opt-in updates.

## 11. Acceptance Criteria
- User can import and process at least 10 sample satellite images across supported formats.
- Automatic source detection works for Sentinel-2 and PlanetScope samples.
- Stitching produces correct geospatial alignment and preserves metadata.
- At least 5 SR models fully integrated and runnable on CPU in v1.
- Minimum CPU-validated models: Real-ESRGAN, SwinIR, SRGAN adapted to EO, SatelliteSR, MRDAM.
- Installer works on Windows/macOS/Linux without breaking other software.
- UI framework is Qt (PySide6) and runs on Windows/macOS/Linux.
- NVIDIA CUDA acceleration works where available, with CPU fallback verified.
- Users can select band handling (RGB only / RGB+all / all bands).
- Licensing validation passes for all bundled models (permissive only).
- Each model integration passes a standard validation suite with EO sample images and expected metrics before proceeding to the next model.
- Validation metrics: PSNR/SSIM plus visual inspection.
- Model installation is one-click and fully automated (no manual steps, no external installers).

## 12. Milestones (Proposed)
1. Discovery and model review (licenses, dependencies, input/output constraints)
2. UI/UX prototype
3. Core pipeline: import, metadata read, recommendation engine
4. Stitching module
5. Model integration phase 1
6. Installer packaging and QA
7. Beta release

## 13. Risks and Mitigations
- Model dependency conflicts - isolate per model via managed environments.
- Large file performance issues - streaming IO and tiling.
- GPU driver variability - clear compatibility checks and CPU fallback.
- Licensing conflicts - review and document licenses early.

## 14. Open Questions
- None for v1 (license-unknown models remain optional until verified).

## 15. Next Steps
- Verify licenses for SenGLEAN and SRGAN adapted to EO.
- Define validation datasets and expected PSNR/SSIM baselines.
- Draft packaging/build pipeline for Qt + per-model venvs.
- Implement model manager + one-click install flows.
