from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from app.structured_logging import StructuredLogger


@dataclass(frozen=True)
class Job:
    job_id: str
    total_units: int
    work: Callable[[int], None]
    description: str | None = None


@dataclass(frozen=True)
class JobProgress:
    job_id: str
    completed_units: int
    total_units: int
    progress: float
    eta_seconds: float | None


@dataclass(frozen=True)
class JobResult:
    job_id: str
    completed_units: int
    total_units: int
    duration_ms: int


class JobRunner:
    def __init__(
        self,
        logger: StructuredLogger | None = None,
        time_provider: Callable[[], float] | None = None,
    ) -> None:
        self._logger = logger
        self._time = time_provider or time.monotonic

    def run(
        self,
        job: Job,
        on_progress: Callable[[JobProgress], None] | None = None,
    ) -> JobResult:
        if job.total_units <= 0:
            raise ValueError("total_units must be positive")

        start_time = self._time()
        completed = 0
        total_duration = 0.0

        if self._logger:
            self._logger.log_event(
                "INFO",
                "job_start",
                "Job started",
                job_id=job.job_id,
                total_units=job.total_units,
                description=job.description,
            )

        try:
            for unit_index in range(job.total_units):
                unit_start = self._time()
                job.work(unit_index)
                unit_end = self._time()

                duration = unit_end - unit_start
                total_duration += duration
                completed += 1

                average_unit = total_duration / completed
                remaining = job.total_units - completed
                eta_seconds = average_unit * remaining

                progress = JobProgress(
                    job_id=job.job_id,
                    completed_units=completed,
                    total_units=job.total_units,
                    progress=completed / job.total_units,
                    eta_seconds=eta_seconds,
                )

                if on_progress:
                    on_progress(progress)

                if self._logger:
                    self._logger.log_event(
                        "INFO",
                        "job_progress",
                        "Job progress update",
                        job_id=job.job_id,
                        completed_units=completed,
                        total_units=job.total_units,
                        progress=progress.progress,
                        eta_seconds=eta_seconds,
                    )
        except Exception as exc:  # noqa: BLE001
            if self._logger:
                self._logger.log_event(
                    "ERROR",
                    "job_failed",
                    "Job failed",
                    job_id=job.job_id,
                    error=str(exc),
                    error_code="JOB-001",
                )
            raise

        duration_ms = int((self._time() - start_time) * 1000)
        if self._logger:
            self._logger.log_event(
                "INFO",
                "job_complete",
                "Job completed",
                job_id=job.job_id,
                completed_units=completed,
                total_units=job.total_units,
                duration_ms=duration_ms,
            )

        return JobResult(
            job_id=job.job_id,
            completed_units=completed,
            total_units=job.total_units,
            duration_ms=duration_ms,
        )
