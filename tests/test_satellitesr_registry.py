import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


class TestSatelliteSRRegistryEntry(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.repo_root = repo_root
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_satellitesr(self) -> dict[str, object]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data:
            if isinstance(entry, dict) and entry.get("name") == "SatelliteSR":
                return entry
        raise AssertionError("SatelliteSR model entry missing from registry")

    def test_satellitesr_weights_available(self) -> None:
        satellitesr = self._load_satellitesr()
        weights_url = str(satellitesr.get("weights_url", "")).strip()
        self.assertTrue(weights_url, "SatelliteSR weights_url must not be empty")
        self.assertNotEqual(weights_url.upper(), "TBD", "SatelliteSR weights_url must be defined")

        parsed = urlparse(weights_url)
        if parsed.scheme in ("", "file"):
            path = Path(parsed.path) if parsed.scheme == "file" else Path(weights_url)
            if not path.is_absolute():
                path = self.repo_root / path
            self.assertTrue(path.is_file(), "SatelliteSR weights file must exist")

    def test_satellitesr_dependencies_are_pinned(self) -> None:
        satellitesr = self._load_satellitesr()
        dependencies = satellitesr.get("dependencies", [])
        self.assertIsInstance(dependencies, list, "SatelliteSR dependencies must be a list")
        self.assertGreater(len(dependencies), 0, "SatelliteSR dependencies must be populated")
        for dep in dependencies:
            self.assertIsInstance(dep, str, "SatelliteSR dependency entries must be strings")
            pinned = "==" in dep or "@" in dep or dep.endswith(".whl") or dep.startswith("file:")
            self.assertTrue(pinned, f"SatelliteSR dependency '{dep}' must be pinned")


if __name__ == "__main__":
    unittest.main()
