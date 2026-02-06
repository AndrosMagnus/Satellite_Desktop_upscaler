import unittest

from app.run_settings import (
    parse_compute,
    parse_precision,
    parse_scale,
    parse_tiling,
)


class TestRunSettingsParsing(unittest.TestCase):
    def test_parse_scale(self) -> None:
        self.assertIsNone(parse_scale("Auto"))
        self.assertIsNone(parse_scale(""))
        self.assertEqual(parse_scale("2x"), 2)
        self.assertEqual(parse_scale(" 4x "), 4)

    def test_parse_tiling(self) -> None:
        self.assertIsNone(parse_tiling("Auto"))
        self.assertIsNone(parse_tiling(""))
        self.assertEqual(parse_tiling("512 px"), "512 px")

    def test_parse_precision(self) -> None:
        self.assertIsNone(parse_precision("Auto"))
        self.assertIsNone(parse_precision(""))
        self.assertEqual(parse_precision("FP16"), "FP16")
        self.assertEqual(parse_precision(" fp32 "), "FP32")

    def test_parse_compute(self) -> None:
        self.assertIsNone(parse_compute("Auto"))
        self.assertIsNone(parse_compute(""))
        self.assertEqual(parse_compute("GPU"), "GPU")
        self.assertEqual(parse_compute(" cpu "), "CPU")


if __name__ == "__main__":
    unittest.main()
