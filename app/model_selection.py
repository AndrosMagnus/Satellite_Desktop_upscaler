from __future__ import annotations

from dataclasses import dataclass

from app.dataset_analysis import DatasetInfo
from app.recommendation import (
    HardwareProfile,
    ModelOverrides,
    SceneMetadata,
    recommend_model_with_overrides,
)


@dataclass(frozen=True)
class ExecutionModelPlan:
    model: str
    scale: int
    tiling: str
    precision: str
    compute: str
    warnings: tuple[str, ...]
    reason: str


def recommend_execution_plan(
    info: DatasetInfo,
    hardware: HardwareProfile,
    *,
    model_override: str | None = None,
    scale_override: int | None = None,
    tiling_override: str | None = None,
    precision_override: str | None = None,
    compute_override: str | None = None,
    safe_mode: bool = False,
) -> ExecutionModelPlan:
    scene = SceneMetadata(
        provider=info.provider,
        band_count=_band_count_for_scene(info),
        resolution_m=_resolution_m(info),
        is_cloud_imagery=_is_cloud_imagery(info),
    )
    overrides = ModelOverrides(
        model=model_override,
        scale=scale_override,
        tiling=_tiling_override_to_bool(tiling_override),
        precision=_precision_for_override(precision_override),
        compute_mode=compute_override,
        safe_mode=safe_mode,
    )
    recommendation = recommend_model_with_overrides(scene, hardware, overrides)
    scale = int(scale_override if scale_override is not None else recommendation.scale)
    if scale <= 0:
        scale = max(1, recommendation.scale)
    return ExecutionModelPlan(
        model=recommendation.model,
        scale=scale,
        tiling=_tiling_for_request(tiling_override, recommendation.tiling),
        precision=_precision_for_request(precision_override, recommendation.precision),
        compute=_compute_for_request(
            compute_override,
            safe_mode=safe_mode,
            gpu_available=hardware.gpu_available,
        ),
        warnings=tuple(recommendation.warnings),
        reason=recommendation.reason,
    )


def _band_count_for_scene(info: DatasetInfo) -> int:
    if info.band_count is None or info.band_count <= 0:
        return 3
    return int(info.band_count)


def _resolution_m(info: DatasetInfo) -> float | None:
    if info.grid is None:
        return None
    x_size = abs(float(info.grid.transform[0]))
    if x_size <= 0.0:
        return None
    return x_size


def _is_cloud_imagery(info: DatasetInfo) -> bool:
    provider = (info.provider or "").strip().lower()
    if "cloud" in provider:
        return True
    stem = info.path.stem.lower()
    cloud_tokens = ("cloud", "mrdam", "meteorological", "weather")
    return any(token in stem for token in cloud_tokens)


def _tiling_override_to_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    if normalized in {"off", "none", "disabled", "false", "0"}:
        return False
    return True


def _tiling_for_request(value: str | None, recommended: bool) -> str:
    if value is not None and value.strip():
        return value.strip()
    return "512 px" if recommended else "Off"


def _precision_for_override(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    if normalized in {"fp16", "float16"}:
        return "fp16"
    if normalized in {"fp32", "float32"}:
        return "fp32"
    return None


def _precision_for_request(value: str | None, recommended: str) -> str:
    normalized = _precision_for_override(value)
    if normalized is not None:
        return normalized.upper()
    return recommended.upper()


def _compute_for_request(
    value: str | None,
    *,
    safe_mode: bool,
    gpu_available: bool,
) -> str:
    if safe_mode:
        return "CPU"
    if value:
        normalized = value.strip().upper()
        if normalized in {"CPU", "GPU"}:
            return normalized
    return "GPU" if gpu_available else "CPU"
