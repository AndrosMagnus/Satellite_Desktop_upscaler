from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.job_runner import Job, JobRunner
from app.structured_logging import StructuredLogger


class _FakeClock:
    def __init__(self) -> None:
        self._time = 0.0

    def monotonic(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds


class TestJobRunner(unittest.TestCase):
    def test_job_runner_reports_progress_and_eta(self) -> None:
        clock = _FakeClock()
        durations = [1.0, 1.0, 2.0]
        progress_updates = []

        def work(unit_index: int) -> None:
            clock.advance(durations[unit_index])

        runner = JobRunner(time_provider=clock.monotonic)
        job = Job(job_id="job-1", total_units=3, work=work)

        runner.run(job, on_progress=progress_updates.append)

        self.assertEqual(len(progress_updates), 3)
        self.assertAlmostEqual(progress_updates[0].progress, 1 / 3)
        self.assertAlmostEqual(progress_updates[0].eta_seconds, 2.0)
        self.assertAlmostEqual(progress_updates[1].progress, 2 / 3)
        self.assertAlmostEqual(progress_updates[1].eta_seconds, 1.0)
        self.assertAlmostEqual(progress_updates[2].progress, 1.0)
        self.assertAlmostEqual(progress_updates[2].eta_seconds, 0.0)

    def test_job_runner_writes_structured_logs(self) -> None:
        clock = _FakeClock()

        def work(_: int) -> None:
            clock.advance(0.5)

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            logger = StructuredLogger("runner", log_dir=log_dir)
            runner = JobRunner(logger=logger, time_provider=clock.monotonic)

            runner.run(Job(job_id="job-2", total_units=2, work=work))

            log_file = log_dir / "app.log"
            self.assertTrue(log_file.exists())
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()

            self.assertGreaterEqual(len(lines), 3)
            payloads = [json.loads(line) for line in lines]

            for payload in payloads:
                self.assertIn("ts", payload)
                self.assertTrue(payload["ts"].endswith("Z"))
                self.assertIn("level", payload)
                self.assertIn("component", payload)
                self.assertIn("event", payload)
                self.assertIn("message", payload)
