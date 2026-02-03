"""Hardware target definitions for the desktop SR app."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CpuFallbackExpectations:
    """Document how the app behaves when GPU acceleration is unavailable."""

    validated_models: Tuple[str, ...]
    notes: Tuple[str, ...]


@dataclass(frozen=True)
class HardwareTargets:
    """Minimum hardware targets for local SR processing."""

    minimum_ram_gb: int
    minimum_vram_gb: int
    cpu_fallback: CpuFallbackExpectations


_CPU_FALLBACK_EXPECTATIONS = CpuFallbackExpectations(
    validated_models=(
        "Real-ESRGAN",
        "SwinIR",
        "SRGAN adapted to EO",
        "SatelliteSR",
        "MRDAM",
    ),
    notes=(
        "CPU mode is available when CUDA is not detected or a user forces CPU.",
        "CPU processing is significantly slower than GPU and may require tiling for large images.",
        "Safe mode defaults to conservative settings to keep memory use stable on CPU.",
    ),
)

_HARDWARE_TARGETS = HardwareTargets(
    minimum_ram_gb=16,
    minimum_vram_gb=6,
    cpu_fallback=_CPU_FALLBACK_EXPECTATIONS,
)


def get_hardware_targets() -> HardwareTargets:
    """Return the minimum hardware targets and CPU fallback expectations."""
    return _HARDWARE_TARGETS
