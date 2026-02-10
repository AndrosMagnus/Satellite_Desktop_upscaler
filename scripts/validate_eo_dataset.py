"""CLI to validate EO samples with PSNR/SSIM and preview outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

if __package__ in {None, ""}:
    _REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))

from app.validation import (
    evaluate_dataset,
    load_samples_from_manifest,
    report_to_dict,
    write_preview_ppm,
)
from app.validation_baselines import (
    evaluate_threshold,
    load_validation_baselines,
    resolve_threshold,
    threshold_to_dict,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate EO dataset samples with PSNR/SSIM and generate previews."
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
        help="Use the bundled sample EO dataset manifest.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/eo_validation"),
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
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).resolve().parent / "sample_data" / "validation_baselines.json",
        help="Baseline threshold JSON file.",
    )
    parser.add_argument(
        "--fail-on-threshold",
        action="store_true",
        help="Exit with code 2 if metrics do not meet threshold.",
    )
    return parser.parse_args()


def _parse_bands(value: str | None) -> list[int] | None:
    if value is None:
        return None
    parts = [part.strip() for part in value.split(",") if part.strip()]
    return [int(part) for part in parts]


def _sample_manifest_path() -> Path:
    return Path(__file__).resolve().parent / "sample_data" / "eo_sample" / "manifest.json"


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
    payload = report_to_dict(report)
    threshold = resolve_threshold(
        load_validation_baselines(args.baseline),
        dataset="eo",
    )
    if threshold is not None:
        result = evaluate_threshold(report, threshold)
        payload["threshold"] = threshold_to_dict(threshold, result)
        if args.fail_on_threshold and not result.passed:
            report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return 2
    report_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

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
