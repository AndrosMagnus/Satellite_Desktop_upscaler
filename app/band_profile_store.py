from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.imagery_policy import RgbBandMapping


BAND_PROFILE_ENV = "SAT_UPSCALE_BAND_PROFILE_PATH"


class BandProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_profile_path()

    @property
    def path(self) -> Path:
        return self._path

    def load_mapping(self, provider: str, sensor: str) -> RgbBandMapping | None:
        key = _profile_key(provider, sensor)
        payload = self._load_payload()
        profile = payload.get(key)
        if not isinstance(profile, dict):
            return None
        red = _as_index(profile.get("red"))
        green = _as_index(profile.get("green"))
        blue = _as_index(profile.get("blue"))
        if red is None or green is None or blue is None:
            return None
        return RgbBandMapping(red=red, green=green, blue=blue, source="saved profile")

    def save_mapping(
        self,
        provider: str,
        sensor: str,
        mapping: RgbBandMapping,
    ) -> None:
        key = _profile_key(provider, sensor)
        payload = self._load_payload()
        payload[key] = {
            "provider": provider,
            "sensor": sensor,
            "red": mapping.red,
            "green": mapping.green,
            "blue": mapping.blue,
            "updated_at": _iso_utc_now(),
        }
        self._write_payload(payload)

    def _load_payload(self) -> dict[str, object]:
        if not self._path.is_file():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(raw, dict):
            return {}
        return dict(raw)

    def _write_payload(self, payload: dict[str, object]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_name(f"{self._path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._path)
        except OSError:
            return


def _default_profile_path() -> Path:
    env_path = os.environ.get(BAND_PROFILE_ENV)
    if env_path:
        return Path(env_path).expanduser()
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("SatelliteUpscale")).expanduser()
    except ImportError:
        base = _fallback_data_dir("SatelliteUpscale")
    return base / "band_profiles.json"


def _fallback_data_dir(app_name: str) -> Path:
    home = Path.home()
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / app_name
        return home / "AppData" / "Roaming" / app_name
    if os.uname().sysname == "Darwin":
        return home / "Library" / "Application Support" / app_name
    return home / ".local" / "share" / app_name


def _profile_key(provider: str, sensor: str) -> str:
    left = provider.strip().lower() or "unknown-provider"
    right = sensor.strip().lower() or "unknown-sensor"
    return f"{left}::{right}"


def _as_index(value: object) -> int | None:
    if not isinstance(value, int):
        return None
    if value < 0:
        return None
    return value


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
