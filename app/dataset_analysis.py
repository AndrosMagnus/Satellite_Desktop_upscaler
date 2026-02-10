from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re

from app.imagery_policy import infer_sensor_name
from app.output_metadata import format_preserves_metadata
from app.provider_detection import recommend_provider


@dataclass(frozen=True)
class GridSignature:
    crs: str
    transform: tuple[float, float, float, float, float, float]
    width: int
    height: int


@dataclass(frozen=True)
class DatasetInfo:
    path: Path
    provider: str | None
    sensor: str | None
    format_label: str | None
    band_count: int | None
    grid: GridSignature | None
    dtype: str | None
    nodata: float | None
    scales: tuple[float, ...] | None
    offsets: tuple[float, ...] | None
    band_names: tuple[str, ...] | None
    acquisition_time: str | None = None
    scene_id: str | None = None

    @property
    def is_geospatial(self) -> bool:
        return format_preserves_metadata(self.format_label)

    def preservation_gaps(self) -> tuple[str, ...]:
        if not self.is_geospatial:
            return ()
        gaps: list[str] = []
        if self.grid is None:
            gaps.extend(["CRS", "geotransform"])
        if self.band_count is None:
            gaps.append("band_count")
        if self.dtype is None:
            gaps.append("dtype")
        if self.scales is None:
            gaps.append("scales")
        if self.offsets is None:
            gaps.append("offsets")
        if self.band_names is None:
            gaps.append("band_names")
        return tuple(gaps)


def analyze_dataset(path: str | Path) -> DatasetInfo:
    path_obj = Path(path)
    recommendation = recommend_provider(str(path_obj))
    provider = recommendation.best
    sensor = infer_sensor_name(str(path_obj), provider)
    raster_tags: dict[str, str] = {}

    format_label = None
    band_count: int | None = None
    grid: GridSignature | None = None
    dtype: str | None = None
    nodata: float | None = None
    scales: tuple[float, ...] | None = None
    offsets: tuple[float, ...] | None = None
    band_names: tuple[str, ...] | None = None

    try:
        from app.metadata import extract_image_header_info

        header = extract_image_header_info(str(path_obj))
        if header is not None:
            format_label = header.format
    except Exception:  # noqa: BLE001
        format_label = None

    try:
        import rasterio

        with rasterio.open(path_obj) as src:
            band_count = int(src.count) if src.count else None
            crs_obj = src.crs
            if crs_obj is not None:
                crs = crs_obj.to_string() or str(crs_obj)
                transform = src.transform
                grid = GridSignature(
                    crs=crs,
                    transform=(
                        float(transform.a),
                        float(transform.b),
                        float(transform.c),
                        float(transform.d),
                        float(transform.e),
                        float(transform.f),
                    ),
                    width=int(src.width),
                    height=int(src.height),
                )
            if src.dtypes:
                dtype = str(src.dtypes[0])
            nodata = src.nodata
            try:
                if src.scales:
                    scales = tuple(float(value) for value in src.scales)
            except Exception:  # noqa: BLE001
                scales = None
            try:
                if src.offsets:
                    offsets = tuple(float(value) for value in src.offsets)
            except Exception:  # noqa: BLE001
                offsets = None
            if src.descriptions and any(src.descriptions):
                band_names = tuple(str(value) if value else "" for value in src.descriptions)
            raster_tags = _read_raster_tags(src)
            if format_label is None:
                driver = src.driver or ""
                if driver.upper() in {"GTIFF", "COG"}:
                    format_label = "GeoTIFF"
                elif driver.upper() in {"JP2OPENJPEG", "JPEG2000", "JP2KAK"}:
                    format_label = "JP2"
    except Exception:  # noqa: BLE001
        pass

    if band_count is None:
        band_count = _infer_band_count_with_pillow(path_obj)
    acquisition_time = infer_acquisition_time(path_obj, tags=raster_tags)
    scene_id = infer_scene_id(path_obj, provider=provider, tags=raster_tags)

    return DatasetInfo(
        path=path_obj,
        provider=provider,
        sensor=sensor,
        acquisition_time=acquisition_time,
        scene_id=scene_id,
        format_label=format_label,
        band_count=band_count,
        grid=grid,
        dtype=dtype,
        nodata=nodata,
        scales=scales,
        offsets=offsets,
        band_names=band_names,
    )


def group_by_grid(infos: list[DatasetInfo]) -> dict[GridSignature, list[DatasetInfo]]:
    grouped: dict[GridSignature, list[DatasetInfo]] = {}
    for info in infos:
        if info.grid is None:
            continue
        grouped.setdefault(info.grid, []).append(info)
    return grouped


def summarize_grid_groups(groups: dict[GridSignature, list[DatasetInfo]]) -> str:
    if not groups:
        return "No geospatial grid groups detected."
    lines: list[str] = []
    for index, (grid, members) in enumerate(groups.items(), start=1):
        names = ", ".join(item.path.name for item in members[:3])
        if len(members) > 3:
            names = f"{names}, +{len(members) - 3} more"
        lines.append(
            f"Group {index}: CRS={grid.crs}, transform={_format_transform(grid.transform)}, files={len(members)} ({names})"
        )
    return "\n".join(lines)


def _infer_band_count_with_pillow(path: Path) -> int | None:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return len(image.getbands())
    except Exception:  # noqa: BLE001
        return None


def _format_transform(transform: tuple[float, float, float, float, float, float]) -> str:
    return (
        f"({transform[0]:.6f},{transform[1]:.6f},{transform[2]:.6f},"
        f"{transform[3]:.6f},{transform[4]:.6f},{transform[5]:.6f})"
    )


_ACQUISITION_TAG_KEYS = (
    "ACQUISITION_TIME",
    "ACQUISITION_DATETIME",
    "SENSING_TIME",
    "DATE_ACQUIRED",
    "DATETIME",
    "TIFFTAG_DATETIME",
    "PRODUCT_START_TIME",
)

_SCENE_ID_TAG_KEYS = (
    "SCENE_ID",
    "SCENEID",
    "LANDSAT_SCENE_ID",
    "LANDSAT_PRODUCT_ID",
    "PRODUCT_ID",
    "PRODUCTID",
    "GRANULE_ID",
    "IDENTIFIER",
)

_TIFF_DATETIME_RE = re.compile(
    r"^(\d{4}):(\d{2}):(\d{2})[ T](\d{2}):(\d{2}):(\d{2})$"
)
_ISO_DATETIME_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:([+-]\d{2}:?\d{2}|Z))?$"
)
_COMPACT_DATETIME_RE = re.compile(
    r"^(\d{4})(\d{2})(\d{2})[T_]?(\d{2})(\d{2})(\d{2})(Z)?$",
    re.IGNORECASE,
)
_ISO_DATE_RE = re.compile(r"^(\d{4})[:\-](\d{2})[:\-](\d{2})$")
_COMPACT_DATE_RE = re.compile(r"^(\d{4})(\d{2})(\d{2})$")

_FILENAME_DATETIME_PATTERNS = (
    re.compile(
        r"(?<!\d)(20\d{2})(\d{2})(\d{2})[T_](\d{2})(\d{2})(\d{2})(Z)?(?!\d)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})[T_](\d{2})[-_]?(\d{2})[-_]?(\d{2})(Z)?(?!\d)",
        re.IGNORECASE,
    ),
)

_FILENAME_DATE_PATTERNS = (
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)"),
    re.compile(r"(?<!\d)(20\d{2})[-_](\d{2})[-_](\d{2})(?!\d)"),
)

_SENTINEL_SCENE_RE = re.compile(
    r"(S2[AB]_[A-Z0-9]{4,}_[0-9]{8}T[0-9]{6}_[A-Z0-9]{3,}_[A-Z0-9]{4}_[A-Z0-9]{5}_[0-9]{8}T[0-9]{6})",
    re.IGNORECASE,
)
_LANDSAT_SCENE_RE = re.compile(r"(L[COTEM]\d{2}_[A-Z0-9_]{20,})", re.IGNORECASE)
_PLANETSCOPE_SCENE_RE = re.compile(
    r"(\d{8}_\d{6}_\d{2}_[0-9A-Z]{2,4}(?:_[A-Z0-9]+){0,4})",
    re.IGNORECASE,
)

_SCENE_SUFFIX_PATTERNS = (
    re.compile(r"[_\-]B\d{1,2}A?$", re.IGNORECASE),
    re.compile(r"[_\-]TCI$", re.IGNORECASE),
    re.compile(r"[_\-]VISUAL$", re.IGNORECASE),
    re.compile(r"[_\-]ANALYTIC(?:MS)?$", re.IGNORECASE),
    re.compile(r"[_\-]UDM2?$", re.IGNORECASE),
    re.compile(r"[_\-]R\d+[_\-]C\d+$", re.IGNORECASE),
    re.compile(r"[_\-]X\d+[_\-]Y\d+$", re.IGNORECASE),
)


def infer_acquisition_time(
    path: str | Path,
    *,
    tags: Mapping[str, object] | None = None,
) -> str | None:
    from_tags = _lookup_tag_value(tags, _ACQUISITION_TAG_KEYS)
    if from_tags:
        normalized = _normalize_acquisition_time(from_tags)
        if normalized:
            return normalized
    return _infer_acquisition_time_from_filename(Path(path).stem)


def infer_scene_id(
    path: str | Path,
    *,
    provider: str | None = None,
    tags: Mapping[str, object] | None = None,
) -> str | None:
    from_tags = _lookup_tag_value(tags, _SCENE_ID_TAG_KEYS)
    if from_tags:
        return _normalize_scene_id(from_tags)
    return _infer_scene_id_from_filename(Path(path).stem, provider)


def _read_raster_tags(source: object) -> dict[str, str]:
    tag_reader = getattr(source, "tags", None)
    if not callable(tag_reader):
        return {}
    collected: dict[str, str] = {}
    _merge_tags(collected, _safe_read_tags(tag_reader))
    namespace_reader = getattr(source, "tag_namespaces", None)
    if callable(namespace_reader):
        try:
            namespaces = namespace_reader()
        except Exception:  # noqa: BLE001
            namespaces = []
        for namespace in namespaces:
            _merge_tags(collected, _safe_read_tags(tag_reader, namespace))
    return collected


def _safe_read_tags(tag_reader: object, namespace: str | None = None) -> Mapping[object, object]:
    if not callable(tag_reader):
        return {}
    try:
        if namespace is None:
            payload = tag_reader()
        else:
            payload = tag_reader(ns=namespace)
    except Exception:  # noqa: BLE001
        return {}
    if isinstance(payload, Mapping):
        return payload
    return {}


def _merge_tags(dest: dict[str, str], source: Mapping[object, object]) -> None:
    for raw_key, raw_value in source.items():
        key = str(raw_key).strip()
        value = str(raw_value).strip()
        if key and value:
            dest[key] = value


def _lookup_tag_value(
    tags: Mapping[str, object] | None,
    candidates: tuple[str, ...],
) -> str | None:
    if not tags:
        return None
    lookup: dict[str, str] = {}
    for raw_key, raw_value in tags.items():
        key = str(raw_key).strip().lower()
        value = str(raw_value).strip()
        if key and value:
            lookup[key] = value
    for candidate in candidates:
        value = lookup.get(candidate.lower())
        if value:
            return value
    return None


def _normalize_acquisition_time(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    value = value.replace("/", "-")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+UTC$", "Z", value, flags=re.IGNORECASE)

    match = _TIFF_DATETIME_RE.fullmatch(value)
    if match:
        return (
            f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            f"T{match.group(4)}:{match.group(5)}:{match.group(6)}"
        )
    match = _ISO_DATETIME_RE.fullmatch(value)
    if match:
        suffix = _normalize_timezone_suffix(match.group(7))
        return (
            f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            f"T{match.group(4)}:{match.group(5)}:{match.group(6)}{suffix}"
        )
    match = _COMPACT_DATETIME_RE.fullmatch(value)
    if match:
        suffix = "Z" if match.group(7) else ""
        return (
            f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            f"T{match.group(4)}:{match.group(5)}:{match.group(6)}{suffix}"
        )
    match = _ISO_DATE_RE.fullmatch(value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    match = _COMPACT_DATE_RE.fullmatch(value)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _normalize_timezone_suffix(value: str | None) -> str:
    if not value:
        return ""
    if value.upper() == "Z":
        return "Z"
    if re.fullmatch(r"[+-]\d{4}", value):
        return f"{value[:3]}:{value[3:]}"
    return value


def _infer_acquisition_time_from_filename(stem: str) -> str | None:
    for pattern in _FILENAME_DATETIME_PATTERNS:
        match = pattern.search(stem)
        if match:
            suffix = "Z" if match.group(7) else ""
            return (
                f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                f"T{match.group(4)}:{match.group(5)}:{match.group(6)}{suffix}"
            )
    for pattern in _FILENAME_DATE_PATTERNS:
        match = pattern.search(stem)
        if match:
            return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def _infer_scene_id_from_filename(stem: str, provider: str | None) -> str | None:
    cleaned = _strip_scene_suffixes(stem)
    provider_normalized = (provider or "").strip().lower()
    if provider_normalized == "sentinel-2":
        match = _SENTINEL_SCENE_RE.search(cleaned)
        if match:
            return match.group(1)
    if provider_normalized == "landsat":
        match = _LANDSAT_SCENE_RE.search(cleaned)
        if match:
            return match.group(1)
    if provider_normalized == "planetscope":
        match = _PLANETSCOPE_SCENE_RE.search(cleaned)
        if match:
            return match.group(1)
    for pattern in (_SENTINEL_SCENE_RE, _LANDSAT_SCENE_RE, _PLANETSCOPE_SCENE_RE):
        match = pattern.search(cleaned)
        if match:
            return match.group(1)
    if len(cleaned) >= 12 and "_" in cleaned and any(char.isdigit() for char in cleaned):
        return cleaned
    return None


def _strip_scene_suffixes(stem: str) -> str:
    current = stem
    for _ in range(4):
        previous = current
        for pattern in _SCENE_SUFFIX_PATTERNS:
            current = pattern.sub("", current)
        if current == previous:
            break
    return current.strip("_-")


def _normalize_scene_id(raw: str) -> str | None:
    value = raw.strip()
    if not value:
        return None
    if value.lower() in {"none", "unknown", "n/a"}:
        return None
    return value[:200]
