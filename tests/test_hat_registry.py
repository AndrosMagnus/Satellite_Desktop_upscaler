import json
import unittest
from pathlib import Path
from urllib.parse import urlparse


class TestHATRegistryEntry(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self.repo_root = repo_root
        self.registry_path = repo_root / "models" / "registry.json"

    def _load_hat(self) -> dict[str, object]:
        with self.registry_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        for entry in data:
            if isinstance(entry, dict) and entry.get("name") == "HAT":
                return entry
        raise AssertionError("HAT model entry missing from registry")

    def test_hat_weights_available(self) -> None:
        hat = self._load_hat()
        weights_url = str(hat.get("weights_url", "")).strip()
        self.assertTrue(weights_url, "HAT weights_url must not be empty")
        self.assertNotEqual(weights_url.upper(), "TBD", "HAT weights_url must be defined")

        parsed = urlparse(weights_url)
        if parsed.scheme in ("", "file"):
            path = Path(parsed.path) if parsed.scheme == "file" else Path(weights_url)
            if not path.is_absolute():
                path = self.repo_root / path
            self.assertTrue(path.is_file(), "HAT weights file must exist")

    def test_hat_dependencies_are_pinned(self) -> None:
        hat = self._load_hat()
        dependencies = hat.get("dependencies", [])
        self.assertIsInstance(dependencies, list, "HAT dependencies must be a list")
        self.assertGreater(len(dependencies), 0, "HAT dependencies must be populated")
        for dep in dependencies:
            self.assertIsInstance(dep, str, "HAT dependency entries must be strings")
            pinned = "==" in dep or "@" in dep or dep.endswith(".whl") or dep.startswith("file:")
            self.assertTrue(pinned, f"HAT dependency '{dep}' must be pinned")


if __name__ == "__main__":
    unittest.main()
