import json
import unittest
from pathlib import Path


class TestModelSupportedInputs(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_registry(self) -> list[dict[str, object]]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, list):
            return []
        return [entry for entry in data if isinstance(entry, dict)]

    def test_satlas_supports_sentinel2_and_naip(self) -> None:
        registry = self._load_registry()
        satlas = next(
            (entry for entry in registry if entry.get("name") == "Satlas"), None
        )
        self.assertIsNotNone(satlas, "Satlas model entry missing from registry")
        bands = satlas.get("bands_supported") if isinstance(satlas, dict) else None
        self.assertIsInstance(bands, list, "Satlas bands_supported must be a list")
        self.assertIn("Sentinel-2", bands)
        self.assertIn("NAIP", bands)


if __name__ == "__main__":
    unittest.main()
