import unittest
from pathlib import Path

from app.dataset_analysis import (
    DatasetInfo,
    GridSignature,
    group_by_grid,
    infer_acquisition_time,
    infer_scene_id,
    summarize_grid_groups,
)


class TestDatasetAnalysisHelpers(unittest.TestCase):
    def test_infer_acquisition_time_prefers_tag_value(self) -> None:
        acquisition_time = infer_acquisition_time(
            Path("scene.tif"),
            tags={"TIFFTAG_DATETIME": "2024:03:11 15:23:41"},
        )
        self.assertEqual(acquisition_time, "2024-03-11T15:23:41")

    def test_infer_acquisition_time_from_filename(self) -> None:
        acquisition_time = infer_acquisition_time(
            Path("S2A_MSIL2A_20240201T104031_N0509_R008_T31TCJ_20240201T130924.tif")
        )
        self.assertEqual(acquisition_time, "2024-02-01T10:40:31")

    def test_infer_scene_id_prefers_tag_value(self) -> None:
        scene_id = infer_scene_id(
            Path("landsat_scene.tif"),
            provider="Landsat",
            tags={
                "LANDSAT_PRODUCT_ID": "LC08_L2SP_023030_20240101_20240109_02_T1",
            },
        )
        self.assertEqual(scene_id, "LC08_L2SP_023030_20240101_20240109_02_T1")

    def test_infer_scene_id_from_filename_removes_band_suffix(self) -> None:
        scene_id = infer_scene_id(
            Path(
                "S2A_MSIL2A_20240201T104031_N0509_R008_T31TCJ_20240201T130924_B04.jp2"
            ),
            provider="Sentinel-2",
        )
        self.assertEqual(
            scene_id,
            "S2A_MSIL2A_20240201T104031_N0509_R008_T31TCJ_20240201T130924",
        )

    def test_preservation_gaps_for_geospatial_inputs(self) -> None:
        info = DatasetInfo(
            path=Path("scene.tif"),
            provider="Sentinel-2",
            sensor="MSI-L2A",
            format_label="GeoTIFF",
            band_count=13,
            grid=None,
            dtype=None,
            nodata=None,
            scales=None,
            offsets=None,
            band_names=None,
        )
        gaps = info.preservation_gaps()
        self.assertIn("CRS", gaps)
        self.assertIn("geotransform", gaps)
        self.assertIn("dtype", gaps)

    def test_group_by_grid(self) -> None:
        grid_a = GridSignature(
            crs="EPSG:4326",
            transform=(1.0, 0.0, 0.0, 0.0, -1.0, 0.0),
            width=100,
            height=100,
        )
        grid_b = GridSignature(
            crs="EPSG:3857",
            transform=(10.0, 0.0, 0.0, 0.0, -10.0, 0.0),
            width=50,
            height=50,
        )
        info_a = DatasetInfo(
            path=Path("a.tif"),
            provider=None,
            sensor=None,
            format_label="GeoTIFF",
            band_count=3,
            grid=grid_a,
            dtype="uint16",
            nodata=None,
            scales=(1.0, 1.0, 1.0),
            offsets=(0.0, 0.0, 0.0),
            band_names=None,
        )
        info_b = DatasetInfo(
            path=Path("b.tif"),
            provider=None,
            sensor=None,
            format_label="GeoTIFF",
            band_count=3,
            grid=grid_b,
            dtype="uint16",
            nodata=None,
            scales=(1.0, 1.0, 1.0),
            offsets=(0.0, 0.0, 0.0),
            band_names=None,
        )
        info_c = DatasetInfo(
            path=Path("c.tif"),
            provider=None,
            sensor=None,
            format_label="GeoTIFF",
            band_count=3,
            grid=grid_a,
            dtype="uint16",
            nodata=None,
            scales=(1.0, 1.0, 1.0),
            offsets=(0.0, 0.0, 0.0),
            band_names=None,
        )
        grouped = group_by_grid([info_a, info_b, info_c])
        self.assertEqual(len(grouped), 2)
        summary = summarize_grid_groups(grouped)
        self.assertIn("Group 1:", summary)
        self.assertIn("files=2", summary)


if __name__ == "__main__":
    unittest.main()
