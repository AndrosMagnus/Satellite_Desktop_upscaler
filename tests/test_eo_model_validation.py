import json
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import validate_eo_models


class TestEoModelValidationCLI(unittest.TestCase):
    def test_sample_cli_generates_reports_for_each_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            original_argv = sys.argv
            sys.argv = [
                "validate_eo_models.py",
                "--sample",
                "--output",
                str(output_dir),
            ]
            try:
                exit_code = validate_eo_models.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            for model in validate_eo_models.DEFAULT_SAMPLE_MODELS:
                model_dir = output_dir / validate_eo_models._slugify(model)
                report_path = model_dir / "report.json"
                self.assertTrue(report_path.exists())
                report_data = json.loads(report_path.read_text(encoding="utf-8"))
                self.assertEqual(report_data.get("model"), model)
                sample_names = {sample["name"] for sample in report_data.get("samples", [])}
                self.assertIn("sample_urban", sample_names)
                self.assertIn("sample_coastal", sample_names)
                for name in sample_names:
                    preview_path = model_dir / f"{name}_preview.ppm"
                    self.assertTrue(preview_path.exists())


if __name__ == "__main__":
    unittest.main()
