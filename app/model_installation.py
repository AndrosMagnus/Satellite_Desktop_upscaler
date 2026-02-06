from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import venv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse
from urllib.request import urlopen

from app.error_handling import UserFacingError


DATA_DIR_ENV = "SATELLITE_UPSCALE_DATA_DIR"


@dataclass(frozen=True)
class InstallPaths:
    root: Path
    weights: Path
    manifest: Path
    venv: Path


@dataclass(frozen=True)
class InstallResult:
    paths: InstallPaths
    size_bytes: int
    checksum: str | None


class ModelInstaller:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir

    def is_installed(self, name: str, version: str) -> bool:
        paths = resolve_install_paths(name, version, base_dir=self._base_dir)
        if not paths.manifest.is_file():
            return False
        if not paths.weights.is_file():
            return False
        if not (paths.venv / "pyvenv.cfg").is_file():
            return False
        return True

    def install(
        self,
        name: str,
        version: str,
        weights_url: str,
        checksum: str | None = None,
        dependencies: Iterable[str] | None = None,
    ) -> InstallResult:
        return install_model(
            name,
            version,
            weights_url,
            checksum=checksum,
            dependencies=dependencies,
            base_dir=self._base_dir,
        )

    def uninstall(self, name: str, version: str) -> None:
        uninstall_model(name, version, base_dir=self._base_dir)


def resolve_model_cache_dir(base_dir: Path | None = None) -> Path:
    data_dir = _resolve_data_dir(base_dir)
    return data_dir / "models"


def resolve_install_paths(
    name: str,
    version: str,
    *,
    base_dir: Path | None = None,
    filename: str | None = None,
) -> InstallPaths:
    cache_dir = resolve_model_cache_dir(base_dir)
    model_dir = cache_dir / _slugify(name) / _slugify(version or "latest")
    weights_name = filename or "weights.bin"
    return InstallPaths(
        root=model_dir,
        weights=model_dir / weights_name,
        manifest=model_dir / "manifest.json",
        venv=model_dir / "venv",
    )


def install_model(
    name: str,
    version: str,
    weights_url: str,
    *,
    checksum: str | None = None,
    dependencies: Iterable[str] | None = None,
    base_dir: Path | None = None,
) -> InstallResult:
    if not weights_url or weights_url.strip().upper() == "TBD":
        raise UserFacingError(
            title="Model weights unavailable",
            summary="This model does not have downloadable weights yet.",
            suggested_fixes=(
                "Choose a different model to install.",
                "Check for updates when weights become available.",
            ),
            error_code="MODEL-001",
            can_retry=False,
        )

    weights_name = _infer_weights_filename(weights_url)
    paths = resolve_install_paths(
        name,
        version,
        base_dir=base_dir,
        filename=weights_name,
    )
    paths.root.mkdir(parents=True, exist_ok=True)
    _ensure_venv(paths.venv)
    _install_dependencies(paths.venv, dependencies or ())

    tmp_path = Path(tempfile.mkstemp(prefix="weights_", suffix=".tmp", dir=paths.root)[1])
    try:
        size_bytes, digest = _download_weights(weights_url, tmp_path)
        expected = _parse_sha256(checksum)
        if expected is not None and digest is not None and digest != expected:
            raise UserFacingError(
                title="Model download failed",
                summary="The downloaded file did not match the expected checksum.",
                suggested_fixes=(
                    "Retry the download.",
                    "Verify the network connection and try again.",
                ),
                error_code="MODEL-002",
                can_retry=True,
            )
        os.replace(tmp_path, paths.weights)
        health = _run_health_check(paths, tuple(dependencies or ()))
        if health["status"] != "ok":
            uninstall_model(name, version, base_dir=base_dir)
            raise UserFacingError(
                title="Model health check failed",
                summary="We couldn't verify the installed model dependencies.",
                suggested_fixes=tuple(health["issues"]) or ("Retry the install.",),
                error_code="MODEL-008",
                can_retry=True,
            )
        _write_manifest(
            paths.manifest,
            name,
            version,
            weights_url,
            paths.weights.name,
            size_bytes,
            checksum,
            tuple(dependencies or ()),
            health=health,
        )
        return InstallResult(paths=paths, size_bytes=size_bytes, checksum=digest)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def uninstall_model(name: str, version: str, *, base_dir: Path | None = None) -> None:
    paths = resolve_install_paths(name, version, base_dir=base_dir)
    if paths.root.exists():
        shutil.rmtree(paths.root, ignore_errors=True)


def _infer_weights_filename(weights_url: str) -> str:
    parsed = urlparse(weights_url)
    if parsed.path:
        name = Path(unquote(parsed.path)).name
        if name:
            return name
    return "weights.bin"


def _download_weights(url: str, dest: Path) -> tuple[int, str | None]:
    parsed = urlparse(url)
    if parsed.scheme in ("", "file"):
        source = _resolve_file_url(parsed, url)
        digest, size_bytes = _copy_with_checksum(source, dest)
        return size_bytes, digest
    if parsed.scheme not in ("http", "https"):
        raise UserFacingError(
            title="Unsupported download",
            summary="We can only install models from http(s) or local files.",
            suggested_fixes=("Check the model registry entry.",),
            error_code="MODEL-003",
            can_retry=False,
        )
    digest = hashlib.sha256()
    size_bytes = 0
    with urlopen(url) as response, dest.open("wb") as handle:  # noqa: S310
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            size_bytes += len(chunk)
    return size_bytes, digest.hexdigest()


def _resolve_file_url(parsed, url: str) -> Path:
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
        if os.name == "nt" and path.as_posix().startswith("/"):
            path = Path(path.as_posix().lstrip("/"))
        return path
    return Path(url)


def _copy_with_checksum(source: Path, dest: Path) -> tuple[str | None, int]:
    digest = hashlib.sha256()
    size_bytes = 0
    with source.open("rb") as src, dest.open("wb") as handle:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            digest.update(chunk)
            size_bytes += len(chunk)
    return digest.hexdigest(), size_bytes


def _write_manifest(
    path: Path,
    name: str,
    version: str,
    weights_url: str,
    weights_filename: str,
    size_bytes: int,
    checksum: str | None,
    dependencies: tuple[str, ...],
    *,
    health: dict[str, object] | None = None,
) -> None:
    payload = {
        "name": name,
        "version": version,
        "weights_url": weights_url,
        "weights_filename": weights_filename,
        "size_bytes": size_bytes,
        "checksum": checksum,
        "dependencies": list(dependencies),
        "installed_at": _iso_utc_now(),
    }
    if health is not None:
        payload["health"] = health
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _ensure_venv(venv_dir: Path) -> None:
    if (venv_dir / "pyvenv.cfg").is_file():
        return
    builder = venv.EnvBuilder(with_pip=True, clear=False)
    try:
        builder.create(venv_dir)
    except SystemExit as exc:
        raise UserFacingError(
            title="Python venv setup failed",
            summary="We couldn't create the model's isolated environment.",
            suggested_fixes=(
                "Install the Python venv support package for your system.",
                "Restart the app after installing it and try again.",
            ),
            error_code="MODEL-007",
            can_retry=False,
        ) from exc


def _venv_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _is_pinned_dependency(value: str) -> bool:
    if "==" in value:
        return True
    if "@" in value:
        return True
    if value.endswith(".whl"):
        return True
    if value.startswith("file:"):
        return True
    return False


def _install_dependencies(venv_dir: Path, dependencies: Iterable[str]) -> None:
    deps = [str(dep).strip() for dep in dependencies if str(dep).strip()]
    if not deps:
        return
    unpinned = [dep for dep in deps if not _is_pinned_dependency(dep)]
    if unpinned:
        raise UserFacingError(
            title="Unpinned dependencies",
            summary="Model dependencies must be pinned to exact versions.",
            suggested_fixes=(
                "Update the model registry to include version pins (example: pkg==1.2.3).",
            ),
            error_code="MODEL-005",
            can_retry=False,
        )
    python_path = _venv_python(venv_dir)
    try:
        subprocess.run(
            [
                str(python_path),
                "-m",
                "pip",
                "install",
                "--no-input",
                "--disable-pip-version-check",
                *deps,
            ],
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise UserFacingError(
            title="Dependency installation failed",
            summary="We couldn't install the model dependencies.",
            suggested_fixes=(
                "Check your network connection and try again.",
                "Verify the dependency pins in the model registry.",
            ),
            error_code="MODEL-006",
            can_retry=True,
        ) from exc


def run_missing_health_checks(base_dir: Path | None = None) -> list[dict[str, object]]:
    cache_dir = resolve_model_cache_dir(base_dir)
    if not cache_dir.exists():
        return []
    results: list[dict[str, object]] = []
    for manifest_path in cache_dir.rglob("manifest.json"):
        manifest = _load_manifest(manifest_path)
        if manifest is None or not _health_check_needed(manifest):
            continue
        paths = _paths_from_manifest(manifest_path, manifest)
        dependencies = manifest.get("dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = []
        health = _run_health_check(paths, tuple(str(dep) for dep in dependencies))
        _update_manifest_health(manifest_path, manifest, health)
        results.append(health)
    return results


def _health_check_needed(manifest: dict[str, object]) -> bool:
    health = manifest.get("health")
    if not isinstance(health, dict):
        return True
    checked_at = health.get("checked_at")
    return not isinstance(checked_at, str) or not checked_at.strip()


def _load_manifest(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _paths_from_manifest(manifest_path: Path, manifest: dict[str, object]) -> InstallPaths:
    root = manifest_path.parent
    weights_filename = str(manifest.get("weights_filename") or "weights.bin")
    return InstallPaths(
        root=root,
        weights=root / weights_filename,
        manifest=manifest_path,
        venv=root / "venv",
    )


def _update_manifest_health(
    manifest_path: Path,
    manifest: dict[str, object],
    health: dict[str, object],
) -> None:
    manifest["health"] = health
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _run_health_check(
    paths: InstallPaths, dependencies: tuple[str, ...]
) -> dict[str, object]:
    issues: list[str] = []
    if not paths.weights.is_file():
        issues.append("Model weights were not found.")
    if not (paths.venv / "pyvenv.cfg").is_file():
        issues.append("Model virtual environment is missing.")
    dependency_results = _check_dependencies(paths.venv, dependencies)
    for result in dependency_results:
        status = result.get("status")
        name = result.get("name") or "dependency"
        required = result.get("required")
        if status == "missing":
            issues.append(f"{name} is not installed.")
        elif status == "version_mismatch":
            issues.append(f"{name} does not match required version {required}.")
        elif status == "error":
            issues.append(f"Dependency check failed for {name}.")
    status = "ok" if not issues else "failed"
    return {
        "status": status,
        "checked_at": _iso_utc_now(),
        "issues": issues,
        "dependencies": dependency_results,
    }


def _check_dependencies(
    venv_dir: Path, dependencies: Iterable[str]
) -> list[dict[str, object]]:
    deps = [str(dep).strip() for dep in dependencies if str(dep).strip()]
    if not deps:
        return []
    checks: list[dict[str, object]] = []
    pending_indices: list[int] = []
    results: list[dict[str, object]] = []
    for dep in deps:
        name, required = _parse_dependency(dep)
        if not name:
            results.append(
                {
                    "name": dep,
                    "required": None,
                    "installed": None,
                    "status": "unverifiable",
                }
            )
            continue
        pending_indices.append(len(results))
        checks.append({"name": name, "required": required})
        results.append(
            {
                "name": name,
                "required": required,
                "installed": None,
                "status": "pending",
            }
        )

    if not checks:
        return results
    python_path = _venv_python(venv_dir)
    check_results = _run_dependency_check(python_path, checks)
    for index, check in zip(pending_indices, check_results, strict=True):
        results[index] = check
    return results


def _run_dependency_check(
    python_path: Path, checks: list[dict[str, object]]
) -> list[dict[str, object]]:
    script = (
        "import importlib.metadata as m, json, sys\n"
        "checks = json.loads(sys.argv[1])\n"
        "results = []\n"
        "for item in checks:\n"
        "    name = item.get('name')\n"
        "    required = item.get('required')\n"
        "    try:\n"
        "        installed = m.version(name)\n"
        "    except m.PackageNotFoundError:\n"
        "        results.append({'name': name, 'required': required, 'installed': None, 'status': 'missing'})\n"
        "        continue\n"
        "    status = 'ok'\n"
        "    if required and installed != required:\n"
        "        status = 'version_mismatch'\n"
        "    results.append({'name': name, 'required': required, 'installed': installed, 'status': status})\n"
        "print(json.dumps(results))\n"
    )
    try:
        completed = subprocess.run(
            [str(python_path), "-c", script, json.dumps(checks)],
            check=True,
            capture_output=True,
            text=True,
        )
        parsed = json.loads(completed.stdout.strip() or "[]")
        if isinstance(parsed, list) and len(parsed) == len(checks):
            return [dict(item) for item in parsed]
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        pass
    return [
        {
            "name": item.get("name"),
            "required": item.get("required"),
            "installed": None,
            "status": "error",
        }
        for item in checks
    ]


def _parse_sha256(checksum: str | None) -> str | None:
    if not checksum:
        return None
    if checksum.lower().startswith("sha256:"):
        value = checksum.split(":", 1)[1].strip()
        if value and value.upper() != "TODO":
            return value
    return None


def _iso_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_dependency(value: str) -> tuple[str | None, str | None]:
    requirement = value.split(";", 1)[0].strip()
    if not requirement:
        return None, None
    if requirement.startswith("file:") or requirement.endswith(".whl"):
        return None, None
    if "@" in requirement:
        name = requirement.split("@", 1)[0].strip()
        name = name.split("[", 1)[0].strip()
        return (name or None), None
    if "==" in requirement:
        name, version = requirement.split("==", 1)
        name = name.split("[", 1)[0].strip()
        version = version.strip()
        return (name or None), (version or None)
    name = requirement.split("[", 1)[0].strip()
    return (name or None), None


def _resolve_data_dir(base_dir: Path | None) -> Path:
    if base_dir is not None:
        return Path(base_dir).expanduser()
    env_dir = os.environ.get(DATA_DIR_ENV)
    if env_dir:
        return Path(env_dir).expanduser()
    try:
        from platformdirs import user_data_dir

        return Path(user_data_dir("SatelliteUpscale")).expanduser()
    except ImportError:
        return _fallback_data_dir("SatelliteUpscale")


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


def _slugify(value: str) -> str:
    cleaned = []
    for char in value.lower().strip():
        if char.isalnum():
            cleaned.append(char)
        else:
            if cleaned and cleaned[-1] != "-":
                cleaned.append("-")
    slug = "".join(cleaned).strip("-")
    return slug or "model"
