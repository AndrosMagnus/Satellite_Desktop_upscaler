from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.band_handling import ExportSettings


@dataclass(frozen=True)
class ProcessingSettings:
    band_handling: str
    output_format: str
    scale: int | None
    tiling: str | None
    precision: str | None
    compute: str | None


@dataclass(frozen=True)
class ProcessingModel:
    name: str
    version: str


@dataclass(frozen=True)
class ProcessingTimings:
    started_at: str
    completed_at: str
    duration_ms: int

    @classmethod
    def from_datetimes(cls, started_at: datetime, completed_at: datetime) -> "ProcessingTimings":
        started_iso = _iso_utc(started_at)
        completed_iso = _iso_utc(completed_at)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)
        if duration_ms < 0:
            raise ValueError("completed_at must be after started_at")
        return cls(
            started_at=started_iso,
            completed_at=completed_iso,
            duration_ms=duration_ms,
        )


@dataclass(frozen=True)
class ProcessingReport:
    settings: ProcessingSettings
    model: ProcessingModel
    timings: ProcessingTimings

    def to_dict(self) -> dict[str, object]:
        return {
            "settings": {
                "band_handling": self.settings.band_handling,
                "output_format": self.settings.output_format,
                "scale": self.settings.scale,
                "tiling": self.settings.tiling,
                "precision": self.settings.precision,
                "compute": self.settings.compute,
            },
            "model": {
                "name": self.model.name,
                "version": self.model.version,
            },
            "timings": {
                "started_at": self.timings.started_at,
                "completed_at": self.timings.completed_at,
                "duration_ms": self.timings.duration_ms,
            },
        }


def build_processing_report(
    export_settings: ExportSettings,
    model_name: str,
    timings: ProcessingTimings,
    *,
    scale: int | None = None,
    tiling: str | None = None,
    precision: str | None = None,
    compute: str | None = None,
    model_version: str | None = None,
    registry_path: Path | None = None,
) -> ProcessingReport:
    if not model_name:
        raise ValueError("model_name must be provided")

    resolved_version = model_version or resolve_model_version(
        model_name, registry_path=registry_path
    )

    settings = ProcessingSettings(
        band_handling=export_settings.band_handling.value,
        output_format=export_settings.output_format,
        scale=scale,
        tiling=tiling,
        precision=precision,
        compute=compute,
    )
    model = ProcessingModel(name=model_name, version=resolved_version)
    return ProcessingReport(settings=settings, model=model, timings=timings)


def export_processing_report(report: ProcessingReport, path: Path) -> None:
    payload = report.to_dict()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp_path, path)


def resolve_model_version(model_name: str, registry_path: Path | None = None) -> str:
    if not model_name:
        return "Unknown"
    models = _load_model_registry(registry_path)
    for entry in models:
        if str(entry.get("name", "")) == model_name:
            weights_url = str(entry.get("weights_url", ""))
            version = _extract_model_version(weights_url)
            return version or "Unknown"
    return "Unknown"


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_model_version(weights_url: str) -> str | None:
    if not weights_url:
        return None
    match = re.search(r"/download/(v[^/]+)/", weights_url)
    if match:
        return match.group(1)
    match = re.search(r"\bv\d+\.\d+(?:\.\d+)?\b", weights_url)
    if match:
        return match.group(0)
    return None


def _load_model_registry(registry_path: Path | None = None) -> list[dict[str, object]]:
    if registry_path is None:
        repo_root = Path(__file__).resolve().parents[1]
        registry_path = repo_root / "models" / "registry.json"
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]
