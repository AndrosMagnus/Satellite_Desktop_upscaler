import hashlib
import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from app.error_handling import UserFacingError
from app.model_installation import install_model


class TestModelInstallation(unittest.TestCase):
    @staticmethod
    def _fake_venv_create(_builder, env_dir: str | Path) -> None:
        env_path = Path(env_dir)
        env_path.mkdir(parents=True, exist_ok=True)
        (env_path / "pyvenv.cfg").write_text("home = /usr/bin/python3\n", encoding="utf-8")
        bin_dir = env_path / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        (bin_dir / python_name).write_text("", encoding="utf-8")

    def test_install_creates_venv_manifest_and_installs_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "data"
            weights_src = Path(tmpdir) / "weights.bin"
            weights_src.write_bytes(b"weights")
            checksum = hashlib.sha256(b"weights").hexdigest()
            dependencies = ["example==1.2.3"]

            with patch(
                "app.model_installation.venv.EnvBuilder.create",
                new=self._fake_venv_create,
            ), patch("app.model_installation.subprocess.run") as run, patch(
                "app.model_installation._run_dependency_check"
            ) as dep_check:
                dep_check.return_value = [
                    {
                        "name": "example",
                        "required": "1.2.3",
                        "installed": "1.2.3",
                        "status": "ok",
                    }
                ]
                result = install_model(
                    "Test Model",
                    "v1.0",
                    str(weights_src),
                    checksum=f"sha256:{checksum}",
                    dependencies=dependencies,
                    base_dir=base_dir,
                )
                run.assert_called_once()
                command = run.call_args[0][0]
                self.assertIn("-m", command)
                self.assertIn("pip", command)
                self.assertIn("install", command)
                self.assertIn("example==1.2.3", command)

            self.assertTrue(result.paths.weights.is_file())
            self.assertTrue((result.paths.venv / "pyvenv.cfg").is_file())
            manifest = json.loads(result.paths.manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["dependencies"], dependencies)
            self.assertEqual(manifest["health"]["status"], "ok")

    def test_install_requires_pinned_dependencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir) / "data"
            weights_src = Path(tmpdir) / "weights.bin"
            weights_src.write_bytes(b"weights")

            with patch(
                "app.model_installation.venv.EnvBuilder.create",
                new=self._fake_venv_create,
            ), self.assertRaises(UserFacingError):
                install_model(
                    "Test Model",
                    "v1.0",
                    str(weights_src),
                    dependencies=["numpy"],
                    base_dir=base_dir,
                )


if __name__ == "__main__":
    unittest.main()
