import unittest

from scripts.hardware_targets import get_hardware_targets


class TestHardwareTargets(unittest.TestCase):
    def test_hardware_targets_minimums(self) -> None:
        targets = get_hardware_targets()

        self.assertEqual(
            targets.minimum_ram_gb,
            16,
            "Expected minimum RAM target to be 16 GB",
        )
        self.assertEqual(
            targets.minimum_vram_gb,
            6,
            "Expected minimum VRAM target to be 6 GB",
        )

    def test_cpu_fallback_expectations(self) -> None:
        targets = get_hardware_targets()

        self.assertIn(
            "Real-ESRGAN",
            targets.cpu_fallback.validated_models,
            "Expected Real-ESRGAN to be validated on CPU",
        )
        self.assertTrue(
            any("CPU mode is available" in note for note in targets.cpu_fallback.notes),
            "Expected CPU fallback notes to mention CPU mode availability",
        )


if __name__ == "__main__":
    unittest.main()
