from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from backend import main as backend_main


class TestBackendMainCLI(unittest.TestCase):
    def test_list_models(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = backend_main.main(["--list-models"])
        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("Real-ESRGAN", output)
        self.assertIn("Satlas", output)

    def test_requires_input_when_not_listing_models(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            code = backend_main.main([])
        self.assertEqual(code, 2)
        self.assertIn("--input is required", stderr.getvalue())

    def test_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "scene.tif"
            input_path.write_bytes(b"fake-raster")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = backend_main.main(["--input", str(input_path), "--dry-run"])
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("Dry run:", text)
        self.assertIn("scene.tif", text)
        self.assertIn("model=", text)

    def test_dry_run_safe_mode_forces_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "scene.tif"
            input_path.write_bytes(b"fake-raster")
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = backend_main.main(
                    ["--input", str(input_path), "--dry-run", "--safe-mode"]
                )
        self.assertEqual(code, 0)
        text = stdout.getvalue()
        self.assertIn("compute=CPU", text)

    def test_dry_run_with_stitch_uses_single_mosaic_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_a = Path(tmpdir) / "a.tif"
            input_b = Path(tmpdir) / "b.tif"
            input_a.write_bytes(b"fake-a")
            input_b.write_bytes(b"fake-b")

            def _fake_stitch(paths: list[str], output_path: str, **_kwargs: object) -> str:
                self.assertEqual(len(paths), 2)
                Path(output_path).write_bytes(b"stitched")
                return output_path

            stdout = io.StringIO()
            with mock.patch("backend.main.stitch_rasters", side_effect=_fake_stitch) as stitch:
                with redirect_stdout(stdout):
                    code = backend_main.main(
                        [
                            "--input",
                            str(input_a),
                            "--input",
                            str(input_b),
                            "--dry-run",
                            "--stitch",
                        ]
                    )

        self.assertEqual(code, 0)
        self.assertTrue(stitch.called)
        text = stdout.getvalue()
        self.assertIn("Dry run: 1 input(s)", text)
        self.assertIn("Stitched 2 input files into one mosaic.", text)

    def test_stitch_requires_multiple_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "scene.tif"
            input_path.write_bytes(b"fake-raster")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = backend_main.main(
                    [
                        "--input",
                        str(input_path),
                        "--stitch",
                    ]
                )

        self.assertEqual(code, 2)
        self.assertIn("at least two input tiles", stderr.getvalue())

    def test_run_writes_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "scene.tif"
            output_dir = Path(tmpdir) / "out"
            input_path.write_bytes(b"fake-raster")
            code = backend_main.main(
                [
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--scale",
                    "2",
                ]
            )
            self.assertEqual(code, 0)
            outputs = list(output_dir.glob("scene_x2_master.tif"))
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].read_bytes(), b"fake-raster")

    def test_unknown_model_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = Path(tmpdir) / "scene.tif"
            input_path.write_bytes(b"fake-raster")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = backend_main.main(
                    [
                        "--input",
                        str(input_path),
                        "--model",
                        "MissingModel",
                    ]
                )
        self.assertEqual(code, 2)
        self.assertIn("Unknown model", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
