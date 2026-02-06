import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import validate_cloud_dataset


class TestCloudValidationCLI(unittest.TestCase):
    def test_sample_cli_generates_report_and_previews(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            original_argv = sys.argv
            sys.argv = [
                "validate_cloud_dataset.py",
                "--sample",
                "--output",
                str(output_dir),
            ]
            try:
                exit_code = validate_cloud_dataset.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            report_path = output_dir / "report.json"
            self.assertTrue(report_path.exists())
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("samples", report_data)
            sample_names = {sample["name"] for sample in report_data["samples"]}
            self.assertIn("cloud_bank", sample_names)
            self.assertIn("storm_cell", sample_names)
            for name in sample_names:
                preview_path = output_dir / f"{name}_preview.ppm"
                self.assertTrue(preview_path.exists())


if __name__ == "__main__":
    unittest.main()
