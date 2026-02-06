import os
import tempfile
import unittest
from pathlib import Path

from app.model_entrypoints import build_model_wrapper, resolve_model_entrypoint
from app.model_installation import resolve_install_paths


class TestModelEntrypoints(unittest.TestCase):
    def _create_venv(self, venv_dir: Path) -> None:
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin/python3\n", encoding="utf-8")
        bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        python_path = bin_dir / python_name
        python_path.write_text("", encoding="utf-8")

    def test_satellitesr_entrypoint_resolves(self) -> None:
        entrypoint = resolve_model_entrypoint("SatelliteSR")
        self.assertIsNotNone(entrypoint, "SatelliteSR entrypoint must be registered")
        path = Path(entrypoint)
        self.assertTrue(path.is_file(), "SatelliteSR entrypoint must exist on disk")

    def test_srgan_eo_entrypoint_resolves(self) -> None:
        entrypoint = resolve_model_entrypoint("SRGAN adapted to EO")
        self.assertIsNotNone(entrypoint, "SRGAN adapted to EO entrypoint must be registered")
        path = Path(entrypoint)
        self.assertTrue(path.is_file(), "SRGAN adapted to EO entrypoint must exist on disk")

    def test_build_model_wrapper_uses_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            paths = resolve_install_paths("SatelliteSR", "v1", base_dir=base_dir)
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.manifest.write_text("{}", encoding="utf-8")
            paths.weights.write_bytes(b"weights")
            self._create_venv(paths.venv)

            wrapper = build_model_wrapper("SatelliteSR", "v1", base_dir=base_dir)
            self.assertEqual(wrapper.name, "SatelliteSR")
            self.assertEqual(wrapper.version, "v1")
            self.assertTrue(Path(wrapper.entrypoint).is_file())

    def test_build_srgan_wrapper_uses_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            paths = resolve_install_paths("SRGAN adapted to EO", "v1", base_dir=base_dir)
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.manifest.write_text("{}", encoding="utf-8")
            paths.weights.write_bytes(b"weights")
            self._create_venv(paths.venv)

            wrapper = build_model_wrapper("SRGAN adapted to EO", "v1", base_dir=base_dir)
            self.assertEqual(wrapper.name, "SRGAN adapted to EO")
            self.assertEqual(wrapper.version, "v1")
            self.assertTrue(Path(wrapper.entrypoint).is_file())


if __name__ == "__main__":
    unittest.main()
