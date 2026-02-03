import unittest
from pathlib import Path


class TestTechStackDoc(unittest.TestCase):
    def test_tech_stack_doc_exists(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tech_stack_doc = repo_root / "docs" / "tech_stack.md"
        self.assertTrue(tech_stack_doc.is_file(), "docs/tech_stack.md is missing")

    def test_tech_stack_doc_contains_core_choices(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        tech_stack_doc = repo_root / "docs" / "tech_stack.md"
        content = tech_stack_doc.read_text(encoding="utf-8")

        expected_markers = [
            "Python 3.11",
            "PySide6",
            "PyTorch",
            "Rasterio",
            "GDAL",
            "PyInstaller",
        ]

        missing = [marker for marker in expected_markers if marker not in content]
        self.assertEqual(missing, [], f"Missing stack markers in doc: {missing}")


if __name__ == "__main__":
    unittest.main()
