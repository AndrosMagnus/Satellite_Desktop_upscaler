"""Dry-run estimator for runtime and VRAM usage."""

from __future__ import annotations

from dataclasses import dataclass

from app.recommendation import HardwareProfile


@dataclass(frozen=True)
class DryRunEstimate:
    runtime_seconds: float
    vram_gb: float
    notes: tuple[str, ...]


_MODEL_RUNTIME_MULTIPLIER = {
    "Real-ESRGAN": 1.0,
    "Satlas": 0.9,
    "SwinIR": 1.1,
    "SRGAN adapted to EO": 1.2,
    "SatelliteSR": 1.15,
    "SEN2SR": 1.1,
    "S2DR3": 1.25,
    "DSen2": 1.3,
    "LDSR-S2": 1.2,
    "SenGLEAN": 1.4,
    "Swin2-MoSE": 1.35,
    "MRDAM": 1.05,
}

_MODEL_VRAM_OVERHEAD_GB = {
    "Real-ESRGAN": 0.6,
    "Satlas": 0.7,
    "SwinIR": 0.8,
    "SRGAN adapted to EO": 0.9,
    "SatelliteSR": 0.9,
    "SEN2SR": 1.0,
    "S2DR3": 1.2,
    "DSen2": 1.1,
    "LDSR-S2": 1.0,
    "SenGLEAN": 1.4,
    "Swin2-MoSE": 1.3,
    "MRDAM": 0.8,
}

_BASE_GPU_SECONDS_PER_MP = 0.06
_BASE_CPU_SECONDS_PER_MP = 0.35
_TILE_SIZE = 512


def estimate_dry_run(
    width: int,
    height: int,
    band_count: int,
    scale: int,
    model: str,
    precision: str,
    tiling: bool,
    hardware: HardwareProfile,
) -> DryRunEstimate:
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if band_count <= 0:
        raise ValueError("band_count must be positive")
    if scale <= 0:
        raise ValueError("scale must be positive")

    notes: list[str] = []
    precision_normalized = precision.lower().strip()
    if precision_normalized not in {"fp16", "fp32"}:
        notes.append("Precision override invalid; using fp32 for estimates.")
        precision_normalized = "fp32"

    bytes_per_value = 2 if precision_normalized == "fp16" else 4
    band_factor = max(1.0, band_count / 3.0)
    scale_factor = scale**2

    runtime_multiplier = _MODEL_RUNTIME_MULTIPLIER.get(model, 1.0)
    base_seconds = (
        _BASE_GPU_SECONDS_PER_MP if hardware.gpu_available else _BASE_CPU_SECONDS_PER_MP
    )
    precision_factor = 0.85 if (precision_normalized == "fp16" and hardware.gpu_available) else 1.0
    tiling_factor = 1.25 if tiling else 1.0

    megapixels = (width * height) / 1_000_000
    runtime_seconds = (
        base_seconds
        * megapixels
        * scale_factor
        * band_factor
        * runtime_multiplier
        * tiling_factor
        * precision_factor
    )
    runtime_seconds = max(1.0, runtime_seconds + 2.0)

    if not hardware.gpu_available:
        notes.append("GPU not detected; VRAM estimate set to 0 GB.")
        return DryRunEstimate(
            runtime_seconds=runtime_seconds,
            vram_gb=0.0,
            notes=tuple(notes),
        )

    if tiling:
        tile_width = min(width, _TILE_SIZE)
        tile_height = min(height, _TILE_SIZE)
    else:
        tile_width = width
        tile_height = height

    input_bytes = tile_width * tile_height * band_count * bytes_per_value
    output_bytes = tile_width * tile_height * scale_factor * band_count * bytes_per_value
    activation_multiplier = 1.8
    overhead_gb = _MODEL_VRAM_OVERHEAD_GB.get(model, 0.8)
    if band_count > 3:
        overhead_gb += 0.2

    vram_bytes = (input_bytes + output_bytes) * activation_multiplier
    vram_gb = vram_bytes / (1024**3) + overhead_gb
    if vram_gb > hardware.vram_gb:
        notes.append("Estimated VRAM exceeds available GPU memory.")

    return DryRunEstimate(
        runtime_seconds=runtime_seconds,
        vram_gb=vram_gb,
        notes=tuple(notes),
    )
