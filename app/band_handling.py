from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BandHandling(str, Enum):
    RGB_ONLY = "RGB only"
    RGB_PLUS_ALL = "RGB + all bands"
    ALL_BANDS = "All bands"

    @classmethod
    def labels(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def from_label(cls, label: str) -> "BandHandling":
        for member in cls:
            if member.value == label:
                return member
        raise ValueError(f"Unknown band handling label: {label}")


@dataclass(frozen=True)
class ExportSettings:
    band_handling: BandHandling
    output_format: str
