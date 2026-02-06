import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.model_installation import run_missing_health_checks


class TestModelHealthCheck(unittest.TestCase):
    def test_run_missing_health_checks_updates_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "data"
            model_root = base_dir / "models" / "test-model" / "v1"
            model_root.mkdir(parents=True)
            (model_root / "weights.bin").write_bytes(b"weights")
            venv_dir = model_root / "venv"
            venv_dir.mkdir()
            (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin/python3\n", encoding="utf-8")
            manifest_path = model_root / "manifest.json"
            manifest = {
                "name": "Test Model",
                "version": "v1",
                "weights_url": "file://weights.bin",
                "weights_filename": "weights.bin",
                "size_bytes": 7,
                "checksum": None,
                "dependencies": ["example==1.2.3"],
                "installed_at": "2024-01-01T00:00:00Z",
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            with patch("app.model_installation._run_dependency_check") as dep_check:
                dep_check.return_value = [
                    {
                        "name": "example",
                        "required": "1.2.3",
                        "installed": "1.2.3",
                        "status": "ok",
                    }
                ]
                results = run_missing_health_checks(base_dir=base_dir)

            self.assertEqual(len(results), 1)
            updated = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertIn("health", updated)
            self.assertEqual(updated["health"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
