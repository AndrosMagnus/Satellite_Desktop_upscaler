from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.validation import EvaluationReport


@dataclass(frozen=True)
class ValidationThreshold:
    psnr_min: float
    ssim_min: float


@dataclass(frozen=True)
class ValidationThresholdResult:
    passed: bool
    issues: tuple[str, ...]


def load_validation_baselines(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Baseline file must be a JSON object.")
    return payload


def resolve_threshold(
    baselines: dict[str, object],
    *,
    dataset: str,
    model: str | None = None,
) -> ValidationThreshold | None:
    datasets = baselines.get("datasets")
    if not isinstance(datasets, dict):
        return None
    dataset_entry = datasets.get(dataset)
    if not isinstance(dataset_entry, dict):
        return None

    if model:
        model_map = dataset_entry.get("models")
        if isinstance(model_map, dict):
            model_entry = model_map.get(model)
            threshold = _parse_threshold(model_entry)
            if threshold is not None:
                return threshold

    return _parse_threshold(dataset_entry.get("default"))


def evaluate_threshold(
    report: EvaluationReport,
    threshold: ValidationThreshold,
) -> ValidationThresholdResult:
    issues: list[str] = []
    if report.average_psnr < threshold.psnr_min:
        issues.append(
            f"Average PSNR {report.average_psnr:.3f} below minimum {threshold.psnr_min:.3f}."
        )
    if report.average_ssim < threshold.ssim_min:
        issues.append(
            f"Average SSIM {report.average_ssim:.4f} below minimum {threshold.ssim_min:.4f}."
        )
    return ValidationThresholdResult(passed=not issues, issues=tuple(issues))


def threshold_to_dict(
    threshold: ValidationThreshold,
    result: ValidationThresholdResult,
) -> dict[str, object]:
    return {
        "psnr_min": threshold.psnr_min,
        "ssim_min": threshold.ssim_min,
        "passed": result.passed,
        "issues": list(result.issues),
    }


def _parse_threshold(value: object) -> ValidationThreshold | None:
    if not isinstance(value, dict):
        return None
    psnr_min = value.get("psnr_min")
    ssim_min = value.get("ssim_min")
    if not isinstance(psnr_min, (int, float)):
        return None
    if not isinstance(ssim_min, (int, float)):
        return None
    return ValidationThreshold(psnr_min=float(psnr_min), ssim_min=float(ssim_min))
