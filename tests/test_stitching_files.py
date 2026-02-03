import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import stitching


class TestRasterFileStitching(unittest.TestCase):
    def test_stitch_rasters_uses_rasterio(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out.tif"
            with mock.patch(
                "app.stitching._stitch_with_rasterio", return_value=str(output)
            ) as rasterio_mock:
                with mock.patch("app.stitching._stitch_with_gdal") as gdal_mock:
                    result = stitching.stitch_rasters(["a.tif"], str(output))

        self.assertEqual(result, str(output))
        rasterio_mock.assert_called_once()
        gdal_mock.assert_not_called()

    def test_stitch_rasters_falls_back_to_gdal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out.tif"
            with mock.patch(
                "app.stitching._stitch_with_rasterio", side_effect=RuntimeError("boom")
            ) as rasterio_mock:
                with mock.patch(
                    "app.stitching._stitch_with_gdal", return_value=str(output)
                ) as gdal_mock:
                    result = stitching.stitch_rasters(["a.tif"], str(output))

        self.assertEqual(result, str(output))
        rasterio_mock.assert_called_once()
        gdal_mock.assert_called_once()

    def test_stitch_rasters_rejects_empty_inputs(self) -> None:
        with self.assertRaises(ValueError):
            stitching.stitch_rasters([], "out.tif")

    def test_gdal_cli_invocation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out.tif"
            inputs = [str(Path(temp_dir) / "a.tif"), str(Path(temp_dir) / "b.tif")]
            calls: list[list[str]] = []

            def fake_run(command, check, capture_output, text):
                calls.append(command)
                return subprocess.CompletedProcess(command, 0, "", "")

            with mock.patch("app.stitching.subprocess.run", side_effect=fake_run):
                result = stitching._stitch_with_gdal(inputs, str(output), RuntimeError("r"))

        self.assertEqual(result, str(output))
        self.assertEqual(calls[0][0], "gdalbuildvrt")
        self.assertEqual(calls[1][0], "gdal_translate")


if __name__ == "__main__":
    unittest.main()
