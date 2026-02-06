import unittest

from app.recommendation import (
    HardwareProfile,
    ModelOverrides,
    SceneMetadata,
    _select_scale,
    recommend_model,
    recommend_model_with_overrides,
)


class TestRecommendationEngine(unittest.TestCase):
    def test_sentinel_multispectral_prefers_s2dr3(self) -> None:
        scene = SceneMetadata(provider="Sentinel-2", band_count=13, resolution_m=10.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "S2DR3")
        self.assertEqual(recommendation.scale, 4)
        self.assertFalse(recommendation.tiling)
        self.assertEqual(recommendation.precision, "fp16")

    def test_sentinel_rgb_low_vram_uses_tiling(self) -> None:
        scene = SceneMetadata(provider="Sentinel-2", band_count=3, resolution_m=10.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=2, ram_gb=32)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "Satlas")
        self.assertTrue(recommendation.tiling)
        self.assertEqual(recommendation.precision, "fp32")
        self.assertTrue(
            any("VRAM below minimum" in warning for warning in recommendation.warnings)
        )

    def test_planetscope_multispectral_prefers_srgan(self) -> None:
        scene = SceneMetadata(provider="PlanetScope", band_count=4, resolution_m=3.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=10, ram_gb=32)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "SRGAN adapted to EO")
        self.assertEqual(recommendation.scale, 4)
        self.assertFalse(recommendation.tiling)

    def test_landsat_multispectral_experimental_warning(self) -> None:
        scene = SceneMetadata(provider="Landsat", band_count=7, resolution_m=30.0)
        hardware = HardwareProfile(gpu_available=False, vram_gb=0, ram_gb=16)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "LDSR-S2")
        self.assertTrue(recommendation.tiling)
        self.assertTrue(
            any("GPU not detected" in warning for warning in recommendation.warnings)
        )
        self.assertTrue(
            any("experimental" in warning for warning in recommendation.warnings)
        )

    def test_planetscope_rgb_prefers_swinir(self) -> None:
        scene = SceneMetadata(provider="PlanetScope", band_count=3, resolution_m=3.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=10, ram_gb=32)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "SwinIR")

    def test_vantor_high_resolution_warning(self) -> None:
        scene = SceneMetadata(provider="Vantor", band_count=3, resolution_m=0.3)
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)

        recommendation = recommend_model(scene, hardware)

        self.assertEqual(recommendation.model, "SatelliteSR")
        self.assertEqual(recommendation.scale, 2)
        self.assertTrue(
            any("high resolution" in warning for warning in recommendation.warnings)
        )

    def test_default_scale_when_resolution_unknown(self) -> None:
        self.assertEqual(_select_scale(None, "SEN2SR"), 2)

    def test_override_warnings_for_model_and_options(self) -> None:
        scene = SceneMetadata(provider="Sentinel-2", band_count=13, resolution_m=10.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)
        overrides = ModelOverrides(
            model="Real-ESRGAN",
            scale=2,
            tiling=True,
            precision="fp32",
        )

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertEqual(recommendation.model, "Real-ESRGAN")
        self.assertEqual(recommendation.scale, 2)
        self.assertTrue(recommendation.tiling)
        self.assertEqual(recommendation.precision, "fp32")
        self.assertTrue(
            any(
                "overrides recommended model" in warning
                for warning in recommendation.warnings
            )
        )
        self.assertTrue(
            any(
                "Scale 2x overrides recommended 4x" in warning
                for warning in recommendation.warnings
            )
        )
        self.assertTrue(
            any(
                "Tiling override set to enabled" in warning
                for warning in recommendation.warnings
            )
        )
        self.assertTrue(
            any(
                "Precision override fp32 replaces recommended fp16" in warning
                for warning in recommendation.warnings
            )
        )

    def test_unsupported_scale_override_keeps_recommendation(self) -> None:
        scene = SceneMetadata(provider="Sentinel-2", band_count=13, resolution_m=10.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=8, ram_gb=32)
        overrides = ModelOverrides(scale=8)

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertEqual(recommendation.scale, 4)
        self.assertTrue(
            any(
                "Scale 8x is not supported" in warning
                for warning in recommendation.warnings
            )
        )

    def test_compute_override_cpu_disables_gpu(self) -> None:
        scene = SceneMetadata(provider="PlanetScope", band_count=3, resolution_m=3.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=10, ram_gb=32)
        overrides = ModelOverrides(compute_mode="CPU")

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertTrue(recommendation.tiling)
        self.assertTrue(
            any(
                "Compute override set to CPU" in warning
                for warning in recommendation.warnings
            )
        )

    def test_compute_override_gpu_when_detection_missing(self) -> None:
        scene = SceneMetadata(provider="Landsat", band_count=7, resolution_m=30.0)
        hardware = HardwareProfile(gpu_available=False, vram_gb=0, ram_gb=16)
        overrides = ModelOverrides(compute_mode="GPU")

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertTrue(
            any(
                "Compute override set to GPU" in warning
                for warning in recommendation.warnings
            )
        )

    def test_safe_mode_forces_cpu_and_conservative_defaults(self) -> None:
        scene = SceneMetadata(provider="PlanetScope", band_count=3, resolution_m=3.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=10, ram_gb=32)
        overrides = ModelOverrides(safe_mode=True)

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertEqual(recommendation.scale, 2)
        self.assertTrue(recommendation.tiling)
        self.assertEqual(recommendation.precision, "fp32")
        self.assertTrue(
            any("Safe mode enabled" in warning for warning in recommendation.warnings)
        )
        self.assertTrue(
            any(
                "Compute override set to CPU" in warning
                for warning in recommendation.warnings
            )
        )

    def test_safe_mode_ignores_advanced_overrides(self) -> None:
        scene = SceneMetadata(provider="PlanetScope", band_count=3, resolution_m=3.0)
        hardware = HardwareProfile(gpu_available=True, vram_gb=10, ram_gb=32)
        overrides = ModelOverrides(
            scale=4,
            tiling=False,
            precision="fp16",
            compute_mode="GPU",
            safe_mode=True,
        )

        recommendation = recommend_model_with_overrides(scene, hardware, overrides)

        self.assertEqual(recommendation.scale, 2)
        self.assertTrue(recommendation.tiling)
        self.assertEqual(recommendation.precision, "fp32")


if __name__ == "__main__":
    unittest.main()
