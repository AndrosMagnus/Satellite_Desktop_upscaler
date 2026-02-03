import unittest

from app.recommendation import HardwareProfile, SceneMetadata, recommend_model


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

        self.assertEqual(recommendation.model, "SRGAN adapted to EO")
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


if __name__ == "__main__":
    unittest.main()
