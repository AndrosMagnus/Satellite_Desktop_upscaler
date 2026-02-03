import unittest

from app.stitching import RasterTile, stitch_tiles


class TestStitching(unittest.TestCase):
    def test_stitch_preserves_band_alignment(self) -> None:
        tile_left = RasterTile(
            bands=[
                [[1, 1], [1, 1]],
                [[10, 10], [10, 10]],
            ],
            transform=(0.0, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
            band_names=["B1", "B2"],
        )
        tile_right = RasterTile(
            bands=[
                [[2, 2], [2, 2]],
                [[20, 20], [20, 20]],
            ],
            transform=(2.0, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
            band_names=["B1", "B2"],
        )

        stitched = stitch_tiles([tile_left, tile_right])

        self.assertEqual(stitched.transform, (0.0, 0.0, 1.0, 1.0))
        self.assertEqual(
            stitched.bands[0],
            [[1, 1, 2, 2], [1, 1, 2, 2]],
        )
        self.assertEqual(
            stitched.bands[1],
            [[10, 10, 20, 20], [10, 10, 20, 20]],
        )

    def test_stitch_preserves_metadata(self) -> None:
        tile_top = RasterTile(
            bands=[[[5, 5], [5, 5]]],
            transform=(0.0, 0.0, 1.0, 1.0),
            crs="EPSG:3857",
            band_names=["NIR"],
            nodata=-9999.0,
        )
        tile_bottom = RasterTile(
            bands=[[[6, 6], [6, 6]]],
            transform=(0.0, 2.0, 1.0, 1.0),
            crs="EPSG:3857",
            band_names=["NIR"],
            nodata=-9999.0,
        )

        stitched = stitch_tiles([tile_top, tile_bottom])

        self.assertEqual(stitched.crs, "EPSG:3857")
        self.assertEqual(stitched.band_names, ["NIR"])
        self.assertEqual(stitched.nodata, -9999.0)
        self.assertEqual(stitched.bands[0], [[5, 5], [5, 5], [6, 6], [6, 6]])

    def test_rejects_mismatched_band_count(self) -> None:
        tile_one = RasterTile(
            bands=[[[1]]],
            transform=(0.0, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
        )
        tile_two = RasterTile(
            bands=[[[2]], [[3]]],
            transform=(1.0, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
        )

        with self.assertRaises(ValueError):
            stitch_tiles([tile_one, tile_two])

    def test_rejects_misaligned_offsets(self) -> None:
        tile_one = RasterTile(
            bands=[[[1, 1], [1, 1]]],
            transform=(0.0, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
        )
        tile_two = RasterTile(
            bands=[[[2, 2], [2, 2]]],
            transform=(1.5, 0.0, 1.0, 1.0),
            crs="EPSG:4326",
        )

        with self.assertRaises(ValueError):
            stitch_tiles([tile_one, tile_two])


if __name__ == "__main__":
    unittest.main()
