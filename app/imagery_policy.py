from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.output_metadata import format_preserves_metadata, normalize_format_label


_GEOSPATIAL_VISUAL_SAFE_FALLBACK = "GeoTIFF"

_CANONICAL_FORMAT_LABELS = {
    "MATCH INPUT": "Match input",
    "GEOTIFF": "GeoTIFF",
    "TIFF": "TIFF",
    "TIF": "TIF",
    "JP2": "JP2",
    "JPEG2000": "JPEG2000",
    "PNG": "PNG",
    "JPEG": "JPEG",
}


@dataclass(frozen=True)
class OutputPlan:
    master_format: str
    visual_format: str | None
    critical_warnings: tuple[str, ...]


@dataclass(frozen=True)
class RgbBandMapping:
    red: int
    green: int
    blue: int
    source: str


def build_output_plan(
    input_format: str | None,
    requested_output_format: str,
) -> OutputPlan:
    requested = normalize_format_label(requested_output_format) or "MATCH INPUT"
    requested_label = _canonical_format(requested)
    input_normalized = normalize_format_label(input_format)
    input_label = _canonical_format(input_normalized) if input_normalized else None

    if requested == "MATCH INPUT":
        if input_label:
            return OutputPlan(master_format=input_label, visual_format=None, critical_warnings=())
        return OutputPlan(master_format=_GEOSPATIAL_VISUAL_SAFE_FALLBACK, visual_format=None, critical_warnings=())

    if (
        input_normalized is not None
        and format_preserves_metadata(input_normalized)
        and not format_preserves_metadata(requested)
    ):
        warning = (
            f"Critical warning: {requested_label} visual exports cannot preserve full "
            f"geospatial metadata from {input_label} inputs. A { _GEOSPATIAL_VISUAL_SAFE_FALLBACK } "
            "master output will also be produced."
        )
        return OutputPlan(
            master_format=_GEOSPATIAL_VISUAL_SAFE_FALLBACK,
            visual_format=requested_label,
            critical_warnings=(warning,),
        )

    return OutputPlan(master_format=requested_label, visual_format=None, critical_warnings=())


def default_rgb_mapping(provider: str | None, band_count: int) -> RgbBandMapping | None:
    if band_count <= 0:
        return None
    if band_count == 1:
        return RgbBandMapping(0, 0, 0, "single-band fallback")
    if band_count == 2:
        return RgbBandMapping(0, 1, 1, "two-band fallback")
    if band_count == 3:
        return RgbBandMapping(0, 1, 2, "identity RGB")

    normalized_provider = (provider or "").strip().lower()
    if normalized_provider == "sentinel-2" and band_count >= 4:
        return RgbBandMapping(3, 2, 1, "provider default Sentinel-2 B4/B3/B2")
    if normalized_provider == "planetscope" and band_count >= 4:
        return RgbBandMapping(2, 1, 0, "provider default PlanetScope R/G/B")
    if normalized_provider == "landsat" and band_count >= 4:
        return RgbBandMapping(3, 2, 1, "provider default Landsat B4/B3/B2")
    if normalized_provider in {"vantor", "21at"} and band_count >= 3:
        return RgbBandMapping(0, 1, 2, "provider default RGB-first")
    return None


def infer_sensor_name(path: str, provider: str | None) -> str | None:
    filename = Path(path).name.lower()
    if provider == "Sentinel-2":
        if "msil2a" in filename:
            return "MSI-L2A"
        if "msil1c" in filename:
            return "MSI-L1C"
        return "MSI"
    if provider == "PlanetScope":
        if "psscene" in filename or "analyticms" in filename:
            return "PSScene-4Band"
        return "PlanetScope"
    if provider == "Landsat":
        return "OLI/TIRS"
    return None


def load_model_band_support(
    registry_path: Path | None = None,
) -> dict[str, tuple[str, ...]]:
    if registry_path is None:
        registry_path = Path(__file__).resolve().parents[1] / "models" / "registry.json"
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, list):
        return {}

    support: dict[str, tuple[str, ...]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        bands_supported = entry.get("bands_supported")
        if not isinstance(name, str) or not isinstance(bands_supported, list):
            continue
        normalized = tuple(str(value) for value in bands_supported if isinstance(value, str))
        support[name] = normalized
    return support


def model_supports_dataset(
    model_name: str,
    provider: str | None,
    band_count: int | None,
    *,
    band_support: dict[str, tuple[str, ...]] | None = None,
) -> bool:
    if band_count is None or band_count <= 0:
        return True
    support = band_support or load_model_band_support()
    supported_bands = support.get(model_name)
    if not supported_bands:
        return False

    normalized = {value.strip().lower() for value in supported_bands}
    if band_count <= 3:
        return "rgb" in normalized

    if provider:
        provider_normalized = provider.strip().lower()
        if provider_normalized in normalized:
            return True
    if "all bands" in normalized or "multispectral" in normalized:
        return True
    return False


def _canonical_format(value: str | None) -> str:
    if value is None:
        return _GEOSPATIAL_VISUAL_SAFE_FALLBACK
    return _CANONICAL_FORMAT_LABELS.get(value, value)
