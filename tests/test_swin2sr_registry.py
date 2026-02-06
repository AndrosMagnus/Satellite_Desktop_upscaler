import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


class TestSwin2SRRegistryEntry(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.repo_root = repo_root
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_swin2sr(self) -> dict[str, object]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data:
            if isinstance(entry, dict) and entry.get("name") == "Swin2SR":
                return entry
        raise AssertionError("Swin2SR model entry missing from registry")

    def test_swin2sr_weights_available(self) -> None:
        swin2sr = self._load_swin2sr()
        weights_url = str(swin2sr.get("weights_url", "")).strip()
        self.assertTrue(weights_url, "Swin2SR weights_url must not be empty")
        self.assertNotEqual(weights_url.upper(), "TBD", "Swin2SR weights_url must be defined")

        parsed = urlparse(weights_url)
        if parsed.scheme in ("", "file"):
            path = Path(parsed.path) if parsed.scheme == "file" else Path(weights_url)
            if not path.is_absolute():
                path = self.repo_root / path
            self.assertTrue(path.is_file(), "Swin2SR weights file must exist")

    def test_swin2sr_dependencies_are_pinned(self) -> None:
        swin2sr = self._load_swin2sr()
        dependencies = swin2sr.get("dependencies", [])
        self.assertIsInstance(dependencies, list, "Swin2SR dependencies must be a list")
        self.assertGreater(len(dependencies), 0, "Swin2SR dependencies must be populated")
        for dep in dependencies:
            self.assertIsInstance(dep, str, "Swin2SR dependency entries must be strings")
            pinned = "==" in dep or "@" in dep or dep.endswith(".whl") or dep.startswith("file:")
            self.assertTrue(pinned, f"Swin2SR dependency '{dep}' must be pinned")


if __name__ == "__main__":
    unittest.main()
