"""CLI to validate EO samples for multiple models with PSNR/SSIM and previews."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.validation import (
    evaluate_dataset,
    load_samples_from_manifest,
    report_to_dict,
    write_preview_ppm,
)

DEFAULT_SAMPLE_MODELS = (
    "SatelliteSR",
    "SRGAN adapted to EO",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate EO sample dataset for multiple models with PSNR/SSIM and previews."
    )
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled sample EO dataset manifest for all models.",
    )
    parser.add_argument(
        "--models",
        type=str,
        default=None,
        help="Comma-separated model names to validate (default: SatelliteSR, SRGAN adapted to EO).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/eo_validation_models"),
        help="Directory for report JSON and preview images.",
    )
    parser.add_argument(
        "--data-range",
        type=float,
        default=None,
        help="Override data range for PSNR/SSIM and previews.",
    )
    parser.add_argument(
        "--bands",
        type=str,
        default=None,
        help="Comma-separated band indices for RGB preview (default 0,1,2).",
    )
    parser.add_argument(
        "--skip-previews",
        action="store_true",
        help="Skip generating preview images.",
    )
    return parser.parse_args()


def _parse_bands(value: str | None) -> list[int] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return [int(part) for part in parts]


def _sample_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "sample_data" / "eo_sample" / "manifest.json"


def _slugify(name: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_")
    return cleaned or "model"


def _resolve_models(value: str | None) -> list[str]:
    if not value:
        return list(DEFAULT_SAMPLE_MODELS)
    models = [part.strip() for part in value.split(",") if part.strip()]
    return models


def main() -> int:
    args = _parse_args()
    if not args.sample:
        raise ValueError("Only --sample is supported for multi-model validation.")

    models = _resolve_models(args.models)
    missing = [model for model in models if model not in DEFAULT_SAMPLE_MODELS]
    if missing:
        raise ValueError(f"Unsupported model(s): {', '.join(missing)}")

    manifest_path = _sample_manifest_path()
    samples = load_samples_from_manifest(manifest_path)
    bands = _parse_bands(args.bands)

    output_root = args.output
    output_root.mkdir(parents=True, exist_ok=True)

    for model_name in models:
        report = evaluate_dataset(samples, data_range=args.data_range)
        output_dir = output_root / _slugify(model_name)
        output_dir.mkdir(parents=True, exist_ok=True)

        report_payload = report_to_dict(report)
        report_payload["model"] = model_name
        report_path = output_dir / "report.json"
        report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        if not args.skip_previews:
            for sample in samples:
                preview_path = output_dir / f"{sample.name}_preview.ppm"
                write_preview_ppm(
                    sample.reference,
                    sample.prediction,
                    output_path=preview_path,
                    bands=bands,
                    data_range=args.data_range,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
