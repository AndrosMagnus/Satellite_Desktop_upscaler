"""CLI to validate cloud imagery samples with PSNR/SSIM and preview outputs."""

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate cloud imagery samples with PSNR/SSIM and generate previews."
    )
    manifest_group = parser.add_mutually_exclusive_group(required=True)
    manifest_group.add_argument(
        "--manifest",
        type=Path,
        help="Path to JSON manifest listing reference/prediction pairs.",
    )
    manifest_group.add_argument(
        "--sample",
        action="store_true",
        help="Use the bundled cloud sample dataset manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/cloud_validation"),
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
    return Path(__file__).resolve().parent / "sample_data" / "clouds_sample" / "manifest.json"


def main() -> int:
    args = _parse_args()
    manifest_path = _sample_manifest_path() if args.sample else args.manifest
    if manifest_path is None:
        raise ValueError("Manifest path was not provided.")
    samples = load_samples_from_manifest(manifest_path)
    report = evaluate_dataset(samples, data_range=args.data_range)
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    report_path = output_dir / "report.json"
    report_path.write_text(json.dumps(report_to_dict(report), indent=2), encoding="utf-8")

    if not args.skip_previews:
        bands = _parse_bands(args.bands)
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
