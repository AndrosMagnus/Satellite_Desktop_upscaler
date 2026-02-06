import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

from app.validation import (
    SamplePair,
    compute_psnr,
    compute_ssim,
    evaluate_dataset,
    load_samples_from_manifest,
    write_preview_ppm,
)
from scripts import validate_eo_dataset


class TestValidationMetrics(unittest.TestCase):
    def test_psnr_ssim_identical(self) -> None:
        image = [[1.0, 2.0], [3.0, 4.0]]

        psnr = compute_psnr(image, image, data_range=4.0)
        ssim = compute_ssim(image, image, data_range=4.0)

        self.assertTrue(math.isinf(psnr))
        self.assertEqual(ssim, 1.0)

    def test_metrics_detect_difference(self) -> None:
        reference = [[0.0, 0.0], [0.0, 0.0]]
        prediction = [[0.0, 1.0], [1.0, 0.0]]

        psnr = compute_psnr(reference, prediction, data_range=1.0)
        ssim = compute_ssim(reference, prediction, data_range=1.0)

        self.assertLess(psnr, 100.0)
        self.assertLess(ssim, 1.0)

    def test_evaluate_dataset_averages(self) -> None:
        sample_a = SamplePair(
            name="a",
            reference=[[[0.0], [0.0]]],
            prediction=[[[0.0], [0.0]]],
        )
        sample_b = SamplePair(
            name="b",
            reference=[[[0.0], [1.0]]],
            prediction=[[[0.0], [0.0]]],
        )

        report = evaluate_dataset([sample_a, sample_b], data_range=1.0)

        self.assertEqual(len(report.samples), 2)
        expected_avg = (report.samples[0].psnr + report.samples[1].psnr) / 2
        self.assertAlmostEqual(report.average_psnr, expected_avg)

    def test_write_preview_ppm(self) -> None:
        reference = [[[0.0, 0.5, 1.0]]]
        prediction = [[[1.0, 0.5, 0.0]]]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "preview.ppm"
            write_preview_ppm(reference, prediction, output_path)

            contents = output_path.read_text(encoding="ascii").splitlines()
            self.assertEqual(contents[0], "P3")

    def test_load_samples_from_manifest_resolves_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reference_path = tmp_path / "ref.json"
            prediction_path = tmp_path / "pred.json"
            manifest_path = tmp_path / "manifest.json"

            reference_path.write_text(json.dumps([[1.0]]), encoding="utf-8")
            prediction_path.write_text(json.dumps([[1.0]]), encoding="utf-8")
            manifest_path.write_text(
                json.dumps(
                    [
                        {
                            "name": "sample",
                            "reference": "ref.json",
                            "prediction": "pred.json",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            samples = load_samples_from_manifest(manifest_path)

            self.assertEqual(samples[0].name, "sample")
            self.assertEqual(len(samples), 1)


class TestValidationCLI(unittest.TestCase):
    def test_sample_cli_generates_report_and_previews(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"
            original_argv = sys.argv
            sys.argv = [
                "validate_eo_dataset.py",
                "--sample",
                "--output",
                str(output_dir),
            ]
            try:
                exit_code = validate_eo_dataset.main()
            finally:
                sys.argv = original_argv

            self.assertEqual(exit_code, 0)
            report_path = output_dir / "report.json"
            self.assertTrue(report_path.exists())
            report_data = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("samples", report_data)
            sample_names = {sample["name"] for sample in report_data["samples"]}
            self.assertIn("sample_urban", sample_names)
            self.assertIn("sample_coastal", sample_names)
            for name in sample_names:
                preview_path = output_dir / f"{name}_preview.ppm"
                self.assertTrue(preview_path.exists())


if __name__ == "__main__":
    unittest.main()
