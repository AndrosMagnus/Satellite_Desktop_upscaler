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


def _default_session_path() -> Path:
    env_path = os.getenv(SESSION_ENV_VAR)
    if env_path:
        return Path(env_path)
    return Path.home() / DEFAULT_DIRNAME / DEFAULT_FILENAME


def _safe_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


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
            dirty=bool(data.get("dirty", False)),
            paths=_safe_list(data.get("paths")),
            selected_paths=_safe_list(data.get("selected_paths")),
        )

    def save(self, state: SessionState) -> None:
        payload = {
            "dirty": bool(state.dirty),
            "paths": list(state.paths),
            "selected_paths": list(state.selected_paths),
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_name(f"{self._path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._path)
        except OSError:
            return
