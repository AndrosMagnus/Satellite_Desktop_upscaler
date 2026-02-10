import tempfile
import unittest
from pathlib import Path

from app.validation import EvaluationReport, SampleMetrics
from app.validation_baselines import (
    ValidationThreshold,
    evaluate_threshold,
    load_validation_baselines,
    resolve_threshold,
)


class TestValidationBaselines(unittest.TestCase):
    def test_load_and_resolve_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "baseline.json"
            path.write_text(
                '{"datasets":{"eo":{"default":{"psnr_min":25.0,"ssim_min":0.8},'
                '"models":{"SatelliteSR":{"psnr_min":27.0,"ssim_min":0.82}}}}}',
                encoding="utf-8",
            )
            baselines = load_validation_baselines(path)

        threshold = resolve_threshold(baselines, dataset="eo", model="SatelliteSR")
        self.assertEqual(threshold, ValidationThreshold(psnr_min=27.0, ssim_min=0.82))
        default_threshold = resolve_threshold(baselines, dataset="eo", model="Missing")
        self.assertEqual(
            default_threshold,
            ValidationThreshold(psnr_min=25.0, ssim_min=0.8),
        )

    def test_evaluate_threshold(self) -> None:
        report = EvaluationReport(
            samples=(SampleMetrics("a", 30.0, 0.91, 16, 16, 3),),
            average_psnr=30.0,
            average_ssim=0.91,
        )
        pass_result = evaluate_threshold(
            report, ValidationThreshold(psnr_min=29.0, ssim_min=0.9)
        )
        self.assertTrue(pass_result.passed)

        fail_result = evaluate_threshold(
            report, ValidationThreshold(psnr_min=31.0, ssim_min=0.95)
        )
        self.assertFalse(fail_result.passed)
        self.assertEqual(len(fail_result.issues), 2)


if __name__ == "__main__":
    unittest.main()
