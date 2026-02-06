from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


APP_NAME = "SatelliteUpscale"
LOG_FILE_NAME = "app.log"
DEFAULT_LOG_LEVEL = "INFO"
MAX_LOG_BYTES = 10 * 1024 * 1024
MAX_LOG_FILES = 5


@dataclass(frozen=True)
class LogPaths:
    log_dir: Path
    log_file: Path


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def resolve_log_paths(app_name: str = APP_NAME, base_dir: Path | None = None) -> LogPaths:
    data_dir = _resolve_data_dir(app_name, base_dir)
    log_dir = data_dir / "logs"
    return LogPaths(log_dir=log_dir, log_file=log_dir / LOG_FILE_NAME)


def _resolve_data_dir(app_name: str, base_dir: Path | None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir(app_name)).expanduser()
    except ImportError:
        return _fallback_data_dir(app_name)


def _fallback_data_dir(app_name: str) -> Path:
    home = Path.home()
    if _is_windows():
        base = _env_path("APPDATA") or (home / "AppData" / "Roaming")
        return base / app_name
    if _is_macos():
        return home / "Library" / "Application Support" / app_name
    return home / ".local" / "share" / app_name


def _env_path(name: str) -> Path | None:
    import os

    value = os.environ.get(name)
    if not value:
        return None
    return Path(value)


def _is_windows() -> bool:
    import sys

    return sys.platform.startswith("win")


def _is_macos() -> bool:
    import sys

    return sys.platform == "darwin"


class JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = getattr(record, "payload", {})
        if "ts" not in payload:
            payload["ts"] = _iso_utc_now()
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


class StructuredLogger:
    def __init__(
        self,
        component: str,
        level: str = DEFAULT_LOG_LEVEL,
        log_dir: Path | None = None,
    ) -> None:
        self.component = component
        self._logger = logging.getLogger(f"{APP_NAME}.{component}")
        self._logger.setLevel(_coerce_level(level))
        self._logger.handlers.clear()
        self._logger.propagate = False

        if log_dir is None:
            paths = resolve_log_paths()
        else:
            log_dir = Path(log_dir).expanduser()
            paths = LogPaths(log_dir=log_dir, log_file=log_dir / LOG_FILE_NAME)
        paths.log_dir.mkdir(parents=True, exist_ok=True)

        handler = RotatingFileHandler(
            paths.log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=MAX_LOG_FILES,
            encoding="utf-8",
        )
        handler.setFormatter(JsonLineFormatter())
        self._logger.addHandler(handler)

    def log_event(
        self,
        level: str,
        event: str,
        message: str,
        **fields: Any,
    ) -> None:
        payload = {
            "ts": _iso_utc_now(),
            "level": level.upper(),
            "component": self.component,
            "event": event,
            "message": message,
        }
        for key, value in fields.items():
            if value is not None:
                payload[key] = value
        self._logger.log(_coerce_level(level), message, extra={"payload": payload})

    def close(self) -> None:
        handlers = list(self._logger.handlers)
        for handler in handlers:
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)


def _coerce_level(level: str) -> int:
    return logging._nameToLevel.get(level.upper(), logging.INFO)
