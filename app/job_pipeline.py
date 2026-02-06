from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.band_handling import ExportSettings
from app.job_runner import Job, JobCancellationToken, JobProgress, JobResult, JobRunner
from app.processing_report import (
    ProcessingTimings,
    build_processing_report,
    export_processing_report,
)


@dataclass(frozen=True)
class ProcessingReportConfig:
    export_settings: ExportSettings
    model_name: str
    report_path: Path
    scale: int | None = None
    tiling: str | None = None
    precision: str | None = None
    compute: str | None = None
    model_version: str | None = None
    registry_path: Path | None = None


class OutputTracker:
    def __init__(self, output_dir: Path) -> None:
        self._output_dir = Path(output_dir)
        self._paths: list[Path] = []

    @property
    def output_dir(self) -> Path:
        return self._output_dir

    def output_path(self, relative_path: str | Path) -> Path:
        rel = Path(relative_path)
        path = rel if rel.is_absolute() else self._output_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        self._paths.append(path)
        return path

    def discard(self) -> None:
        for path in sorted(self._paths, key=lambda item: len(item.parts), reverse=True):
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                try:
                    path.unlink()
                except FileNotFoundError:
                    continue
        self._paths.clear()
        if self._output_dir.exists() and not any(self._output_dir.iterdir()):
            self._output_dir.rmdir()


class JobPipeline:
    def __init__(self, runner: JobRunner | None = None) -> None:
        self._runner = runner or JobRunner()

    def run(
        self,
        *,
        job_id: str,
        total_units: int,
        output_dir: Path,
        work: Callable[[int, OutputTracker], None],
        report_config: ProcessingReportConfig | None = None,
        report_clock: Callable[[], datetime] | None = None,
        cancel_token: JobCancellationToken | None = None,
        on_progress: Callable[[JobProgress], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ) -> JobResult:
        tracker = OutputTracker(output_dir)
        token = cancel_token or JobCancellationToken()
        started_at: datetime | None = None
        clock = report_clock or (lambda: datetime.now(timezone.utc))
        if report_config is not None:
            started_at = clock()

        def unit_work(unit_index: int) -> None:
            work(unit_index, tracker)

        def handle_cancel() -> None:
            tracker.discard()
            if on_cancel:
                on_cancel()

        job = Job(
            job_id=job_id,
            total_units=total_units,
            work=unit_work,
            cancel_token=token,
            on_cancel=handle_cancel,
        )
        result = self._runner.run(job, on_progress=on_progress)
        if report_config is not None:
            completed_at = clock()
            timings = ProcessingTimings.from_datetimes(
                started_at or completed_at, completed_at
            )
            report = build_processing_report(
                export_settings=report_config.export_settings,
                model_name=report_config.model_name,
                timings=timings,
                scale=report_config.scale,
                tiling=report_config.tiling,
                precision=report_config.precision,
                compute=report_config.compute,
                model_version=report_config.model_version,
                registry_path=report_config.registry_path,
            )
            export_processing_report(report, report_config.report_path)
        return result
