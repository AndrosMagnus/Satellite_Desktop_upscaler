from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.band_handling import BandHandling
from app.imagery_policy import OutputPlan
from app.upscale_execution import (
    RunCancelledError,
    UpscaleRequest,
    expand_input_paths,
    run_upscale_batch,
    run_upscale_request,
)


try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class TestUpscaleExecutionHelpers(unittest.TestCase):
    def test_expand_input_paths_includes_supported_directory_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            keep = root / "scene.tif"
            skip = root / "notes.txt"
            keep.write_bytes(b"data")
            skip.write_text("ignore", encoding="utf-8")

            expanded = expand_input_paths([root])

        self.assertEqual(expanded, [keep.resolve()])

    def test_geospatial_request_falls_back_to_file_copy_for_unreadable_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "invalid.bin"
            input_path.write_bytes(b"not-an-image")
            request = UpscaleRequest(
                input_path=input_path,
                output_plan=OutputPlan(
                    master_format="GeoTIFF",
                    visual_format=None,
                    critical_warnings=(),
                ),
                scale=2,
                band_handling=BandHandling.ALL_BANDS,
            )

            artifact = run_upscale_request(request, output_dir=root / "out")

            self.assertTrue(artifact.master_output_path.exists())
            self.assertEqual(artifact.master_output_path.read_bytes(), b"not-an-image")
            self.assertTrue(artifact.notes)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required for visual upscale test")
    def test_visual_upscale_request_writes_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "input.png"
            Image.new("RGB", (6, 4), color=(10, 20, 30)).save(input_path)
            request = UpscaleRequest(
                input_path=input_path,
                output_plan=OutputPlan(
                    master_format="PNG",
                    visual_format=None,
                    critical_warnings=(),
                ),
                scale=2,
                band_handling=BandHandling.RGB_ONLY,
            )

            artifact = run_upscale_request(request, output_dir=root / "out")

            self.assertTrue(artifact.master_output_path.exists())
            with Image.open(artifact.master_output_path) as image:
                self.assertEqual(image.size, (12, 8))

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required for tagged output test")
    def test_output_tag_suffix_is_added_to_output_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            input_path = root / "input.png"
            Image.new("RGB", (4, 4), color=(0, 0, 0)).save(input_path)
            request = UpscaleRequest(
                input_path=input_path,
                output_plan=OutputPlan("PNG", None, ()),
                scale=2,
                band_handling=BandHandling.RGB_ONLY,
                output_tag="Model A",
            )

            artifact = run_upscale_request(request, output_dir=root / "out")

            self.assertIn("_model-a_master", artifact.master_output_path.name)

    @unittest.skipUnless(PIL_AVAILABLE, "Pillow is required for batch test")
    def test_batch_progress_callback_receives_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "a.png"
            second = root / "b.png"
            Image.new("RGB", (2, 2), color=(10, 10, 10)).save(first)
            Image.new("RGB", (2, 2), color=(20, 20, 20)).save(second)
            requests = [
                UpscaleRequest(
                    input_path=first,
                    output_plan=OutputPlan("PNG", None, ()),
                    scale=2,
                    band_handling=BandHandling.RGB_ONLY,
                ),
                UpscaleRequest(
                    input_path=second,
                    output_plan=OutputPlan("PNG", None, ()),
                    scale=2,
                    band_handling=BandHandling.RGB_ONLY,
                ),
            ]
            updates: list[tuple[int, int, Path]] = []

            artifacts = run_upscale_batch(
                requests,
                output_dir=root / "out",
                on_progress=lambda completed, total, path: updates.append(
                    (completed, total, path)
                ),
            )

            self.assertEqual(len(artifacts), 2)
            self.assertEqual(len(updates), 2)
            self.assertEqual(updates[0][0], 1)
            self.assertEqual(updates[1][0], 2)

    def test_batch_cancellation_discards_partial_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "a.tif"
            second = root / "b.tif"
            first.write_bytes(b"invalid-raster-a")
            second.write_bytes(b"invalid-raster-b")
            requests = [
                UpscaleRequest(
                    input_path=first,
                    output_plan=OutputPlan("GeoTIFF", None, ()),
                    scale=2,
                    band_handling=BandHandling.RGB_ONLY,
                ),
                UpscaleRequest(
                    input_path=second,
                    output_plan=OutputPlan("GeoTIFF", None, ()),
                    scale=2,
                    band_handling=BandHandling.RGB_ONLY,
                ),
            ]
            should_cancel = {"value": False}
            updates: list[tuple[int, int, Path]] = []

            def on_progress(completed: int, total: int, path: Path) -> None:
                updates.append((completed, total, path))
                should_cancel["value"] = True

            with self.assertRaises(RunCancelledError):
                run_upscale_batch(
                    requests,
                    output_dir=root / "out",
                    on_progress=on_progress,
                    should_cancel=lambda: should_cancel["value"],
                )

            outputs = sorted((root / "out").glob("*_master.tif"))
            self.assertEqual(len(outputs), 0)
            self.assertFalse((root / "out").exists())
            self.assertEqual(len(updates), 1)


if __name__ == "__main__":
    unittest.main()
