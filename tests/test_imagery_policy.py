import unittest

from app.imagery_policy import (
    RgbBandMapping,
    build_output_plan,
    default_rgb_mapping,
    model_supports_dataset,
)


class TestImageryPolicy(unittest.TestCase):
    def test_dual_output_for_geospatial_to_png(self) -> None:
        plan = build_output_plan("GeoTIFF", "PNG")
        self.assertEqual(plan.master_format, "GeoTIFF")
        self.assertEqual(plan.visual_format, "PNG")
        self.assertTrue(plan.critical_warnings)

    def test_match_input_preserves_single_output(self) -> None:
        plan = build_output_plan("JP2", "Match input")
        self.assertEqual(plan.master_format, "JP2")
        self.assertIsNone(plan.visual_format)
        self.assertEqual(plan.critical_warnings, ())

    def test_default_rgb_mappings(self) -> None:
        sentinel = default_rgb_mapping("Sentinel-2", 13)
        self.assertEqual(sentinel, RgbBandMapping(3, 2, 1, sentinel.source))

        planet = default_rgb_mapping("PlanetScope", 4)
        self.assertEqual(planet, RgbBandMapping(2, 1, 0, planet.source))

        unknown = default_rgb_mapping("Unknown", 5)
        self.assertIsNone(unknown)

    def test_model_multispectral_support(self) -> None:
        support = {
            "S2DR3": ("Sentinel-2",),
            "Real-ESRGAN": ("RGB",),
            "SatelliteSR": ("RGB", "Sentinel-2"),
        }
        self.assertTrue(
            model_supports_dataset(
                "S2DR3", "Sentinel-2", 13, band_support=support
            )
        )
        self.assertFalse(
            model_supports_dataset(
                "Real-ESRGAN", "Sentinel-2", 13, band_support=support
            )
        )
        self.assertTrue(
            model_supports_dataset(
                "SatelliteSR", "Sentinel-2", 13, band_support=support
            )
        )


if __name__ == "__main__":
    unittest.main()
