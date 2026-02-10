# Validation Baselines

The baseline thresholds used by validation scripts are stored in:

- `scripts/sample_data/validation_baselines.json`

Current baseline keys:

- `sentinel2` (single-model Sentinel-2 validation)
- `eo` (EO validation and per-model overrides)
- `clouds` (cloud-imagery validation)

Each threshold entry defines:

- `psnr_min`: minimum average PSNR required
- `ssim_min`: minimum average SSIM required

Validation scripts support:

- `--baseline <path>`: override threshold file
- `--fail-on-threshold`: return exit code `2` if averages fall below baseline

Updated scripts:

- `scripts/validate_sentinel2_dataset.py`
- `scripts/validate_eo_dataset.py`
- `scripts/validate_eo_models.py`
- `scripts/validate_cloud_dataset.py`
