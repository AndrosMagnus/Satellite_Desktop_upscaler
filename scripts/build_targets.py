"""Build tooling configuration for supported OS targets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class OsTarget:
    name: str
    minimum_version: str


SUPPORTED_OS_TARGETS: Dict[str, OsTarget] = {
    "windows": OsTarget(name="Windows", minimum_version="10"),
    "macos": OsTarget(name="macOS", minimum_version="12"),
    "ubuntu": OsTarget(name="Ubuntu", minimum_version="20.04"),
}


def get_supported_os_targets() -> Dict[str, OsTarget]:
    """Return the supported OS targets for build tooling."""

    return dict(SUPPORTED_OS_TARGETS)
