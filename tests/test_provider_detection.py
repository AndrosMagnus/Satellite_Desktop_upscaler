import unittest

from app.provider_detection import detect_provider


class TestProviderDetection(unittest.TestCase):
    def test_detects_sentinel(self) -> None:
        path = "/data/S2A_MSIL2A_20240107T101031.SAFE/GRANULE/L2A_T32TMT.tif"
        self.assertEqual(detect_provider(path), "Sentinel-2")

    def test_detects_planetscope(self) -> None:
        path = "/imagery/20240101_123456_12_45_3B_AnalyticMS_PSScene.tif"
        self.assertEqual(detect_provider(path), "PlanetScope")

    def test_detects_vantor(self) -> None:
        path = "/exports/Vantor_WorldView-3_WV03_RGB_2023-11-02.tif"
        self.assertEqual(detect_provider(path), "Vantor")

    def test_detects_21at(self) -> None:
        path = "/exports/21AT_TripleSat_TSAT_2022_04_19.tif"
        self.assertEqual(detect_provider(path), "21AT")

    def test_detects_landsat(self) -> None:
        path = "/landsat/LC08_L1TP_012034_20200715_20200808_01_T1.tif"
        self.assertEqual(detect_provider(path), "Landsat")

    def test_returns_none_when_unknown(self) -> None:
        path = "/exports/scene_foo_bar_2024.tif"
        self.assertIsNone(detect_provider(path))


if __name__ == "__main__":
    unittest.main()
