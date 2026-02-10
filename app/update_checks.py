from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen


UPDATE_PREF_ENV = "SAT_UPSCALE_UPDATE_PREFS_PATH"
UPDATE_FEED_ENV = "SAT_UPSCALE_UPDATE_FEED_URL"


@dataclass(frozen=True)
class UpdatePreferences:
    enabled: bool


@dataclass(frozen=True)
class ModelUpdate:
    name: str
    current_version: str
    latest_version: str


@dataclass(frozen=True)
class UpdateCheckResult:
    app_update_available: bool
    current_app_version: str
    latest_app_version: str | None
    model_updates: tuple[ModelUpdate, ...]
    message: str
    app_entries: tuple[dict[str, str], ...] = ()
    model_entries: tuple[dict[str, str], ...] = ()


class UpdatePreferenceStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or _default_pref_path()

    def load(self) -> UpdatePreferences:
        if not self._path.is_file():
            return UpdatePreferences(enabled=False)
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return UpdatePreferences(enabled=False)
        if not isinstance(payload, dict):
            return UpdatePreferences(enabled=False)
        enabled = bool(payload.get("enabled", False))
        return UpdatePreferences(enabled=enabled)

    def save(self, preferences: UpdatePreferences) -> None:
        payload = {"enabled": preferences.enabled}
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self._path.with_name(f"{self._path.name}.tmp")
            tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._path)
        except OSError:
            return


def check_for_updates(
    *,
    current_app_version: str,
    model_versions: dict[str, str],
    feed_url: str | None = None,
    timeout_seconds: float = 5.0,
) -> UpdateCheckResult:
    source = feed_url or os.environ.get(UPDATE_FEED_ENV)
    if not source:
        return UpdateCheckResult(
            app_update_available=False,
            current_app_version=current_app_version,
            latest_app_version=None,
            model_updates=(),
            message="Update feed is not configured.",
        )
    try:
        with urlopen(source, timeout=timeout_seconds) as response:  # noqa: S310
            raw = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return UpdateCheckResult(
            app_update_available=False,
            current_app_version=current_app_version,
            latest_app_version=None,
            model_updates=(),
            message=f"Update check failed: {exc}",
        )
    if not isinstance(raw, dict):
        return UpdateCheckResult(
            app_update_available=False,
            current_app_version=current_app_version,
            latest_app_version=None,
            model_updates=(),
            message="Invalid update feed payload.",
        )

    app_payload = raw.get("app", {})
    latest_app = None
    if isinstance(app_payload, dict):
        latest_raw = app_payload.get("latest")
        if isinstance(latest_raw, str):
            latest_app = latest_raw
    app_update = False
    if latest_app:
        app_update = _version_greater(latest_app, current_app_version)

    model_updates: list[ModelUpdate] = []
    model_payload = raw.get("models", {})
    if isinstance(model_payload, dict):
        for name, current in model_versions.items():
            latest = model_payload.get(name)
            if not isinstance(latest, str):
                continue
            if _version_greater(latest, current):
                model_updates.append(
                    ModelUpdate(
                        name=name,
                        current_version=current,
                        latest_version=latest,
                    )
                )

    if not app_update and not model_updates:
        message = "No updates available."
    else:
        pieces = []
        if app_update and latest_app:
            pieces.append(f"App update available: {current_app_version} -> {latest_app}")
        if model_updates:
            pieces.append(f"Model updates: {len(model_updates)}")
        message = "; ".join(pieces)

    app_entries, model_entries = _parse_changelog_entries(raw.get("changelog"))

    return UpdateCheckResult(
        app_update_available=app_update,
        current_app_version=current_app_version,
        latest_app_version=latest_app,
        model_updates=tuple(model_updates),
        message=message,
        app_entries=app_entries,
        model_entries=model_entries,
    )


def _default_pref_path() -> Path:
    env_path = os.environ.get(UPDATE_PREF_ENV)
    if env_path:
        return Path(env_path).expanduser()
    try:
        from platformdirs import user_data_dir

        base = Path(user_data_dir("SatelliteUpscale")).expanduser()
    except ImportError:
        base = _fallback_data_dir("SatelliteUpscale")
    return base / "update_prefs.json"


def _fallback_data_dir(app_name: str) -> Path:
    home = Path.home()
    if os.name == "nt":
        base = os.environ.get("APPDATA")
        if base:
            return Path(base) / app_name
        return home / "AppData" / "Roaming" / app_name
    if platform.system() == "Darwin":
        return home / "Library" / "Application Support" / app_name
    return home / ".local" / "share" / app_name


def _version_greater(left: str, right: str) -> bool:
    def _tokenize(value: str) -> tuple[int, ...]:
        parts = []
        for token in value.replace("v", "").split("."):
            token = token.strip()
            if not token:
                continue
            try:
                parts.append(int(token))
            except ValueError:
                return tuple()
        return tuple(parts)

    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if left_tokens and right_tokens:
        return left_tokens > right_tokens
    return left.strip() > right.strip()


def _parse_changelog_entries(
    value: object,
) -> tuple[tuple[dict[str, str], ...], tuple[dict[str, str], ...]]:
    if not isinstance(value, dict):
        return (), ()
    app_raw = value.get("app") or value.get("app_entries")
    model_raw = value.get("models") or value.get("model_entries")
    return (_normalize_changelog_entries(app_raw), _normalize_changelog_entries(model_raw))


def _normalize_changelog_entries(value: object) -> tuple[dict[str, str], ...]:
    if not isinstance(value, list):
        return ()
    entries: list[dict[str, str]] = []
    for raw in value:
        if not isinstance(raw, dict):
            continue
        date = raw.get("date")
        title = raw.get("title")
        details = raw.get("details")
        if not isinstance(date, str) or not date.strip():
            continue
        if not isinstance(title, str) or not title.strip():
            continue
        if not isinstance(details, str) or not details.strip():
            continue
        entries.append(
            {
                "date": date.strip(),
                "title": title.strip(),
                "details": details.strip(),
            }
        )
    return tuple(entries)
