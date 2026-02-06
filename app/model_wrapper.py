from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.error_handling import UserFacingError
from app.model_installation import resolve_install_paths, resolve_venv_python


@dataclass(frozen=True)
class ModelWrapper:
    name: str
    version: str
    weights_path: Path
    venv_dir: Path
    entrypoint: str
    manifest_path: Path | None = None
    extra_env: dict[str, str] = field(default_factory=dict)

    @property
    def model_dir(self) -> Path:
        return self.weights_path.parent

    @property
    def python_executable(self) -> Path:
        return resolve_venv_python(self.venv_dir)

    @classmethod
    def from_installation(
        cls,
        name: str,
        version: str,
        *,
        entrypoint: str,
        base_dir: Path | None = None,
        cache_dir: Path | None = None,
    ) -> "ModelWrapper":
        if not entrypoint:
            raise ValueError("entrypoint must be provided")

        paths = resolve_install_paths(name, version, base_dir=base_dir, cache_dir=cache_dir)
        missing: list[str] = []
        if not paths.manifest.is_file():
            missing.append("manifest")
        if not paths.weights.is_file():
            missing.append("weights")
        if not (paths.venv / "pyvenv.cfg").is_file():
            missing.append("venv")
        if missing:
            details = ", ".join(missing)
            raise UserFacingError(
                title="Model not installed",
                summary="We couldn't find the files needed to run the selected model.",
                suggested_fixes=(
                    "Install the model in the Model Manager.",
                    f"Missing: {details}.",
                ),
                error_code="MODEL-009",
                can_retry=True,
            )

        return cls(
            name=name,
            version=version,
            weights_path=paths.weights,
            venv_dir=paths.venv,
            entrypoint=entrypoint,
            manifest_path=paths.manifest,
        )
