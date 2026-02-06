"""Raster tile stitching helpers with geospatial metadata preservation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import tempfile
from typing import Sequence


@dataclass(frozen=True)
class RasterTile:
    bands: list[list[list[float]]]
    transform: tuple[float, float, float, float]
    crs: str | None = None
    band_names: list[str] | None = None
    nodata: float | None = None

    @property
    def width(self) -> int:
        if not self.bands or not self.bands[0]:
            return 0
        return len(self.bands[0][0])

    @property
    def height(self) -> int:
        if not self.bands:
            return 0
        return len(self.bands[0])

    @property
    def band_count(self) -> int:
        return len(self.bands)


class ReprojectionNotSupportedError(ValueError):
    """Raised when stitching would require reprojection."""


def stitch_tiles(tiles: Sequence[RasterTile]) -> RasterTile:
    """Stitch tiles into a single raster while preserving metadata and band alignment.

    The transform is interpreted as (origin_x, origin_y, pixel_width, pixel_height)
    with x increasing to the right and y increasing downward.
    """

    if not tiles:
        raise ValueError("No tiles supplied for stitching.")

    reference = tiles[0]
    _validate_tile(reference)

    pixel_width = reference.transform[2]
    pixel_height = reference.transform[3]
    if pixel_width == 0 or pixel_height == 0:
        raise ValueError("Pixel size must be non-zero.")

    band_names = reference.band_names
    band_count = reference.band_count

    for tile in tiles[1:]:
        _validate_tile(tile)
        if tile.transform[2] != pixel_width or tile.transform[3] != pixel_height:
            raise ValueError("All tiles must share the same pixel size.")
        if tile.crs != reference.crs:
            raise ValueError("All tiles must share the same CRS.")
        if tile.band_count != band_count:
            raise ValueError("All tiles must share the same band count.")
        if band_names is not None and tile.band_names is not None and tile.band_names != band_names:
            raise ValueError("Band names must match across tiles.")
        if band_names is None and tile.band_names is not None:
            band_names = tile.band_names

    min_x = min(tile.transform[0] for tile in tiles)
    min_y = min(tile.transform[1] for tile in tiles)
    max_x = max(tile.transform[0] + tile.width * pixel_width for tile in tiles)
    max_y = max(tile.transform[1] + tile.height * pixel_height for tile in tiles)

    width = _extent_to_pixels(min_x, max_x, pixel_width)
    height = _extent_to_pixels(min_y, max_y, pixel_height)

    fill_value = reference.nodata if reference.nodata is not None else 0.0
    stitched_bands: list[list[list[float]]] = [
        [[fill_value for _ in range(width)] for _ in range(height)] for _ in range(band_count)
    ]

    for tile in tiles:
        offset_x = _offset_to_pixels(min_x, tile.transform[0], pixel_width)
        offset_y = _offset_to_pixels(min_y, tile.transform[1], pixel_height)
        _blit_tile(tile, stitched_bands, offset_x, offset_y, fill_value)

    return RasterTile(
        bands=stitched_bands,
        transform=(min_x, min_y, pixel_width, pixel_height),
        crs=reference.crs,
        band_names=band_names,
        nodata=reference.nodata,
    )


def stitch_rasters(paths: Sequence[str], output_path: str, *, cli_fallback: bool = True) -> str:
    """Stitch raster files on disk using Rasterio, with optional GDAL CLI fallback."""

    if not paths:
        raise ValueError("No input rasters provided for stitching.")

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        return _stitch_with_rasterio(paths, str(output))
    except Exception as exc:
        if isinstance(exc, ReprojectionNotSupportedError) or not cli_fallback:
            raise
        return _stitch_with_gdal(paths, str(output), exc)


def _validate_tile(tile: RasterTile) -> None:
    if tile.band_count == 0:
        raise ValueError("Tile must contain at least one band.")
    width = tile.width
    height = tile.height
    if width == 0 or height == 0:
        raise ValueError("Tile bands must be non-empty.")
    for band in tile.bands:
        if len(band) != height:
            raise ValueError("All bands in a tile must share the same height.")
        for row in band:
            if len(row) != width:
                raise ValueError("All rows in a band must share the same width.")
    if tile.band_names is not None and len(tile.band_names) != tile.band_count:
        raise ValueError("Band names length must match band count.")


def _extent_to_pixels(start: float, end: float, pixel_size: float) -> int:
    span = (end - start) / pixel_size
    rounded = round(span)
    if abs(span - rounded) > 1e-6:
        raise ValueError("Tile extents do not align to the pixel grid.")
    return int(rounded)


def _offset_to_pixels(origin: float, value: float, pixel_size: float) -> int:
    offset = (value - origin) / pixel_size
    rounded = round(offset)
    if abs(offset - rounded) > 1e-6:
        raise ValueError("Tile offsets do not align to the pixel grid.")
    return int(rounded)


def _blit_tile(
    tile: RasterTile,
    stitched: list[list[list[float]]],
    offset_x: int,
    offset_y: int,
    fill_value: float,
) -> None:
    for band_index, band in enumerate(tile.bands):
        target_band = stitched[band_index]
        for row_index, row in enumerate(band):
            target_row = target_band[offset_y + row_index]
            for col_index, value in enumerate(row):
                target_col = offset_x + col_index
                existing = target_row[target_col]
                if existing != fill_value and existing != value:
                    raise ValueError("Overlapping tiles contain conflicting values.")
                target_row[target_col] = value


def _stitch_with_rasterio(paths: Sequence[str], output_path: str) -> str:
    try:
        import rasterio
        from rasterio.merge import merge
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("Rasterio is required for stitching.") from exc

    from contextlib import ExitStack

    with ExitStack() as stack:
        datasets = [stack.enter_context(rasterio.open(path)) for path in paths]
        reference_crs = datasets[0].crs
        if any(dataset.crs != reference_crs for dataset in datasets[1:]):
            raise ReprojectionNotSupportedError(
                "Reprojection is not supported in v1; all input rasters must share the same CRS."
            )
        band_count = getattr(datasets[0], "count", 0)
        if band_count <= 0:
            raise ValueError("Input rasters must contain at least one band.")
        for dataset in datasets[1:]:
            if dataset.count != band_count:
                raise ValueError("All tiles must share the same band count.")
        band_descriptions = _resolve_band_descriptions(datasets, band_count)
        nodata_value = _resolve_nodata_value(datasets)
        mosaic, out_transform = merge(datasets)
        out_meta = datasets[0].meta.copy()
        out_meta.update(
            {
                "height": mosaic.shape[1],
                "width": mosaic.shape[2],
                "transform": out_transform,
            }
        )
        if nodata_value is not None:
            out_meta["nodata"] = nodata_value

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(mosaic)
            if band_descriptions and any(band_descriptions):
                dest.descriptions = band_descriptions
            _copy_rasterio_metadata(datasets[0], dest)

    return output_path


def _stitch_with_gdal(paths: Sequence[str], output_path: str, rasterio_error: Exception) -> str:
    with tempfile.TemporaryDirectory() as temp_dir:
        vrt_path = str(Path(temp_dir) / "mosaic.vrt")
        _run_gdal_command(["gdalbuildvrt", vrt_path, *paths], rasterio_error)
        _run_gdal_command(["gdal_translate", vrt_path, output_path], rasterio_error)
    return output_path


def _run_gdal_command(command: list[str], rasterio_error: Exception) -> None:
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        message = (
            "Rasterio stitching failed and GDAL CLI fallback failed. "
            f"Rasterio error: {rasterio_error!r}. "
            f"GDAL error: {exc!r}."
        )
        raise RuntimeError(message) from exc


def _copy_rasterio_metadata(source: object, dest: object) -> None:
    try:
        dest.update_tags(**source.tags())
    except Exception:  # pragma: no cover - rasterio metadata guard
        return

    for namespace in _tag_namespaces(source):
        try:
            tags = source.tags(ns=namespace)
        except Exception:  # pragma: no cover - rasterio metadata guard
            continue
        if tags:
            dest.update_tags(ns=namespace, **tags)

    source_count = getattr(source, "count", 0)
    for band_index in range(1, source_count + 1):
        try:
            band_tags = source.tags(bidx=band_index)
        except Exception:  # pragma: no cover - rasterio metadata guard
            band_tags = {}
        if band_tags:
            dest.update_tags(bidx=band_index, **band_tags)
        for namespace in _tag_namespaces(source, band_index):
            try:
                tags = source.tags(ns=namespace, bidx=band_index)
            except Exception:  # pragma: no cover - rasterio metadata guard
                continue
            if tags:
                dest.update_tags(bidx=band_index, ns=namespace, **tags)

    for attr_name in ("colorinterp", "scales", "offsets", "units"):
        try:
            value = getattr(source, attr_name)
        except Exception:  # pragma: no cover - rasterio metadata guard
            continue
        if value:
            try:
                setattr(dest, attr_name, value)
            except Exception:  # pragma: no cover - rasterio metadata guard
                continue


def _resolve_band_descriptions(
    datasets: Sequence[object], band_count: int
) -> tuple[str | None, ...] | None:
    descriptions: tuple[str | None, ...] | None = None
    for dataset in datasets:
        raw = getattr(dataset, "descriptions", None)
        if not raw:
            continue
        if len(raw) != band_count:
            raise ValueError("Band descriptions length must match band count.")
        if any(raw):
            current = tuple(raw)
            if descriptions is None:
                descriptions = current
            elif current != descriptions:
                raise ValueError("Band descriptions must match across tiles.")
    return descriptions


def _resolve_nodata_value(datasets: Sequence[object]) -> float | None:
    nodata_value: float | None = None
    for dataset in datasets:
        value = getattr(dataset, "nodata", None)
        if value is None:
            continue
        if nodata_value is None:
            nodata_value = value
        elif value != nodata_value:
            raise ValueError("All tiles must share the same nodata value.")
    return nodata_value


def _tag_namespaces(source: object, band_index: int | None = None) -> tuple[str, ...]:
    namespaces_fn = getattr(source, "tag_namespaces", None)
    if namespaces_fn is None:
        return ()
    try:
        if band_index is None:
            namespaces = namespaces_fn()
        else:
            namespaces = namespaces_fn(bidx=band_index)
    except Exception:  # pragma: no cover - rasterio metadata guard
        return ()
    if not namespaces:
        return ()
    return tuple(ns for ns in namespaces if ns)
