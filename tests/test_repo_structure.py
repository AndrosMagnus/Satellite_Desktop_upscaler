import unittest
from pathlib import Path


class TestRepoStructure(unittest.TestCase):
    def test_baseline_directories_exist(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        expected_dirs = [
            repo_root / "app",
            repo_root / "backend",
            repo_root / "models",
            repo_root / "docs",
            repo_root / "scripts",
            repo_root / "tests",
        ]

        missing = [path.name for path in expected_dirs if not path.is_dir()]
        self.assertEqual(missing, [], f"Missing baseline directories: {missing}")

    def test_placeholder_files_present_in_empty_dirs(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        placeholder_dirs = [
            repo_root / "app",
            repo_root / "models",
            repo_root / "docs",
        ]

        missing_placeholders = [
            path.name
            for path in placeholder_dirs
            if not (path / ".gitkeep").is_file()
        ]
        self.assertEqual(
            missing_placeholders,
            [],
            f"Missing .gitkeep files in: {missing_placeholders}",
        )


if __name__ == "__main__":
    unittest.main()
