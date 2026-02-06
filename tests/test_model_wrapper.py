import os
import tempfile
import unittest
from pathlib import Path

from app.error_handling import UserFacingError
from app.model_installation import resolve_install_paths
from app.model_wrapper import ModelWrapper


class TestModelWrapper(unittest.TestCase):
    def _create_venv(self, venv_dir: Path) -> Path:
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / "pyvenv.cfg").write_text("home = /usr/bin/python3\n", encoding="utf-8")
        bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        python_path = bin_dir / python_name
        python_path.write_text("", encoding="utf-8")
        return python_path

    def test_from_installation_requires_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            paths = resolve_install_paths("Test Model", "v1", base_dir=base_dir)
            paths.root.mkdir(parents=True, exist_ok=True)

            with self.assertRaises(UserFacingError) as ctx:
                ModelWrapper.from_installation(
                    "Test Model",
                    "v1",
                    entrypoint="model_runner",
                    base_dir=base_dir,
                )

            self.assertEqual(ctx.exception.error_code, "MODEL-009")

    def test_from_installation_loads_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            paths = resolve_install_paths("Test Model", "v1", base_dir=base_dir)
            paths.root.mkdir(parents=True, exist_ok=True)
            paths.manifest.write_text("{}", encoding="utf-8")
            paths.weights.write_bytes(b"weights")
            python_path = self._create_venv(paths.venv)

            wrapper = ModelWrapper.from_installation(
                "Test Model",
                "v1",
                entrypoint="model_runner",
                base_dir=base_dir,
            )

            self.assertEqual(wrapper.weights_path, paths.weights)
            self.assertEqual(wrapper.venv_dir, paths.venv)
            self.assertEqual(wrapper.python_executable, python_path)


if __name__ == "__main__":
    unittest.main()
