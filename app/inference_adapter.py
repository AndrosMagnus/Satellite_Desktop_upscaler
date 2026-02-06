from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from app.error_handling import UserFacingError
from app.model_wrapper import ModelWrapper


@dataclass(frozen=True)
class InferenceRequest:
    input_path: Path
    output_path: Path
    scale: int | None = None
    tiling: str | None = None
    precision: str | None = None
    compute: str | None = None
    extra_args: tuple[str, ...] = ()


class InferenceAdapter:
    def __init__(
        self,
        runner: Callable[[list[str], dict[str, str] | None], None] | None = None,
    ) -> None:
        self._runner = runner or _default_runner

    def build_command(self, wrapper: ModelWrapper, request: InferenceRequest) -> list[str]:
        python_path = str(wrapper.python_executable)
        entrypoint = wrapper.entrypoint
        cmd: list[str]

        if _is_script_entrypoint(entrypoint):
            entrypoint_path = Path(entrypoint)
            if not entrypoint_path.is_absolute():
                entrypoint_path = wrapper.model_dir / entrypoint_path
            cmd = [python_path, str(entrypoint_path)]
        else:
            cmd = [python_path, "-m", entrypoint]

        cmd.extend(["--weights", str(wrapper.weights_path)])
        cmd.extend(["--input", str(request.input_path)])
        cmd.extend(["--output", str(request.output_path)])

        if request.scale is not None:
            cmd.extend(["--scale", str(request.scale)])
        if request.tiling is not None:
            cmd.extend(["--tiling", request.tiling])
        if request.precision is not None:
            cmd.extend(["--precision", request.precision])
        if request.compute is not None:
            cmd.extend(["--compute", request.compute])
        if request.extra_args:
            cmd.extend(request.extra_args)

        return cmd

    def run(
        self,
        wrapper: ModelWrapper,
        request: InferenceRequest,
        *,
        extra_env: dict[str, str] | None = None,
    ) -> None:
        if not request.input_path.is_file():
            raise FileNotFoundError(str(request.input_path))
        if not wrapper.weights_path.is_file():
            raise FileNotFoundError(str(wrapper.weights_path))

        entrypoint = wrapper.entrypoint
        if _is_script_entrypoint(entrypoint):
            entrypoint_path = Path(entrypoint)
            if not entrypoint_path.is_absolute():
                entrypoint_path = wrapper.model_dir / entrypoint_path
            if not entrypoint_path.is_file():
                raise UserFacingError(
                    title="Model entrypoint missing",
                    summary="We couldn't locate the model's inference script.",
                    suggested_fixes=(
                        "Reinstall the model and try again.",
                        "Verify the model package includes its inference entrypoint.",
                    ),
                    error_code="MODEL-011",
                    can_retry=True,
                )

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        env = _merge_env(wrapper.extra_env, extra_env)
        effective_compute = _cpu_fallback_compute(request.compute, env or os.environ)
        effective_request = (
            request
            if effective_compute == request.compute
            else replace(request, compute=effective_compute)
        )
        cmd = self.build_command(wrapper, effective_request)
        try:
            self._runner(cmd, env)
        except subprocess.CalledProcessError as exc:
            raise UserFacingError(
                title="Model inference failed",
                summary="We couldn't run the selected model.",
                suggested_fixes=(
                    "Check the model logs for details.",
                    "Try again after restarting the app.",
                ),
                error_code="MODEL-010",
                can_retry=True,
            ) from exc


def _default_runner(cmd: list[str], env: dict[str, str] | None) -> None:
    subprocess.run(cmd, check=True, env=env)


def _merge_env(
    wrapper_env: dict[str, str],
    extra_env: dict[str, str] | None,
) -> dict[str, str] | None:
    if not wrapper_env and not extra_env:
        return None
    merged = dict(os.environ)
    merged.update(wrapper_env)
    if extra_env:
        merged.update(extra_env)
    return merged


def _is_script_entrypoint(entrypoint: str) -> bool:
    return entrypoint.endswith(".py") or "/" in entrypoint or "\\" in entrypoint


def _cpu_fallback_compute(
    compute: str | None,
    env: Mapping[str, str],
) -> str | None:
    normalized = _normalize_compute(compute)
    if normalized == "cpu":
        return compute
    if normalized in (None, "auto", "gpu", "cuda") and not _gpu_available(env):
        return "CPU"
    return compute


def _normalize_compute(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped.lower()


def _gpu_available(env: Mapping[str, str]) -> bool:
    if _cuda_disabled_by_env(env):
        return False
    if shutil.which("nvidia-smi") is None:
        return False
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            check=False,
            env=dict(env),
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    return any(line.strip() for line in result.stdout.splitlines())


def _cuda_disabled_by_env(env: Mapping[str, str]) -> bool:
    for key in ("CUDA_VISIBLE_DEVICES", "NVIDIA_VISIBLE_DEVICES"):
        value = env.get(key)
        if value is None:
            continue
        normalized = value.strip().lower()
        if normalized in {"", "-1", "none", "null", "void"}:
            return True
    return False
