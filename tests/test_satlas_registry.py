import json
import unittest
from pathlib import Path


class TestSatlasRegistryEntry(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_satlas(self) -> dict[str, object]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data:
            if isinstance(entry, dict) and entry.get("name") == "Satlas":
                return entry
        raise AssertionError("Satlas model entry missing from registry")

    def test_satlas_weights_available(self) -> None:
        satlas = self._load_satlas()
        weights_url = str(satlas.get("weights_url", "")).strip()
        self.assertTrue(weights_url, "Satlas weights_url must not be empty")
        self.assertNotEqual(weights_url.upper(), "TBD", "Satlas weights_url must be defined")

    def test_satlas_dependencies_are_pinned(self) -> None:
        satlas = self._load_satlas()
        dependencies = satlas.get("dependencies", [])
        self.assertIsInstance(dependencies, list, "Satlas dependencies must be a list")
        self.assertGreater(len(dependencies), 0, "Satlas dependencies must be populated")
        for dep in dependencies:
            self.assertIsInstance(dep, str, "Satlas dependency entries must be strings")
            self.assertIn("==", dep, f"Satlas dependency '{dep}' must be pinned with ==")


if __name__ == "__main__":
    unittest.main()
