import unittest

from scripts.build_targets import get_supported_os_targets


class TestBuildTargets(unittest.TestCase):
    def test_supported_os_targets(self) -> None:
        targets = get_supported_os_targets()

        self.assertEqual(
            targets["windows"].minimum_version,
            "10",
            "Expected Windows minimum version to be 10",
        )
        self.assertEqual(
            targets["macos"].minimum_version,
            "12",
            "Expected macOS minimum version to be 12",
        )
        self.assertEqual(
            targets["ubuntu"].minimum_version,
            "20.04",
            "Expected Ubuntu minimum version to be 20.04",
        )


if __name__ == "__main__":
    unittest.main()
