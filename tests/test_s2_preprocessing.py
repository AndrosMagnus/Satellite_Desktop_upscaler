import unittest


class TestS2Preprocessing(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import numpy as np
        except ImportError as exc:
            self.skipTest(f"numpy not available: {exc}")
        self.np = np

    def test_scales_reflectance_range(self) -> None:
        np = self.np
        from app.model_wrappers.s2_sr_wrapper import _preprocess_s2_array

        array = np.array(
            [
                [[0.0, 5000.0], [10000.0, 2500.0]],
                [[7500.0, 2500.0], [5000.0, 0.0]],
            ],
            dtype="float32",
        )
        processed, scaled = _preprocess_s2_array(array)

        self.assertTrue(scaled)
        self.assertAlmostEqual(float(processed.max()), 1.0, places=6)
        self.assertAlmostEqual(float(processed[0, 0, 1]), 0.5, places=6)

    def test_keeps_normalized_values(self) -> None:
        np = self.np
        from app.model_wrappers.s2_sr_wrapper import _preprocess_s2_array

        array = np.array([[[0.1, 0.5, 1.0]]], dtype="float32")
        processed, scaled = _preprocess_s2_array(array)

        self.assertFalse(scaled)
        self.assertAlmostEqual(float(processed[0, 0, 1]), 0.5, places=6)

    def test_clips_invalid_values(self) -> None:
        np = self.np
        from app.model_wrappers.s2_sr_wrapper import _preprocess_s2_array

        array = np.array([[[-1.0, np.nan, np.inf]]], dtype="float32")
        processed, scaled = _preprocess_s2_array(array)

        self.assertFalse(scaled)
        self.assertAlmostEqual(float(processed.min()), 0.0, places=6)
        self.assertAlmostEqual(float(processed.max()), 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
