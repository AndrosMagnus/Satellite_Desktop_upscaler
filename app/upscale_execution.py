from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from app.band_handling import BandHandling
from app.dataset_analysis import GridSignature
from app.error_handling import UserFacingError
from app.inference_adapter import InferenceAdapter, InferenceRequest
from app.imagery_policy import OutputPlan, RgbBandMapping
from app.model_entrypoints import build_model_wrapper
from app.output_metadata import format_preserves_metadata, normalize_format_label


SUPPORTED_INPUT_SUFFIXES = {".tif", ".tiff", ".jp2", ".png", ".jpg", ".jpeg"}

_CATEGORICAL_TOKENS = (
    "qa",
    "mask",
    "class",
    "label",
    "cloud",
    "flag",
    "scl",
)


@dataclass(frozen=True)
class UpscaleRequest:
    input_path: Path
    output_plan: OutputPlan
    scale: int
    band_handling: BandHandling
    rgb_mapping: RgbBandMapping | None = None
    reproject_to: GridSignature | None = None
    model_name: str | None = None
    model_version: str | None = None
    model_cache_dir: Path | None = None
    tiling: str | None = None
    precision: str | None = None
    compute: str | None = None
    output_tag: str | None = None


@dataclass(frozen=True)
class UpscaleArtifact:
    input_path: Path
    master_output_path: Path
    visual_output_path: Path | None
    notes: tuple[str, ...] = ()


class RunCancelledError(RuntimeError):
    """Raised when a user cancels an in-flight upscale batch."""


def expand_input_paths(paths: Sequence[str | Path]) -> list[Path]:
    expanded: list[Path] = []
    seen: set[Path] = set()
    for value in paths:
        candidate = Path(value)
        if candidate.is_dir():
            for child in sorted(candidate.rglob("*")):
                if not child.is_file():
                    continue
                if child.suffix.lower() not in SUPPORTED_INPUT_SUFFIXES:
                    continue
                resolved = child.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                expanded.append(resolved)
            continue
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        expanded.append(resolved)
    return expanded


def run_upscale_batch(
    requests: Sequence[UpscaleRequest],
    *,
    output_dir: Path,
    on_progress: Callable[[int, int, Path], None] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> list[UpscaleArtifact]:
    if not requests:
        return []
    artifacts: list[UpscaleArtifact] = []
    output_dir.mkdir(parents=True, exist_ok=True)
    total = len(requests)
    try:
        for index, request in enumerate(requests, start=1):
            if should_cancel is not None and should_cancel():
                raise RunCancelledError("Upscale run cancelled")
            artifact = run_upscale_request(request, output_dir=output_dir)
            artifacts.append(artifact)
            if on_progress is not None:
                on_progress(index, total, artifact.master_output_path)
            if should_cancel is not None and should_cancel():
                raise RunCancelledError("Upscale run cancelled")
    except RunCancelledError:
        _discard_artifacts(artifacts)
        _remove_empty_dir(output_dir)
        raise
    return artifacts


def _discard_artifacts(artifacts: Sequence[UpscaleArtifact]) -> None:
    for artifact in artifacts:
        for path in (artifact.master_output_path, artifact.visual_output_path):
            if path is None:
                continue
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                continue
            _remove_empty_dir(path.parent)


def _remove_empty_dir(directory: Path) -> None:
    try:
        if directory.exists() and directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
    except OSError:
        return


def run_upscale_request(
    request: UpscaleRequest,
    *,
    output_dir: Path,
) -> UpscaleArtifact:
    if request.scale <= 0:
        raise ValueError("scale must be positive")
    if not request.input_path.is_file():
        raise FileNotFoundError(str(request.input_path))

    master_output_path = _build_output_path(
        request.input_path,
        request.scale,
        request.output_plan.master_format,
        output_dir=output_dir,
        suffix="master",
        output_tag=request.output_tag,
    )
    notes: list[str] = []

    geospatial_master = format_preserves_metadata(request.output_plan.master_format)
    if geospatial_master:
        try:
            master_output_path, write_notes = _upscale_geospatial_master(
                request,
                master_output_path,
            )
            notes.extend(write_notes)
        except Exception:
            fallback_path = master_output_path.with_suffix(
                request.input_path.suffix or ".bin"
            )
            try:
                _upscale_visual_image(
                    request.input_path,
                    fallback_path,
                    scale=request.scale,
                    band_handling=request.band_handling,
                    rgb_mapping=request.rgb_mapping,
                )
                notes.append(
                    "Geospatial export fallback: produced visual upscale because geospatial IO failed."
                )
            except Exception:
                import shutil

                fallback_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(request.input_path, fallback_path)
                notes.append(
                    "Geospatial export fallback: copied source because image decoding failed."
                )
            master_output_path = fallback_path
    else:
        if request.model_name:
            model_ok = _run_model_inference(
                request,
                output_path=master_output_path,
            )
            if not model_ok:
                _upscale_visual_image(
                    request.input_path,
                    master_output_path,
                    scale=request.scale,
                    band_handling=request.band_handling,
                    rgb_mapping=request.rgb_mapping,
                )
                notes.append(
                    f"Model '{request.model_name}' unavailable; used built-in visual upscale fallback."
                )
        else:
            _upscale_visual_image(
                request.input_path,
                master_output_path,
                scale=request.scale,
                band_handling=request.band_handling,
                rgb_mapping=request.rgb_mapping,
            )

    visual_output_path: Path | None = None
    if request.output_plan.visual_format:
        visual_output_path = _build_output_path(
            request.input_path,
            request.scale,
            request.output_plan.visual_format,
            output_dir=output_dir,
            suffix="visual",
            output_tag=request.output_tag,
        )
        if request.model_name:
            model_ok = _run_model_inference(request, output_path=visual_output_path)
            if not model_ok:
                _build_visual_export(
                    request,
                    master_output_path=master_output_path,
                    visual_output_path=visual_output_path,
                )
                notes.append(
                    f"Model '{request.model_name}' unavailable for visual export; used built-in fallback."
                )
        else:
            _build_visual_export(
                request,
                master_output_path=master_output_path,
                visual_output_path=visual_output_path,
            )

    return UpscaleArtifact(
        input_path=request.input_path,
        master_output_path=master_output_path,
        visual_output_path=visual_output_path,
        notes=tuple(notes),
    )


def _run_model_inference(request: UpscaleRequest, *, output_path: Path) -> bool:
    if not request.model_name:
        return False
    version = request.model_version or "Latest"
    try:
        wrapper = build_model_wrapper(
            request.model_name,
            version,
            cache_dir=request.model_cache_dir,
        )
        adapter = InferenceAdapter()
        adapter.run(
            wrapper,
            InferenceRequest(
                input_path=request.input_path,
                output_path=output_path,
                scale=request.scale,
                tiling=request.tiling,
                precision=request.precision,
                compute=request.compute,
            ),
        )
    except Exception:
        return False
    return output_path.exists()


def _upscale_geospatial_master(
    request: UpscaleRequest,
    requested_output_path: Path,
) -> tuple[Path, list[str]]:
    try:
        import numpy as np
        import rasterio
        from affine import Affine
        from rasterio.enums import Resampling
        from rasterio.warp import reproject
    except ImportError as exc:
        raise UserFacingError(
            title="Geospatial runtime dependency missing",
            summary=(
                "Rasterio is required to preserve geospatial metadata for this output."
            ),
            suggested_fixes=(
                "Install rasterio and retry.",
                "Select a non-geospatial output only if metadata loss is acceptable.",
            ),
            error_code="IO-010",
            can_retry=True,
        ) from exc

    notes: list[str] = []
    driver = _driver_for_format(request.output_plan.master_format)

    with rasterio.open(request.input_path) as src:
        descriptions = tuple(src.descriptions) if src.descriptions else ()
        source_affine = src.transform
        out_width = src.width * request.scale
        out_height = src.height * request.scale
        out_crs = src.crs
        out_affine = source_affine * Affine.scale(1 / request.scale, 1 / request.scale)
        use_reproject = False
        if request.reproject_to is not None:
            target = request.reproject_to
            source_crs = src.crs.to_string() if src.crs is not None else None
            source_transform = (
                float(src.transform.a),
                float(src.transform.b),
                float(src.transform.c),
                float(src.transform.d),
                float(src.transform.e),
                float(src.transform.f),
            )
            use_reproject = (
                source_crs != target.crs
                or source_transform != target.transform
                or src.width != target.width
                or src.height != target.height
            )
        if use_reproject and request.reproject_to is not None:
            target = request.reproject_to
            out_width = target.width * request.scale
            out_height = target.height * request.scale
            out_affine = Affine(*target.transform) * Affine.scale(
                1 / request.scale, 1 / request.scale
            )
            out_crs = target.crs

        data = np.empty((src.count, out_height, out_width), dtype=src.dtypes[0])
        for band in range(1, src.count + 1):
            method = _resampling_for_band(
                description=descriptions[band - 1] if band - 1 < len(descriptions) else None,
                tags=src.tags(bidx=band),
                dtype=src.dtypes[band - 1],
                nearest=Resampling.nearest,
                continuous=Resampling.bilinear,
            )
            destination = data[band - 1]
            if use_reproject:
                reproject(
                    source=rasterio.band(src, band),
                    destination=destination,
                    src_transform=src.transform,
                    src_crs=src.crs,
                    src_nodata=src.nodata,
                    dst_transform=out_affine,
                    dst_crs=out_crs,
                    dst_nodata=src.nodata,
                    resampling=method,
                )
            else:
                destination[:] = src.read(
                    band,
                    out_shape=(out_height, out_width),
                    resampling=method,
                )

        profile = src.profile.copy()
        profile.update(
            {
                "driver": driver,
                "height": out_height,
                "width": out_width,
                "count": src.count,
                "transform": out_affine,
            }
        )
        if out_crs is not None:
            profile["crs"] = out_crs

        output_path = requested_output_path
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(data)
                if descriptions and len(descriptions) == src.count:
                    dst.descriptions = descriptions
                _copy_raster_metadata(src, dst)
        except Exception:
            fallback_path = requested_output_path.with_suffix(".tif")
            profile["driver"] = "GTiff"
            with rasterio.open(fallback_path, "w", **profile) as dst:
                dst.write(data)
                if descriptions and len(descriptions) == src.count:
                    dst.descriptions = descriptions
                _copy_raster_metadata(src, dst)
            output_path = fallback_path
            notes.append("Requested geospatial format unavailable; wrote GeoTIFF master instead.")

    return output_path, notes


def _build_visual_export(
    request: UpscaleRequest,
    *,
    master_output_path: Path,
    visual_output_path: Path,
) -> None:
    try:
        import numpy as np
        import rasterio
    except ImportError:
        _upscale_visual_image(
            request.input_path,
            visual_output_path,
            scale=request.scale,
            band_handling=BandHandling.RGB_ONLY,
            rgb_mapping=request.rgb_mapping,
        )
        return

    try:
        with rasterio.open(master_output_path) as src:
            mapping = request.rgb_mapping
            if mapping is None:
                mapping = _default_mapping_for_count(src.count)
            indexes = _mapping_to_indexes(mapping, src.count)
            array = src.read(indexes)
    except Exception:
        _upscale_visual_image(
            request.input_path,
            visual_output_path,
            scale=request.scale,
            band_handling=BandHandling.RGB_ONLY,
            rgb_mapping=request.rgb_mapping,
        )
        return

    rgb = np.transpose(array, (1, 2, 0))
    rgb_u8 = _to_uint8(rgb)
    _save_rgb_array(rgb_u8, visual_output_path)


def _upscale_visual_image(
    input_path: Path,
    output_path: Path,
    *,
    scale: int,
    band_handling: BandHandling,
    rgb_mapping: RgbBandMapping | None,
) -> None:
    try:
        import numpy as np
        from PIL import Image
    except ImportError as exc:
        raise UserFacingError(
            title="Image runtime dependency missing",
            summary="Pillow is required to produce visual image outputs.",
            suggested_fixes=(
                "Install Pillow and retry.",
                "Use geospatial output mode if you only need the master raster.",
            ),
            error_code="IO-011",
            can_retry=True,
        ) from exc

    resampling = _pil_bicubic(Image)

    with Image.open(input_path) as image:
        if band_handling == BandHandling.RGB_ONLY:
            image = image.convert("RGB")
            resized = image.resize(
                (image.width * scale, image.height * scale),
                resampling,
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            resized.save(output_path)
            return

        array = np.asarray(image)
        if array.ndim == 2:
            array = array[:, :, None]
        if array.shape[2] > 3 and rgb_mapping is not None:
            indices = _mapping_to_indexes(rgb_mapping, array.shape[2])
            array = array[:, :, [index - 1 for index in indices]]
        elif array.shape[2] > 3:
            array = array[:, :, :3]

        rgb_u8 = _to_uint8(array)
        rendered = Image.fromarray(rgb_u8, mode="RGB")
        resized = rendered.resize(
            (rendered.width * scale, rendered.height * scale),
            resampling,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        resized.save(output_path)


def _build_output_path(
    input_path: Path,
    scale: int,
    format_label: str,
    *,
    output_dir: Path,
    suffix: str,
    output_tag: str | None = None,
) -> Path:
    extension = _extension_for_format(format_label)
    stem = input_path.stem
    middle = ""
    if output_tag:
        sanitized = _sanitize_output_tag(output_tag)
        if sanitized:
            middle = f"_{sanitized}"
    filename = f"{stem}_x{scale}{middle}_{suffix}{extension}"
    return output_dir / filename


def _driver_for_format(format_label: str) -> str:
    normalized = normalize_format_label(format_label)
    if normalized in {"GEOTIFF", "TIFF", "TIF"}:
        return "GTiff"
    if normalized in {"JP2", "JPEG2000"}:
        return "JP2OpenJPEG"
    return "GTiff"


def _extension_for_format(format_label: str) -> str:
    normalized = normalize_format_label(format_label)
    if normalized in {"GEOTIFF", "TIFF", "TIF"}:
        return ".tif"
    if normalized in {"JP2", "JPEG2000"}:
        return ".jp2"
    if normalized == "PNG":
        return ".png"
    if normalized == "JPEG":
        return ".jpg"
    return ".tif"


def _sanitize_output_tag(value: str) -> str:
    cleaned: list[str] = []
    previous_dash = False
    for char in value.strip().lower():
        if char.isalnum():
            cleaned.append(char)
            previous_dash = False
            continue
        if not previous_dash:
            cleaned.append("-")
            previous_dash = True
    return "".join(cleaned).strip("-")


def _resampling_for_band(
    *,
    description: str | None,
    tags: dict[str, str],
    dtype: str,
    nearest: object,
    continuous: object,
) -> object:
    if _is_categorical_band(description=description, tags=tags, dtype=dtype):
        return nearest
    return continuous


def _is_categorical_band(
    *,
    description: str | None,
    tags: dict[str, str] | None,
    dtype: str,
) -> bool:
    value_parts: list[str] = []
    if description:
        value_parts.append(description.lower())
    if tags:
        for key, value in tags.items():
            value_parts.append(str(key).lower())
            value_parts.append(str(value).lower())
    joined = " ".join(value_parts)
    if any(token in joined for token in _CATEGORICAL_TOKENS):
        return True
    return dtype.lower() in {"bool", "uint8"} and "reflectance" not in joined


def _default_mapping_for_count(count: int) -> RgbBandMapping:
    if count <= 1:
        return RgbBandMapping(0, 0, 0, "single-band fallback")
    if count == 2:
        return RgbBandMapping(0, 1, 1, "two-band fallback")
    return RgbBandMapping(0, 1, 2, "rgb-first fallback")


def _mapping_to_indexes(mapping: RgbBandMapping, count: int) -> tuple[int, int, int]:
    candidates = (mapping.red, mapping.green, mapping.blue)
    indexes: list[int] = []
    for value in candidates:
        if value < 0:
            indexes.append(1)
            continue
        normalized = value + 1
        if normalized > count:
            normalized = count
        indexes.append(normalized)
    return (indexes[0], indexes[1], indexes[2])


def _to_uint8(array) -> object:
    import numpy as np

    values = np.asarray(array)
    if values.ndim == 2:
        values = np.repeat(values[:, :, None], 3, axis=2)
    if values.shape[2] == 1:
        values = np.repeat(values, 3, axis=2)
    if values.shape[2] == 2:
        values = np.concatenate((values, values[:, :, 1:2]), axis=2)
    if values.shape[2] > 3:
        values = values[:, :, :3]

    as_float = values.astype("float32")
    min_value = float(as_float.min()) if as_float.size else 0.0
    max_value = float(as_float.max()) if as_float.size else 0.0
    if max_value <= min_value:
        return np.zeros((as_float.shape[0], as_float.shape[1], 3), dtype="uint8")
    stretched = (as_float - min_value) / (max_value - min_value)
    return (stretched * 255.0).clip(0.0, 255.0).astype("uint8")


def _save_rgb_array(array, path: Path) -> None:
    from PIL import Image

    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.fromarray(array, mode="RGB")
    image.save(path)


def _pil_bicubic(image_module: object) -> object:
    resampling = getattr(image_module, "Resampling", None)
    if resampling is not None:
        return resampling.BICUBIC
    return image_module.BICUBIC


def _copy_raster_metadata(source: object, dest: object) -> None:
    try:
        dest.update_tags(**source.tags())
    except Exception:
        return

    for namespace in _tag_namespaces(source):
        try:
            tags = source.tags(ns=namespace)
        except Exception:
            continue
        if tags:
            dest.update_tags(ns=namespace, **tags)

    source_count = getattr(source, "count", 0)
    for band_index in range(1, source_count + 1):
        try:
            band_tags = source.tags(bidx=band_index)
        except Exception:
            band_tags = {}
        if band_tags:
            dest.update_tags(bidx=band_index, **band_tags)
        for namespace in _tag_namespaces(source, band_index):
            try:
                tags = source.tags(ns=namespace, bidx=band_index)
            except Exception:
                continue
            if tags:
                dest.update_tags(bidx=band_index, ns=namespace, **tags)

    for attr_name in ("colorinterp", "scales", "offsets", "units"):
        try:
            value = getattr(source, attr_name)
        except Exception:
            continue
        if value:
            try:
                setattr(dest, attr_name, value)
            except Exception:
                continue


def _tag_namespaces(source: object, band_index: int | None = None) -> tuple[str, ...]:
    namespaces_fn = getattr(source, "tag_namespaces", None)
    if namespaces_fn is None:
        return ()
    try:
        if band_index is None:
            namespaces = namespaces_fn()
        else:
            namespaces = namespaces_fn(bidx=band_index)
    except Exception:
        return ()
    if not namespaces:
        return ()
    return tuple(ns for ns in namespaces if ns)
