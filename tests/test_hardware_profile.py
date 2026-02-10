import unittest
from unittest import mock

from app.hardware_profile import detect_hardware_profile


class TestHardwareProfile(unittest.TestCase):
    def test_detect_profile_uses_detected_values(self) -> None:
        with (
            mock.patch("app.hardware_profile._gpu_detected", return_value=True),
            mock.patch("app.hardware_profile._detect_vram_gb", return_value=12),
            mock.patch("app.hardware_profile._detect_ram_gb", return_value=32),
        ):
            profile = detect_hardware_profile()

        self.assertTrue(profile.gpu_available)
        self.assertEqual(profile.vram_gb, 12)
        self.assertEqual(profile.ram_gb, 32)

    def test_detect_profile_falls_back_to_targets(self) -> None:
        targets = mock.Mock(minimum_vram_gb=6, minimum_ram_gb=16)
        with (
            mock.patch("app.hardware_profile._gpu_detected", return_value=True),
            mock.patch("app.hardware_profile._detect_vram_gb", return_value=0),
            mock.patch("app.hardware_profile._detect_ram_gb", return_value=0),
            mock.patch("app.hardware_profile.get_hardware_targets", return_value=targets),
        ):
            profile = detect_hardware_profile()

        self.assertTrue(profile.gpu_available)
        self.assertEqual(profile.vram_gb, 6)
        self.assertEqual(profile.ram_gb, 16)

    def test_detect_profile_without_gpu(self) -> None:
        with (
            mock.patch("app.hardware_profile._gpu_detected", return_value=False),
            mock.patch("app.hardware_profile._detect_ram_gb", return_value=24),
        ):
            profile = detect_hardware_profile()

        self.assertFalse(profile.gpu_available)
        self.assertEqual(profile.vram_gb, 0)
        self.assertEqual(profile.ram_gb, 24)


if __name__ == "__main__":
    unittest.main()
