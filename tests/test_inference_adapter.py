import os
import tempfile
import unittest
from pathlib import Path

from app.inference_adapter import InferenceAdapter, InferenceRequest
from app.model_wrapper import ModelWrapper


class TestInferenceAdapter(unittest.TestCase):
    def _create_wrapper(self, base_dir: Path) -> ModelWrapper:
        model_dir = base_dir / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        weights_path = model_dir / "weights.bin"
        weights_path.write_bytes(b"weights")

        venv_dir = model_dir / "venv"
        venv_dir.mkdir(parents=True, exist_ok=True)
        (venv_dir / "pyvenv.cfg").write_text("home=/usr/bin/python3\n", encoding="utf-8")
        bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
        bin_dir.mkdir(parents=True, exist_ok=True)
        python_name = "python.exe" if os.name == "nt" else "python"
        (bin_dir / python_name).write_text("", encoding="utf-8")

        return ModelWrapper(
            name="Test Model",
            version="v1",
            weights_path=weights_path,
            venv_dir=venv_dir,
            entrypoint="model_runner",
        )

    def test_build_command_includes_options(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapper = self._create_wrapper(Path(tmpdir))
            request = InferenceRequest(
                input_path=Path(tmpdir) / "input.tif",
                output_path=Path(tmpdir) / "out" / "output.tif",
                scale=4,
                tiling="auto",
                precision="fp16",
                compute="gpu",
                extra_args=("--foo", "bar"),
            )

            adapter = InferenceAdapter()
            cmd = adapter.build_command(wrapper, request)

            self.assertIn("-m", cmd)
            self.assertIn("model_runner", cmd)
            self.assertIn("--weights", cmd)
            self.assertIn(str(wrapper.weights_path), cmd)
            self.assertIn("--input", cmd)
            self.assertIn(str(request.input_path), cmd)
            self.assertIn("--output", cmd)
            self.assertIn(str(request.output_path), cmd)
            self.assertIn("--scale", cmd)
            self.assertIn("4", cmd)
            self.assertIn("--tiling", cmd)
            self.assertIn("auto", cmd)
            self.assertIn("--precision", cmd)
            self.assertIn("fp16", cmd)
            self.assertIn("--compute", cmd)
            self.assertIn("gpu", cmd)
            self.assertIn("--foo", cmd)
            self.assertIn("bar", cmd)

    def test_run_uses_entrypoint_script_and_merges_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            wrapper = self._create_wrapper(base_dir)
            script_path = wrapper.model_dir / "run_inference.py"
            script_path.write_text("", encoding="utf-8")
            wrapper = ModelWrapper(
                name=wrapper.name,
                version=wrapper.version,
                weights_path=wrapper.weights_path,
                venv_dir=wrapper.venv_dir,
                entrypoint="run_inference.py",
                extra_env={"MODEL_ENV": "1"},
            )

            input_path = base_dir / "input.tif"
            input_path.write_text("", encoding="utf-8")
            output_path = base_dir / "outputs" / "out.tif"

            captured: dict[str, object] = {}

            def runner(cmd: list[str], env: dict[str, str] | None) -> None:
                captured["cmd"] = cmd
                captured["env"] = env

            adapter = InferenceAdapter(runner=runner)
            adapter.run(
                wrapper,
                InferenceRequest(input_path=input_path, output_path=output_path),
                extra_env={"EXTRA_ENV": "2"},
            )

            cmd = captured.get("cmd")
            env = captured.get("env")
            self.assertIsInstance(cmd, list)
            self.assertIsInstance(env, dict)
            self.assertEqual(cmd[0], str(wrapper.python_executable))
            self.assertEqual(cmd[1], str(script_path))
            self.assertIn("MODEL_ENV", env)
            self.assertEqual(env["MODEL_ENV"], "1")
            self.assertIn("EXTRA_ENV", env)
            self.assertEqual(env["EXTRA_ENV"], "2")
            self.assertTrue(output_path.parent.exists())


if __name__ == "__main__":
    unittest.main()
