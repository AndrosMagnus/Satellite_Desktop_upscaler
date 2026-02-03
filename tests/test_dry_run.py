import unittest

from app.dry_run import DryRunEstimate, estimate_dry_run
from app.recommendation import HardwareProfile


class TestDryRunEstimator(unittest.TestCase):
    def test_gpu_estimate_increases_with_scale(self) -> None:
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        estimate_2x = estimate_dry_run(
            width=1024,
            height=1024,
            band_count=3,
            scale=2,
            model="Real-ESRGAN",
            precision="fp16",
            tiling=False,
            hardware=hardware,
        )
        estimate_4x = estimate_dry_run(
            width=1024,
            height=1024,
            band_count=3,
            scale=4,
            model="Real-ESRGAN",
            precision="fp16",
            tiling=False,
            hardware=hardware,
        )

        self.assertIsInstance(estimate_2x, DryRunEstimate)
        self.assertGreater(estimate_4x.runtime_seconds, estimate_2x.runtime_seconds)
        self.assertGreater(estimate_4x.vram_gb, estimate_2x.vram_gb)

    def test_cpu_estimate_returns_zero_vram(self) -> None:
        hardware = HardwareProfile(gpu_available=False, vram_gb=0, ram_gb=16)

        estimate = estimate_dry_run(
            width=512,
            height=512,
            band_count=4,
            scale=2,
            model="S2DR3",
            precision="fp32",
            tiling=True,
            hardware=hardware,
        )

        self.assertEqual(estimate.vram_gb, 0.0)
        self.assertTrue(
            any("GPU not detected" in note for note in estimate.notes)
        )

    def test_invalid_precision_falls_back(self) -> None:
        hardware = HardwareProfile(gpu_available=True, vram_gb=6, ram_gb=16)

        estimate = estimate_dry_run(
            width=256,
            height=256,
            band_count=3,
            scale=2,
            model="Satlas",
            precision="invalid",
            tiling=False,
            hardware=hardware,
        )

        self.assertTrue(
            any("Precision override invalid" in note for note in estimate.notes)
        )
        self.assertGreater(estimate.vram_gb, 0.0)

    def test_tiling_reduces_vram(self) -> None:
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        no_tiling = estimate_dry_run(
            width=4096,
            height=4096,
            band_count=3,
            scale=2,
            model="SwinIR",
            precision="fp16",
            tiling=False,
            hardware=hardware,
        )
        with_tiling = estimate_dry_run(
            width=4096,
            height=4096,
            band_count=3,
            scale=2,
            model="SwinIR",
            precision="fp16",
            tiling=True,
            hardware=hardware,
        )

        self.assertGreater(no_tiling.vram_gb, with_tiling.vram_gb)
        self.assertGreater(with_tiling.runtime_seconds, 0.0)


if __name__ == "__main__":
    unittest.main()
