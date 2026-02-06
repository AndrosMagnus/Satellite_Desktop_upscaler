from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
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
        cmd = self.build_command(wrapper, request)
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
