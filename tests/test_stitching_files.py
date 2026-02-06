import subprocess
import sys
import tempfile
import types
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

    def test_stitch_rasters_rejects_reprojection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "out.tif"
            with mock.patch(
                "app.stitching._stitch_with_rasterio",
                side_effect=stitching.ReprojectionNotSupportedError("no reprojection"),
            ) as rasterio_mock:
                with mock.patch("app.stitching._stitch_with_gdal") as gdal_mock:
                    with self.assertRaises(stitching.ReprojectionNotSupportedError):
                        stitching.stitch_rasters(["a.tif"], str(output))

        rasterio_mock.assert_called_once()
        gdal_mock.assert_not_called()

    def test_stitch_rasters_rejects_empty_inputs(self) -> None:
        with self.assertRaises(ValueError):
            stitching.stitch_rasters([], "out.tif")

    def test_rasterio_rejects_mismatched_crs(self) -> None:
        fake_rasterio = types.ModuleType("rasterio")
        fake_merge = types.ModuleType("rasterio.merge")

        class FakeDataset:
            def __init__(self, crs):
                self.crs = crs

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def fake_open(path):
            crs = "EPSG:4326" if "a" in path else "EPSG:3857"
            return FakeDataset(crs)

        def fake_merge_call(_datasets):
            raise AssertionError("merge should not be called when CRS mismatches")

        fake_rasterio.open = fake_open
        fake_merge.merge = fake_merge_call

        with mock.patch.dict(sys.modules, {"rasterio": fake_rasterio, "rasterio.merge": fake_merge}):
            with self.assertRaises(stitching.ReprojectionNotSupportedError):
                stitching._stitch_with_rasterio(["a.tif", "b.tif"], "out.tif")

    def test_rasterio_rejects_mismatched_band_descriptions(self) -> None:
        fake_rasterio = types.ModuleType("rasterio")
        fake_merge = types.ModuleType("rasterio.merge")

        class FakeDataset:
            def __init__(self, crs, descriptions):
                self.crs = crs
                self.count = 2
                self.descriptions = descriptions
                self.nodata = None
                self.meta = {
                    "driver": "GTiff",
                    "dtype": "uint8",
                    "count": 2,
                    "crs": crs,
                    "transform": "t",
                }

            def tags(self, **_kwargs):
                return {}

            def tag_namespaces(self, **_kwargs):
                return ()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        datasets = {
            "a.tif": FakeDataset("EPSG:4326", ("B1", "B2")),
            "b.tif": FakeDataset("EPSG:4326", ("B2", "B1")),
        }

        def fake_open(path, *args, **kwargs):
            return datasets[path]

        def fake_merge_call(_datasets):
            raise AssertionError("merge should not be called when band descriptions mismatch")

        fake_rasterio.open = fake_open
        fake_merge.merge = fake_merge_call

        with mock.patch.dict(sys.modules, {"rasterio": fake_rasterio, "rasterio.merge": fake_merge}):
            with self.assertRaises(ValueError):
                stitching._stitch_with_rasterio(["a.tif", "b.tif"], "out.tif")

    def test_rasterio_preserves_band_descriptions_and_nodata(self) -> None:
        fake_rasterio = types.ModuleType("rasterio")
        fake_merge = types.ModuleType("rasterio.merge")
        writer_holder: dict[str, object] = {}

        class FakeDataset:
            def __init__(self, crs, descriptions, nodata):
                self.crs = crs
                self.count = 2
                self.descriptions = descriptions
                self.nodata = nodata
                self.meta = {
                    "driver": "GTiff",
                    "dtype": "uint8",
                    "count": 2,
                    "crs": crs,
                    "transform": "t",
                }

            def tags(self, **_kwargs):
                return {}

            def tag_namespaces(self, **_kwargs):
                return ()

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeWriter:
            def __init__(self, meta):
                self.meta = meta
                self.descriptions = None
                self.written = None

            def write(self, mosaic):
                self.written = mosaic

            def update_tags(self, **_kwargs):
                return None

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        datasets = {
            "a.tif": FakeDataset("EPSG:4326", (None, None), None),
            "b.tif": FakeDataset("EPSG:4326", ("B1", "B2"), -9999.0),
        }

        def fake_open(path, mode="r", **kwargs):
            if mode == "w":
                writer = FakeWriter(kwargs)
                writer_holder["writer"] = writer
                return writer
            return datasets[path]

        class FakeMosaic:
            def __init__(self):
                self.shape = (2, 2, 2)

        def fake_merge_call(_datasets):
            return FakeMosaic(), "transform"

        fake_rasterio.open = fake_open
        fake_merge.merge = fake_merge_call

        with mock.patch.dict(sys.modules, {"rasterio": fake_rasterio, "rasterio.merge": fake_merge}):
            stitching._stitch_with_rasterio(["a.tif", "b.tif"], "out.tif")

        writer = writer_holder["writer"]
        self.assertEqual(writer.meta["nodata"], -9999.0)
        self.assertEqual(writer.descriptions, ("B1", "B2"))

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
