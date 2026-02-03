import unittest
from pathlib import Path


class TestRepoConventionsDoc(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.doc_path = repo_root / "docs" / "repo_conventions.md"

    def test_repo_conventions_doc_exists(self) -> None:
        self.assertTrue(
            self.doc_path.is_file(),
            "docs/repo_conventions.md is missing",
        )

    def test_repo_conventions_doc_contains_required_sections(self) -> None:
        content = self.doc_path.read_text(encoding="utf-8")

        expected_markers = [
            "## Logging",
            "JSON lines",
            "ISO 8601",
            "logs/app.log",
            "## Error Handling",
            "User-Facing",
            "Error Codes",
            "## Configuration",
            "config.json",
            "schema_version",
        ]

        missing = [marker for marker in expected_markers if marker not in content]
        self.assertEqual(missing, [], f"Missing conventions markers: {missing}")


if __name__ == "__main__":
    unittest.main()
