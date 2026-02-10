# Troubleshooting

## GPU / CUDA
- Symptom: GPU not detected.
- Check:
  - NVIDIA driver installed.
  - `nvidia-smi` works in terminal.
  - Compute mode is `Auto` or `GPU`.

## Slow Processing
- Symptom: runs are slower than expected.
- Check:
  - CPU fallback may be active.
  - Safe Mode may be enabled.
  - Reduce scale or enable tiling.

## Metadata Warnings
- Symptom: warning about metadata loss on export.
- Cause: output format does not preserve geospatial metadata.
- Fix:
  - Use `GeoTIFF` or `Match input`.
  - Keep dual-output enabled when visual exports are needed.

## Missing Model Runtime
- Symptom: model run/install errors with missing files or venv.
- Fix:
  - Reinstall from Model Manager.
  - Ensure cache directory is valid and writable.

## Large Batch Cancellation
- `Cancel run` stops between files in the current pipeline.
- If a single file is long-running, cancellation may complete at the next file boundary.

