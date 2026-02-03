"""Rule-based model recommendation engine."""

from __future__ import annotations

from dataclasses import dataclass

from scripts.hardware_targets import get_hardware_targets


@dataclass(frozen=True)
class SceneMetadata:
    provider: str | None
    band_count: int
    resolution_m: float | None
    is_cloud_imagery: bool = False


@dataclass(frozen=True)
class HardwareProfile:
    gpu_available: bool
    vram_gb: int
    ram_gb: int


@dataclass(frozen=True)
class ModelRecommendation:
    model: str
    scale: int
    tiling: bool
    precision: str
    warnings: tuple[str, ...]
    reason: str


_MODEL_CAPABILITIES = {
    "Real-ESRGAN": {"gpu_required": False, "cpu_supported": True},
    "Satlas": {"gpu_required": False, "cpu_supported": True},
    "SwinIR": {"gpu_required": False, "cpu_supported": True},
    "SRGAN adapted to EO": {"gpu_required": False, "cpu_supported": True},
    "SatelliteSR": {"gpu_required": False, "cpu_supported": True},
    "SEN2SR": {"gpu_required": False, "cpu_supported": True},
    "S2DR3": {"gpu_required": False, "cpu_supported": True},
    "DSen2": {"gpu_required": False, "cpu_supported": True},
    "LDSR-S2": {"gpu_required": False, "cpu_supported": True},
    "SenGLEAN": {"gpu_required": True, "cpu_supported": False},
    "Swin2-MoSE": {"gpu_required": True, "cpu_supported": False},
    "MRDAM": {"gpu_required": False, "cpu_supported": True},
}

_MODEL_SCALES = {
    "Real-ESRGAN": (2, 4),
    "Satlas": (4,),
    "SwinIR": (2, 4),
    "SRGAN adapted to EO": (2, 4),
    "SatelliteSR": (2, 4),
    "SEN2SR": (2,),
    "S2DR3": (2, 4),
    "DSen2": (2,),
    "LDSR-S2": (2,),
    "SenGLEAN": (2, 4),
    "Swin2-MoSE": (2, 4),
    "MRDAM": (2, 4),
}

_PROVIDER_MODEL_PRIORITY = {
    "Sentinel-2": {
        "multispectral": ("S2DR3", "SEN2SR"),
        "RGB": ("Satlas",),
    },
    "PlanetScope": {
        "multispectral": ("SRGAN adapted to EO", "SatelliteSR"),
        "RGB": ("SwinIR", "Real-ESRGAN"),
    },
    "Landsat": {
        "multispectral": ("SRGAN adapted to EO",),
        "RGB": ("SwinIR", "Real-ESRGAN"),
    },
    "Vantor": {
        "multispectral": ("SRGAN adapted to EO", "SatelliteSR"),
        "RGB": ("SatelliteSR", "SRGAN adapted to EO"),
    },
    "21AT": {
        "multispectral": ("SRGAN adapted to EO", "SatelliteSR"),
        "RGB": ("SatelliteSR", "SRGAN adapted to EO"),
    },
}


def recommend_model(scene: SceneMetadata, hardware: HardwareProfile) -> ModelRecommendation:
    """Return a rule-based model recommendation."""

    if scene.band_count <= 0:
        raise ValueError("band_count must be positive")

    band_profile = _band_profile(scene.band_count)
    warnings: list[str] = []
    model = _select_base_model(scene, band_profile)

    if scene.provider == "Landsat" and band_profile == "multispectral":
        warnings.append("Landsat multispectral SR is experimental; validate outputs carefully.")

    model = _enforce_hardware_constraints(model, band_profile, hardware, warnings)
    scale = _select_scale(scene.resolution_m, model)
    tiling = _should_tile(hardware)
    precision = _select_precision(hardware)

    if scene.resolution_m is not None and scene.resolution_m <= 0.5:
        warnings.append("Input appears high resolution; consider scale 2 or no upscale.")

    reason = _build_reason(scene, band_profile, model)
    return ModelRecommendation(
        model=model,
        scale=scale,
        tiling=tiling,
        precision=precision,
        warnings=tuple(warnings),
        reason=reason,
    )


def _band_profile(band_count: int) -> str:
    return "RGB" if band_count <= 3 else "multispectral"


def _select_base_model(scene: SceneMetadata, band_profile: str) -> str:
    if scene.is_cloud_imagery:
        return "MRDAM"

    provider = scene.provider
    if provider in _PROVIDER_MODEL_PRIORITY:
        candidates = _PROVIDER_MODEL_PRIORITY[provider][band_profile]
        return _select_first_candidate(candidates, band_profile)
    return "SRGAN adapted to EO" if band_profile == "multispectral" else "Real-ESRGAN"


def _select_first_candidate(candidates: tuple[str, ...], band_profile: str) -> str:
    for model in candidates:
        if model:
            return model
    return "SRGAN adapted to EO" if band_profile == "multispectral" else "Real-ESRGAN"


def _enforce_hardware_constraints(
    model: str,
    band_profile: str,
    hardware: HardwareProfile,
    warnings: list[str],
) -> str:
    capabilities = _MODEL_CAPABILITIES.get(model, {"gpu_required": False, "cpu_supported": True})
    if capabilities.get("gpu_required") and not hardware.gpu_available:
        fallback = "Real-ESRGAN" if band_profile == "RGB" else "SRGAN adapted to EO"
        warnings.append(f"{model} requires GPU acceleration; falling back to {fallback}.")
        model = fallback

    targets = get_hardware_targets()
    if not hardware.gpu_available:
        warnings.append("GPU not detected; using CPU fallback.")
    if hardware.vram_gb < targets.minimum_vram_gb:
        warnings.append("VRAM below minimum target; tiling enabled for stability.")
    if hardware.ram_gb < targets.minimum_ram_gb:
        warnings.append("System RAM below minimum target; tiling enabled for stability.")
    return model


def _select_scale(resolution_m: float | None, model: str) -> int:
    preferred = _preferred_scale(resolution_m)
    scales = _MODEL_SCALES.get(model, (2, 4))
    if preferred in scales:
        return preferred
    for scale in sorted(scales):
        if scale >= preferred:
            return scale
    return max(scales)


def _preferred_scale(resolution_m: float | None) -> int:
    if resolution_m is None:
        return 4
    if resolution_m <= 1.5:
        return 2
    return 4


def _should_tile(hardware: HardwareProfile) -> bool:
    targets = get_hardware_targets()
    if not hardware.gpu_available:
        return True
    if hardware.vram_gb < targets.minimum_vram_gb:
        return True
    if hardware.ram_gb < targets.minimum_ram_gb:
        return True
    return False


def _select_precision(hardware: HardwareProfile) -> str:
    targets = get_hardware_targets()
    if hardware.gpu_available and hardware.vram_gb >= targets.minimum_vram_gb:
        return "fp16"
    return "fp32"


def _build_reason(scene: SceneMetadata, band_profile: str, model: str) -> str:
    provider = scene.provider or "Unknown provider"
    resolution = (
        "resolution unknown"
        if scene.resolution_m is None
        else f"{scene.resolution_m:.2f}m GSD"
    )
    return f"{provider} {band_profile} scene at {resolution}; mapped to {model}."
