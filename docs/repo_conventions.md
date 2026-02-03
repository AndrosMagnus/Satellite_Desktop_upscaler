# Repository-Wide Conventions

This document defines shared conventions for the desktop upscaling app. These standards apply
across backend services, CLI tools, and the desktop UI unless explicitly overridden in a
component-specific design note.

## Logging

### Format
- Use structured JSON lines (one JSON object per line).
- Timestamp field: `ts` in ISO 8601 UTC format (e.g., `2026-02-03T18:04:12Z`).
- Core fields: `level`, `component`, `event`, `message`.
- Optional fields: `request_id`, `job_id`, `model_name`, `duration_ms`, `error_code`.

### File Location
- Logs are written to an app-specific `logs/` directory under the platform data directory.
- Preferred path resolution uses `platformdirs` (or equivalent) with app name
  `SatelliteUpscale`.
- Default locations:
  - Windows: `%APPDATA%\\SatelliteUpscale\\logs\\app.log`
  - macOS: `~/Library/Application Support/SatelliteUpscale/logs/app.log`
  - Linux: `~/.local/share/SatelliteUpscale/logs/app.log`

### Rotation
- Rotate at 10 MB per file, keep the last 5 files.
- The active file is always `app.log`.

## Error Handling

### Principles
- Classify errors as either user-facing or internal-only.
- User-facing errors must be actionable, avoid stack traces, and suggest next steps.
- Internal errors must include stack traces in logs with context fields (`error_code`,
  `component`, `event`).

### Error Codes
- Use stable, human-readable codes in the form `AREA-CODE`, for example `IO-001` or
  `MODEL-003`.
- Error codes appear in both logs and user-facing dialogs.

### User-Facing Messaging
- Provide a short title, a concise explanation, and a recommended action.
- Example:
  - Title: "Model download failed"
  - Message: "We could not download the selected model. Check your network connection or
    try again later."
  - Code: `MODEL-002`

## Configuration

### Storage Location
- Store configuration in a single JSON file named `config.json` under the platform
  configuration directory.
- Preferred path resolution uses `platformdirs` (or equivalent) with app name
  `SatelliteUpscale`.
- Default locations:
  - Windows: `%APPDATA%\\SatelliteUpscale\\config.json`
  - macOS: `~/Library/Application Support/SatelliteUpscale/config.json`
  - Linux: `~/.config/SatelliteUpscale/config.json`

### Schema (v1)
- `schema_version`: integer, required.
- `last_opened_project`: string path or null.
- `recent_projects`: list of string paths, max 10.
- `default_output_dir`: string path.
- `preferred_model`: string model id.
- `logging`: object with `level` and `enable_file_logging`.

### Migration
- On startup, if `schema_version` is older than the app version, migrate in-place and
  write a backup named `config.json.bak`.
