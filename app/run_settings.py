from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunSettings:
    scale: int | None
    tiling: str | None
    precision: str | None
    compute: str | None
    seam_blend: bool
    safe_mode: bool


def parse_scale(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    digits = "".join(ch for ch in normalized if ch.isdigit())
    return int(digits) if digits else None


def parse_tiling(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "auto":
        return None
    return normalized


def parse_precision(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "auto":
        return None
    return normalized.upper()


def parse_compute(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized or normalized.lower() == "auto":
        return None
    return normalized.upper()
