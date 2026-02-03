import unittest
from pathlib import Path


class TestRepoStructure(unittest.TestCase):
    def test_baseline_folders_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        required = ["app", "backend", "models", "docs", "scripts", "tests"]

        missing = [name for name in required if not (root / name).is_dir()]

        self.assertEqual(missing, [], f"Missing directories: {missing}")


if __name__ == "__main__":
    unittest.main()
