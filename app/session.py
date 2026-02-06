from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


SESSION_ENV_VAR = "SAT_UPSCALE_SESSION_PATH"
DEFAULT_DIRNAME = ".satellite_upscale"
DEFAULT_FILENAME = "session.json"


@dataclass
class SessionState:
    dirty: bool = False
    paths: list[str] = field(default_factory=list)
    selected_paths: list[str] = field(default_factory=list)
    export_preset: str | None = None
    band_handling: str | None = None
    output_format: str | None = None
    comparison_mode: bool = False
    comparison_model_a: str | None = None
    comparison_model_b: str | None = None
    model_cache_dir: str | None = None
    advanced_scale: str | None = None
    advanced_tiling: str | None = None
    advanced_precision: str | None = None
    advanced_compute: str | None = None
    advanced_seam_blend: bool = False
    advanced_safe_mode: bool = False
    advanced_notifications: bool = False


def _default_session_path() -> Path:
    env_path = os.getenv(SESSION_ENV_VAR)
    if env_path:
        return Path(env_path)
    return Path.home() / DEFAULT_DIRNAME / DEFAULT_FILENAME


def _safe_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _safe_str(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None


def _safe_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return False


class SessionStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_session_path()

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> SessionState:
        if not self._path.exists():
            return SessionState()
        try:
            raw = self._path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return SessionState()
        return SessionState(
            dirty=_safe_bool(data.get("dirty", False)),
            paths=_safe_list(data.get("paths")),
            selected_paths=_safe_list(data.get("selected_paths")),
            export_preset=_safe_str(data.get("export_preset")),
            band_handling=_safe_str(data.get("band_handling")),
            output_format=_safe_str(data.get("output_format")),
            comparison_mode=_safe_bool(data.get("comparison_mode")),
            comparison_model_a=_safe_str(data.get("comparison_model_a")),
            comparison_model_b=_safe_str(data.get("comparison_model_b")),
            model_cache_dir=_safe_str(data.get("model_cache_dir")),
            advanced_scale=_safe_str(data.get("advanced_scale")),
            advanced_tiling=_safe_str(data.get("advanced_tiling")),
            advanced_precision=_safe_str(data.get("advanced_precision")),
            advanced_compute=_safe_str(data.get("advanced_compute")),
            advanced_seam_blend=_safe_bool(data.get("advanced_seam_blend")),
            advanced_safe_mode=_safe_bool(data.get("advanced_safe_mode")),
            advanced_notifications=_safe_bool(data.get("advanced_notifications")),
        )

    def save(self, state: SessionState) -> None:
        payload = {
            "dirty": bool(state.dirty),
            "paths": list(state.paths),
            "selected_paths": list(state.selected_paths),
            "export_preset": state.export_preset,
            "band_handling": state.band_handling,
            "output_format": state.output_format,
            "comparison_mode": bool(state.comparison_mode),
            "comparison_model_a": state.comparison_model_a,
            "comparison_model_b": state.comparison_model_b,
            "model_cache_dir": state.model_cache_dir,
            "advanced_scale": state.advanced_scale,
            "advanced_tiling": state.advanced_tiling,
            "advanced_precision": state.advanced_precision,
            "advanced_compute": state.advanced_compute,
            "advanced_seam_blend": bool(state.advanced_seam_blend),
            "advanced_safe_mode": bool(state.advanced_safe_mode),
            "advanced_notifications": bool(state.advanced_notifications),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_name(f"{self._path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._path)
        except OSError:
            return
