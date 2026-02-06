from __future__ import annotations

import re

_GEOSPATIAL_FORMATS = {
    "GEOTIFF",
    "TIFF",
    "TIF",
    "JP2",
    "JPEG2000",
}

_IGNORED_FORMATS = {
    "UNKNOWN",
    "NOT AN IMAGE",
}

_IGNORED_FORMAT_ALIASES = {
    "NOTANIMAGE",
}


def normalize_format_label(label: str | None) -> str | None:
    if not label:
        return None
    normalized = label.strip().upper()
    if not normalized:
        return None
    if normalized in _IGNORED_FORMATS:
        return None
    compact = re.sub(r"[\s_-]+", "", normalized)
    if compact in _IGNORED_FORMAT_ALIASES:
        return None
    if compact == "MATCHINPUT":
        return "MATCH INPUT"
    if compact == "JPG":
        return "JPEG"
    if compact == "J2K":
        return "JPEG2000"
    if compact == "GEOTIFF":
        return "GEOTIFF"
    if compact == "JPEG2000":
        return "JPEG2000"
    if compact == "JP2":
        return "JP2"
    if compact == "TIF":
        return "TIF"
    if compact == "TIFF":
        return "TIFF"
    return normalized


def format_preserves_metadata(label: str | None) -> bool:
    normalized = normalize_format_label(label)
    if normalized is None:
        return False
    return normalized in _GEOSPATIAL_FORMATS


def metadata_loss_warning(input_format: str | None, output_format: str) -> str | None:
    output_normalized = normalize_format_label(output_format)
    if output_normalized is None:
        return None
    if output_normalized == "MATCH INPUT":
        return None

    input_normalized = normalize_format_label(input_format)
    if input_normalized is None:
        return None

    if input_normalized in _GEOSPATIAL_FORMATS and output_normalized not in _GEOSPATIAL_FORMATS:
        return (
            f"Warning: {output_format} exports do not preserve geospatial metadata from "
            f"{input_format} sources."
        )
    return None
