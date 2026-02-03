import unittest

from app.mosaic_detection import suggest_mosaic


class TestMosaicDetection(unittest.TestCase):
    def test_detects_adjacent_grid_tiles(self) -> None:
        suggestion = suggest_mosaic(
            [
                "/tmp/scene_r0_c0.tif",
                "/tmp/scene_r0_c1.tif",
            ]
        )
        self.assertTrue(suggestion.is_mosaic)
        self.assertTrue(suggestion.has_adjacent)
        self.assertFalse(suggestion.has_overlap)
        self.assertIsNotNone(suggestion.message)

    def test_detects_overlapping_grid_tiles(self) -> None:
        suggestion = suggest_mosaic(
            [
                "/tmp/scene_r2_c3.tif",
                "/tmp/scene_r2_c3_copy.tif",
            ]
        )
        self.assertTrue(suggestion.is_mosaic)
        self.assertTrue(suggestion.has_overlap)
        self.assertFalse(suggestion.has_adjacent)

    def test_detects_bbox_adjacency(self) -> None:
        suggestion = suggest_mosaic(
            [
                "/tmp/tile_x0_y0_w100_h100.tif",
                "/tmp/tile_x100_y0_w100_h100.tif",
            ]
        )
        self.assertTrue(suggestion.is_mosaic)
        self.assertTrue(suggestion.has_adjacent)
        self.assertFalse(suggestion.has_overlap)

    def test_detects_bbox_overlap(self) -> None:
        suggestion = suggest_mosaic(
            [
                "/tmp/tile_x0_y0_w100_h100.tif",
                "/tmp/tile_x50_y0_w100_h100.tif",
            ]
        )
        self.assertTrue(suggestion.is_mosaic)
        self.assertTrue(suggestion.has_overlap)
        self.assertFalse(suggestion.has_adjacent)

    def test_no_mosaic_for_unmatched_names(self) -> None:
        suggestion = suggest_mosaic(
            [
                "/tmp/alpha.tif",
                "/tmp/beta.tif",
            ]
        )
        self.assertFalse(suggestion.is_mosaic)
        self.assertIsNone(suggestion.message)


if __name__ == "__main__":
    unittest.main()
