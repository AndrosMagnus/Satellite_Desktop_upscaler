from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import CancelledError
from pathlib import Path

from app.job_pipeline import JobPipeline
from app.job_runner import JobCancellationToken


class TestJobPipeline(unittest.TestCase):
    def test_pipeline_cancellation_discards_outputs(self) -> None:
        cancel_token = JobCancellationToken()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "outputs"
            output_paths: list[Path] = []

            def work(unit_index: int, tracker) -> None:
                output_path = tracker.output_path(f"chunk-{unit_index}.txt")
                output_path.write_text("partial", encoding="utf-8")
                output_paths.append(output_path)
                if unit_index == 0:
                    cancel_token.cancel()

            pipeline = JobPipeline()
            with self.assertRaises(CancelledError):
                pipeline.run(
                    job_id="job-cancel",
                    total_units=2,
                    output_dir=output_dir,
                    work=work,
                    cancel_token=cancel_token,
                )

            for path in output_paths:
                self.assertFalse(path.exists())
            self.assertTrue(not output_dir.exists() or not any(output_dir.iterdir()))

    def test_pipeline_success_keeps_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "outputs"

            def work(unit_index: int, tracker) -> None:
                output_path = tracker.output_path(f"chunk-{unit_index}.txt")
                output_path.write_text(f"unit-{unit_index}", encoding="utf-8")

            pipeline = JobPipeline()
            result = pipeline.run(
                job_id="job-complete",
                total_units=2,
                output_dir=output_dir,
                work=work,
            )

            self.assertEqual(result.completed_units, 2)
            self.assertTrue((output_dir / "chunk-0.txt").exists())
            self.assertTrue((output_dir / "chunk-1.txt").exists())
