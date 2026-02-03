import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.band_handling import BandHandling, ExportSettings
from app.processing_report import (
    ProcessingTimings,
    build_processing_report,
    export_processing_report,
    resolve_model_version,
)


class TestProcessingReport(unittest.TestCase):
    def test_processing_report_export_writes_expected_payload(self) -> None:
        export_settings = ExportSettings(
            band_handling=BandHandling.RGB_ONLY,
            output_format="Match input",
        )
        start = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end = start + timedelta(seconds=12)
        timings = ProcessingTimings.from_datetimes(start, end)

        report = build_processing_report(
            export_settings=export_settings,
            model_name="Real-ESRGAN",
            timings=timings,
            scale=4,
            tiling="Auto",
            precision="FP16",
            compute="GPU",
        )

        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "report.json"
            export_processing_report(report, path)
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["settings"]["band_handling"], "RGB only")
        self.assertEqual(payload["settings"]["output_format"], "Match input")
        self.assertEqual(payload["settings"]["scale"], 4)
        self.assertEqual(payload["settings"]["tiling"], "Auto")
        self.assertEqual(payload["settings"]["precision"], "FP16")
        self.assertEqual(payload["settings"]["compute"], "GPU")
        self.assertEqual(payload["model"]["name"], "Real-ESRGAN")
        self.assertEqual(payload["model"]["version"], "v0.1.0")
        self.assertEqual(payload["timings"]["duration_ms"], 12000)
        self.assertEqual(payload["timings"]["started_at"], "2025-01-01T12:00:00Z")
        self.assertEqual(payload["timings"]["completed_at"], "2025-01-01T12:00:12Z")

    def test_resolve_model_version_returns_unknown_when_missing(self) -> None:
        self.assertEqual(resolve_model_version("SatelliteSR"), "Unknown")


if __name__ == "__main__":
    unittest.main()
