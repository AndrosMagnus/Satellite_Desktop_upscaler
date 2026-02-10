"""Rule-based model recommendation engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class ModelOverrides:
    model: str | None = None
    scale: int | None = None
    tiling: bool | None = None
    precision: str | None = None
    compute_mode: str | None = None
    safe_mode: bool = False


_MODEL_CAPABILITIES = {
    "Real-ESRGAN": {"gpu_required": False, "cpu_supported": True},
    "Satlas": {"gpu_required": False, "cpu_supported": True},
    "SwinIR": {"gpu_required": False, "cpu_supported": True},
    "Swin2SR": {"gpu_required": False, "cpu_supported": True},
    "HAT": {"gpu_required": False, "cpu_supported": True},
    "SRGAN adapted to EO": {"gpu_required": False, "cpu_supported": True},
    "SatelliteSR": {"gpu_required": False, "cpu_supported": True},
    "SEN2SR": {"gpu_required": False, "cpu_supported": True},
    "S2DR3": {"gpu_required": False, "cpu_supported": True},
    "DSen2": {"gpu_required": False, "cpu_supported": True},
    "LDSR-S2": {"gpu_required": False, "cpu_supported": True},
    "EVOLAND Sentinel-2 SR": {"gpu_required": False, "cpu_supported": True},
    "SenGLEAN": {"gpu_required": True, "cpu_supported": False},
    "Swin2-MoSE": {"gpu_required": True, "cpu_supported": False},
    "MRDAM": {"gpu_required": False, "cpu_supported": True},
}

_MODEL_SCALES = {
    "Real-ESRGAN": (2, 4),
    "Satlas": (4,),
    "SwinIR": (2, 4),
    "Swin2SR": (2, 4),
    "HAT": (2, 4),
    "SRGAN adapted to EO": (2, 4),
    "SatelliteSR": (2, 4),
    "SEN2SR": (2,),
    "S2DR3": (2, 4),
    "DSen2": (2,),
    "LDSR-S2": (2,),
    "EVOLAND Sentinel-2 SR": (2, 4),
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
        "multispectral": ("LDSR-S2", "SRGAN adapted to EO"),
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
    tiling = _select_tiling(model, hardware)
    precision = _select_precision(hardware, model)

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


def recommend_model_with_overrides(
    scene: SceneMetadata,
    hardware: HardwareProfile,
    overrides: ModelOverrides | None = None,
) -> ModelRecommendation:
    """Return a recommendation updated with user overrides and warnings."""

    compute_warnings: list[str] = []
    safe_mode = bool(overrides.safe_mode) if overrides else False
    compute_mode = "CPU" if safe_mode else (overrides.compute_mode if overrides else None)
    if compute_mode:
        hardware = _apply_compute_override(hardware, compute_mode, compute_warnings)
    recommendation = recommend_model(scene, hardware)
    if safe_mode and overrides and overrides.model:
        recommendation = apply_overrides(
            recommendation, ModelOverrides(model=overrides.model, safe_mode=True)
        )
    if safe_mode:
        recommendation = _apply_safe_mode_defaults(recommendation)
    if compute_warnings:
        recommendation = ModelRecommendation(
            model=recommendation.model,
            scale=recommendation.scale,
            tiling=recommendation.tiling,
            precision=recommendation.precision,
            warnings=tuple((*recommendation.warnings, *compute_warnings)),
            reason=recommendation.reason,
        )
    if overrides is None or safe_mode:
        return recommendation
    return apply_overrides(recommendation, overrides)


def apply_overrides(
    recommendation: ModelRecommendation, overrides: ModelOverrides
) -> ModelRecommendation:
    """Apply user overrides and add warnings when they differ from recommendations."""

    warnings = list(recommendation.warnings)
    model = recommendation.model
    scale = recommendation.scale
    tiling = recommendation.tiling
    precision = recommendation.precision

    if overrides.model and overrides.model != model:
        warnings.append(
            f"Selected model '{overrides.model}' overrides recommended model '{model}'."
        )
        model = overrides.model

    if overrides.scale is not None and overrides.scale != scale:
        supported_scales = _MODEL_SCALES.get(model, ())
        if supported_scales and overrides.scale not in supported_scales:
            warnings.append(
                f"Scale {overrides.scale}x is not supported by {model}; keeping "
                f"recommended {scale}x."
            )
        else:
            warnings.append(f"Scale {overrides.scale}x overrides recommended {scale}x.")
            scale = overrides.scale

    if overrides.tiling is not None and overrides.tiling != tiling:
        enabled_text = "enabled" if tiling else "disabled"
        override_text = "enabled" if overrides.tiling else "disabled"
        warnings.append(
            f"Tiling override set to {override_text}; recommended is {enabled_text}."
        )
        tiling = overrides.tiling

    if overrides.precision and overrides.precision.lower() != precision.lower():
        normalized = overrides.precision.lower()
        if normalized not in {"fp16", "fp32"}:
            warnings.append(
                f"Precision override '{overrides.precision}' is invalid; keeping {precision}."
            )
        else:
            warnings.append(
                f"Precision override {normalized} replaces recommended {precision}."
            )
            precision = normalized

    return ModelRecommendation(
        model=model,
        scale=scale,
        tiling=tiling,
        precision=precision,
        warnings=tuple(warnings),
        reason=recommendation.reason,
    )


def _apply_compute_override(
    hardware: HardwareProfile, compute_mode: str, warnings: list[str]
) -> HardwareProfile:
    normalized = compute_mode.strip().lower()
    if not normalized or normalized == "auto":
        return hardware
    if normalized == "cpu":
        if hardware.gpu_available:
            warnings.append("Compute override set to CPU; GPU acceleration disabled.")
        targets = get_hardware_targets()
        return HardwareProfile(
            gpu_available=False,
            vram_gb=max(hardware.vram_gb, targets.minimum_vram_gb),
            ram_gb=hardware.ram_gb,
        )
    if normalized == "gpu":
        if not hardware.gpu_available:
            warnings.append(
                "Compute override set to GPU; hardware detection did not find a GPU."
            )
        return HardwareProfile(
            gpu_available=True, vram_gb=hardware.vram_gb, ram_gb=hardware.ram_gb
        )
    warnings.append(f"Compute override '{compute_mode}' is invalid; using auto detection.")
    return hardware


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
    if resolution_m is None:
        default_scale = _default_scale(model, scales)
        if default_scale is not None:
            return default_scale
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


def _select_tiling(model: str, hardware: HardwareProfile) -> bool:
    if _should_tile(hardware):
        return True
    default_tiling = _model_default_option(model, "tiling")
    if isinstance(default_tiling, bool):
        return default_tiling
    return False


def _select_precision(hardware: HardwareProfile, model: str) -> str:
    default_precision = _model_default_option(model, "precision")
    if isinstance(default_precision, str):
        normalized = default_precision.lower()
        if normalized in {"fp16", "fp32"}:
            if normalized == "fp16" and _supports_fp16(hardware):
                return "fp16"
            return "fp32"
    if _supports_fp16(hardware):
        return "fp16"
    return "fp32"


def _supports_fp16(hardware: HardwareProfile) -> bool:
    targets = get_hardware_targets()
    return hardware.gpu_available and hardware.vram_gb >= targets.minimum_vram_gb


def _default_scale(model: str, scales: tuple[int, ...]) -> int | None:
    default_scale = _model_default_option(model, "scale")
    if isinstance(default_scale, int) and default_scale in scales:
        return default_scale
    return None


def _model_default_option(model: str, key: str) -> object | None:
    options = _MODEL_DEFAULT_OPTIONS.get(model, {})
    if isinstance(options, dict):
        return options.get(key)
    return None


def _apply_safe_mode_defaults(recommendation: ModelRecommendation) -> ModelRecommendation:
    model = recommendation.model
    scales = _MODEL_SCALES.get(model, (2, 4))
    conservative_scale = min(scales) if scales else recommendation.scale
    warnings = list(recommendation.warnings)
    warnings.append("Safe mode enabled; CPU-only conservative defaults applied.")
    return ModelRecommendation(
        model=model,
        scale=conservative_scale,
        tiling=True,
        precision="fp32",
        warnings=tuple(warnings),
        reason=recommendation.reason,
    )


def _load_model_default_options() -> dict[str, dict[str, object]]:
    repo_root = Path(__file__).resolve().parents[1]
    registry_path = repo_root / "models" / "registry.json"
    try:
        with registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}

    defaults: dict[str, dict[str, object]] = {}
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        options = entry.get("default_options")
        if isinstance(name, str) and isinstance(options, dict):
            defaults[name] = options
    return defaults


_MODEL_DEFAULT_OPTIONS = _load_model_default_options()


def _build_reason(scene: SceneMetadata, band_profile: str, model: str) -> str:
    provider = scene.provider or "Unknown provider"
    resolution = (
        "resolution unknown"
        if scene.resolution_m is None
        else f"{scene.resolution_m:.2f}m GSD"
    )
    return f"{provider} {band_profile} scene at {resolution}; mapped to {model}."
