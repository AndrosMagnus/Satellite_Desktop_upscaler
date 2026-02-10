# User Guide

## Import
- Use `Add Files` or `Add Folder` from the left panel.
- Select one file for single-run workflows or multiple files for batch.

## Review
- Verify preview and metadata in the right panel.
- Confirm provider/preset recommendation before running.

## Optional Stitch
- Select two or more adjacent tiles.
- Use `Stitch (Optional)` to preview bounds and queue stitch-then-run execution.

## Model and Options
- Use recommended preset or override in `Export Presets`.
- Adjust advanced settings (`scale`, `tiling`, `precision`, `compute`) when needed.
- Use Safe Mode for conservative CPU-first settings.

## Run
- Choose output folder in `Run Output` (`Browse` or leave empty for auto default).
- Start from workflow `Run`.
- Track progress in the run progress bar and label.
- Use `Cancel run` to stop between files.

## Export
- Default output is preservation-safe for geospatial inputs.
- If you choose a visual-only format (PNG/JPEG), the app may produce dual output:
  geospatial master + visual export.
