from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

# Support direct script execution (python backend/main.py) by adding repo root.
if __package__ in {None, ""}:
    _repo_root = Path(__file__).resolve().parents[1]
    _repo_root_str = str(_repo_root)
    if _repo_root_str not in sys.path:
        sys.path.insert(0, _repo_root_str)

from app.band_handling import BandHandling
from app.dataset_analysis import DatasetInfo, analyze_dataset
from app.error_handling import UserFacingError
from app.hardware_profile import detect_hardware_profile
from app.imagery_policy import (
    RgbBandMapping,
    build_output_plan,
    default_rgb_mapping,
    load_model_band_support,
    model_supports_dataset,
)
from app.model_selection import recommend_execution_plan
from app.stitching import ReprojectionNotSupportedError, stitch_rasters
from app.model_entrypoints import build_model_wrapper, resolve_model_entrypoint
from app.upscale_execution import UpscaleRequest, expand_input_paths, run_upscale_batch


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.list_models:
        return _handle_list_models()

    raw_inputs = list(args.input or [])
    if not raw_inputs:
        parser.print_usage(sys.stderr)
        print("error: --input is required unless --list-models is used", file=sys.stderr)
        return 2

    try:
        input_paths = expand_input_paths(raw_inputs)
        if not input_paths:
            raise UserFacingError(
                title="No supported inputs found",
                summary="No supported TIFF/JP2/PNG/JPEG files were found in the selection.",
                suggested_fixes=(
                    "Provide explicit file paths or folders with supported imagery files.",
                ),
                error_code="CLI-001",
                can_retry=False,
            )
        input_paths, stitch_note, stitch_temp_dir = _maybe_stitch_inputs(
            input_paths,
            stitch=args.stitch,
        )

        band_handling = _parse_band_handling(args.band_handling)
        model_details: dict[str, str] | None = None
        if args.model:
            model_details = _validate_model_runtime(
                model_name=args.model,
                model_version=args.model_version,
                cache_dir=args.cache_dir,
            )

        dataset_infos = [analyze_dataset(path) for path in input_paths]
        output_dir = _resolve_output_dir(args.output_dir, input_paths)
        requests = _build_requests(
            dataset_infos=dataset_infos,
            scale=args.scale,
            output_format=args.output_format,
            band_handling=band_handling,
            model_name=args.model,
            model_version=args.model_version,
            cache_dir=args.cache_dir,
            tiling=args.tiling,
            precision=args.precision,
            compute=args.compute,
            safe_mode=args.safe_mode,
        )

        if args.dry_run:
            _print_dry_run_summary(
                output_dir=output_dir,
                requests=requests,
                model_details=model_details,
                stitch_note=stitch_note,
            )
            return 0

        artifacts = run_upscale_batch(requests, output_dir=output_dir)
        report = _build_report_payload(
            output_dir=output_dir,
            requests=requests,
            model_details=model_details,
            artifacts=artifacts,
            stitch_note=stitch_note,
        )
        if args.report:
            report_path = Path(args.report).expanduser()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Report written: {report_path}")

        print(
            f"Completed {len(artifacts)} file(s). Output directory: {output_dir}",
            file=sys.stdout,
        )
        return 0
    except UserFacingError as error:
        _print_user_facing_error(error)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"Unhandled error: {exc}", file=sys.stderr)
        return 1
    finally:
        if "stitch_temp_dir" in locals() and stitch_temp_dir is not None:
            shutil.rmtree(stitch_temp_dir, ignore_errors=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="CLI companion for satellite image upscaling.",
        epilog=(
            "Example: python backend/main.py --input C:/data/tile.tif "
            "--output-dir C:/data/out --output-format GeoTIFF --band-handling \"All bands\""
        ),
    )
    parser.add_argument(
        "--input",
        action="append",
        help="Input file or folder path. Repeat for multiple inputs.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to upscaled_output near first input.",
    )
    parser.add_argument(
        "--output-format",
        default="Match input",
        help="Output format: Match input, GeoTIFF, PNG, JPEG.",
    )
    parser.add_argument(
        "--band-handling",
        default=BandHandling.RGB_PLUS_ALL.value,
        help="Band handling: RGB only, RGB + all bands, All bands.",
    )
    parser.add_argument("--scale", type=int, default=None, help="Upscale factor.")
    parser.add_argument(
        "--model",
        default=None,
        help="Optional model name to validate installed runtime compatibility.",
    )
    parser.add_argument(
        "--model-version",
        default="Latest",
        help="Model version for runtime validation (default: Latest).",
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Optional model cache directory override used for runtime validation.",
    )
    parser.add_argument(
        "--tiling",
        default=None,
        help="Optional tiling override (example: 512 px, Off).",
    )
    parser.add_argument(
        "--precision",
        default=None,
        help="Optional precision override (FP16 or FP32).",
    )
    parser.add_argument(
        "--compute",
        default=None,
        help="Optional compute override (GPU or CPU).",
    )
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Force CPU and conservative model defaults.",
    )
    parser.add_argument(
        "--stitch",
        action="store_true",
        help="Stitch selected inputs into one mosaic before processing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze inputs and print execution plan without writing outputs.",
    )
    parser.add_argument(
        "--report",
        default=None,
        help="Write a JSON execution report to this path.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List model names from models/registry.json and exit.",
    )
    return parser


def _handle_list_models() -> int:
    names = sorted(str(entry.get("name", "")) for entry in _load_model_registry())
    names = [name for name in names if name]
    if not names:
        print("No models found.", file=sys.stderr)
        return 1
    for name in names:
        print(name)
    return 0


def _parse_band_handling(value: str) -> BandHandling:
    normalized = value.strip().lower()
    mapping = {
        BandHandling.RGB_ONLY.value.lower(): BandHandling.RGB_ONLY,
        BandHandling.RGB_PLUS_ALL.value.lower(): BandHandling.RGB_PLUS_ALL,
        BandHandling.ALL_BANDS.value.lower(): BandHandling.ALL_BANDS,
        "rgb": BandHandling.RGB_ONLY,
        "rgb-only": BandHandling.RGB_ONLY,
        "rgb+all": BandHandling.RGB_PLUS_ALL,
        "rgb-all": BandHandling.RGB_PLUS_ALL,
        "all": BandHandling.ALL_BANDS,
    }
    result = mapping.get(normalized)
    if result is None:
        raise UserFacingError(
            title="Invalid band handling",
            summary=f"Unsupported band handling option: {value}",
            suggested_fixes=(
                "Use one of: RGB only, RGB + all bands, All bands.",
            ),
            error_code="CLI-002",
            can_retry=False,
        )
    return result


def _validate_model_runtime(
    *,
    model_name: str,
    model_version: str,
    cache_dir: str | None,
) -> dict[str, str]:
    model_names = {str(entry.get("name", "")) for entry in _load_model_registry()}
    if model_name not in model_names:
        raise UserFacingError(
            title="Unknown model",
            summary=f"Model '{model_name}' was not found in models/registry.json.",
            suggested_fixes=("Use --list-models to see available names.",),
            error_code="CLI-003",
            can_retry=False,
        )
    if resolve_model_entrypoint(model_name) is None:
        raise UserFacingError(
            title="Model integration missing",
            summary=f"Model '{model_name}' has no registered inference entrypoint.",
            suggested_fixes=(
                "Select a model with a registered wrapper.",
                "Complete model integration before running this model.",
            ),
            error_code="CLI-004",
            can_retry=False,
        )
    wrapper = build_model_wrapper(
        model_name,
        model_version,
        cache_dir=Path(cache_dir).expanduser() if cache_dir else None,
    )
    return {
        "name": wrapper.name,
        "version": wrapper.version,
        "entrypoint": wrapper.entrypoint,
        "weights_path": str(wrapper.weights_path),
        "venv_dir": str(wrapper.venv_dir),
    }


def _resolve_output_dir(output_dir: str | None, input_paths: list[Path]) -> Path:
    if output_dir:
        return Path(output_dir).expanduser()
    anchor = input_paths[0]
    base = anchor.parent if anchor.is_file() else anchor
    return base / "upscaled_output"


def _maybe_stitch_inputs(
    input_paths: list[Path],
    *,
    stitch: bool,
) -> tuple[list[Path], str | None, Path | None]:
    if not stitch:
        return input_paths, None, None
    if len(input_paths) < 2:
        raise UserFacingError(
            title="Stitching needs multiple inputs",
            summary="--stitch requires at least two input tiles.",
            suggested_fixes=(
                "Add more --input paths.",
                "Remove --stitch for single-image processing.",
            ),
            error_code="CLI-006",
            can_retry=False,
        )

    temp_dir = Path(tempfile.mkdtemp(prefix="satellite-upscale-cli-stitch-"))
    stitched_path = temp_dir / "stitched_input.tif"
    try:
        stitch_rasters([str(path) for path in input_paths], str(stitched_path))
    except ReprojectionNotSupportedError as exc:
        raise UserFacingError(
            title="Stitching requires reprojection",
            summary="The selected tiles cannot be stitched because they use different CRS grids.",
            suggested_fixes=(
                "Provide tiles on the same CRS/grid when using --stitch.",
                "Run without --stitch and process tiles separately.",
            ),
            error_code="CLI-007",
            can_retry=False,
        ) from exc
    except Exception as exc:
        raise UserFacingError(
            title="Stitching failed",
            summary="Failed to stitch selected tiles before run planning.",
            suggested_fixes=(
                "Retry with fewer files to isolate the failing input.",
                "Run without --stitch if the issue persists.",
            ),
            error_code="CLI-008",
            can_retry=True,
        ) from exc
    if not stitched_path.is_file():
        raise UserFacingError(
            title="Stitching failed",
            summary="No stitched output file was produced.",
            suggested_fixes=(
                "Retry with the same inputs.",
                "Run without --stitch if the issue persists.",
            ),
            error_code="CLI-009",
            can_retry=True,
        )
    note = f"Stitched {len(input_paths)} input files into one mosaic."
    return [stitched_path], note, temp_dir


def _build_requests(
    *,
    dataset_infos: list[DatasetInfo],
    scale: int | None,
    output_format: str,
    band_handling: BandHandling,
    model_name: str | None,
    model_version: str,
    cache_dir: str | None,
    tiling: str | None,
    precision: str | None,
    compute: str | None,
    safe_mode: bool,
) -> list[UpscaleRequest]:
    requests: list[UpscaleRequest] = []
    hardware = detect_hardware_profile()
    band_support = load_model_band_support()
    cache_dir_path = Path(cache_dir).expanduser() if cache_dir else None
    for info in dataset_infos:
        plan = build_output_plan(getattr(info, "format_label", None), output_format)
        mapping: RgbBandMapping | None = None
        band_count = getattr(info, "band_count", None)
        if plan.visual_format and isinstance(band_count, int) and band_count > 3:
            mapping = default_rgb_mapping(getattr(info, "provider", None), band_count)
        model_plan = recommend_execution_plan(
            info,
            hardware,
            model_override=model_name,
            scale_override=scale,
            tiling_override=tiling,
            precision_override=precision,
            compute_override=compute,
            safe_mode=safe_mode,
        )
        if (
            band_count is not None
            and band_count > 3
            and not model_supports_dataset(
                model_plan.model,
                getattr(info, "provider", None),
                band_count,
                band_support=band_support,
            )
        ):
            provider_text = getattr(info, "provider", None) or "unknown provider"
            raise UserFacingError(
                title="Model is not multispectral-compatible",
                summary=(
                    f"Model '{model_plan.model}' is not marked as compatible with "
                    f"{provider_text} multispectral inputs."
                ),
                suggested_fixes=(
                    "Choose a model that explicitly supports this provider/band profile.",
                    "Use RGB-only inputs if the model is RGB-only.",
                ),
                error_code="CLI-005",
                can_retry=False,
            )
        request_version = model_version if (model_name and model_plan.model == model_name) else "Latest"
        requests.append(
            UpscaleRequest(
                input_path=getattr(info, "path"),
                output_plan=plan,
                scale=model_plan.scale,
                band_handling=band_handling,
                rgb_mapping=mapping,
                reproject_to=None,
                model_name=model_plan.model,
                model_version=request_version,
                model_cache_dir=cache_dir_path,
                tiling=model_plan.tiling,
                precision=model_plan.precision,
                compute=model_plan.compute,
            )
        )
    return requests


def _print_dry_run_summary(
    *,
    output_dir: Path,
    requests: list[UpscaleRequest],
    model_details: dict[str, str] | None,
    stitch_note: str | None,
) -> None:
    print(f"Dry run: {len(requests)} input(s)")
    print(f"Output directory: {output_dir}")
    if stitch_note:
        print(stitch_note)
    if model_details:
        print(
            f"Model runtime validated: {model_details['name']} ({model_details['version']})"
        )
    for request in requests:
        visual = request.output_plan.visual_format or "none"
        model_text = request.model_name or "none"
        print(
            f"- {request.input_path.name}: master={request.output_plan.master_format}, "
            f"visual={visual}, scale={request.scale}, model={model_text}, "
            f"precision={request.precision}, compute={request.compute}"
        )


def _build_report_payload(
    *,
    output_dir: Path,
    requests: list[UpscaleRequest],
    model_details: dict[str, str] | None,
    artifacts: list[object],
    stitch_note: str | None,
) -> dict[str, object]:
    return {
        "output_dir": str(output_dir),
        "request_count": len(requests),
        "model": model_details,
        "stitch": stitch_note,
        "requests": [
            {
                "input": str(request.input_path),
                "master_format": request.output_plan.master_format,
                "visual_format": request.output_plan.visual_format,
                "scale": request.scale,
                "band_handling": request.band_handling.value,
                "model": request.model_name,
                "model_version": request.model_version,
                "tiling": request.tiling,
                "precision": request.precision,
                "compute": request.compute,
            }
            for request in requests
        ],
        "artifacts": [
            {
                "input": str(artifact.input_path),
                "master_output": str(artifact.master_output_path),
                "visual_output": (
                    str(artifact.visual_output_path)
                    if artifact.visual_output_path is not None
                    else None
                ),
            }
            for artifact in artifacts
        ],
    }


def _print_user_facing_error(error: UserFacingError) -> None:
    print(f"{error.title}: {error.summary}", file=sys.stderr)
    for fix in error.suggested_fixes:
        print(f"- {fix}", file=sys.stderr)
    print(f"Error code: {error.error_code}", file=sys.stderr)


def _load_model_registry() -> list[dict[str, object]]:
    registry_path = Path(__file__).resolve().parents[1] / "models" / "registry.json"
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    models: list[dict[str, object]] = []
    for item in payload:
        if isinstance(item, dict):
            models.append(item)
    return models


if __name__ == "__main__":
    raise SystemExit(main())
