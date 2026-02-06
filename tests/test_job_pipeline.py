from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import CancelledError
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.band_handling import BandHandling, ExportSettings
from app.job_pipeline import JobPipeline, ProcessingReportConfig
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

    def test_pipeline_exports_processing_report_on_success(self) -> None:
        export_settings = ExportSettings(
            band_handling=BandHandling.RGB_PLUS_ALL,
            output_format="GeoTIFF",
        )
        start = datetime(2025, 1, 2, 9, 30, 0, tzinfo=timezone.utc)
        end = start + timedelta(seconds=5)
        clock_times = iter([start, end])

        def report_clock() -> datetime:
            return next(clock_times)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "outputs"
            report_path = Path(temp_dir) / "processing-report.json"

            def work(unit_index: int, tracker) -> None:
                output_path = tracker.output_path(f"unit-{unit_index}.txt")
                output_path.write_text("ok", encoding="utf-8")

            pipeline = JobPipeline()
            pipeline.run(
                job_id="job-report",
                total_units=1,
                output_dir=output_dir,
                work=work,
                report_config=ProcessingReportConfig(
                    export_settings=export_settings,
                    model_name="Real-ESRGAN",
                    report_path=report_path,
                    scale=4,
                    tiling="Auto",
                    precision="FP16",
                    compute="GPU",
                ),
                report_clock=report_clock,
            )

            payload = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(payload["settings"]["band_handling"], "RGB + all bands")
        self.assertEqual(payload["settings"]["output_format"], "GeoTIFF")
        self.assertEqual(payload["settings"]["scale"], 4)
        self.assertEqual(payload["settings"]["tiling"], "Auto")
        self.assertEqual(payload["settings"]["precision"], "FP16")
        self.assertEqual(payload["settings"]["compute"], "GPU")
        self.assertEqual(payload["model"]["name"], "Real-ESRGAN")
        self.assertEqual(payload["model"]["version"], "v0.1.0")
        self.assertEqual(payload["timings"]["duration_ms"], 5000)
        self.assertEqual(payload["timings"]["started_at"], "2025-01-02T09:30:00Z")
        self.assertEqual(payload["timings"]["completed_at"], "2025-01-02T09:30:05Z")
