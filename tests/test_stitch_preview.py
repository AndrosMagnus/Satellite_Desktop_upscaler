import unittest

from app.mosaic_detection import preview_stitch_bounds


class TestStitchPreview(unittest.TestCase):
    def test_preview_from_bbox_tiles(self) -> None:
        paths = [
            "/tmp/scene_x0_y0_w10_h10.tif",
            "/tmp/scene_x10_y0_w10_h10.tif",
            "/tmp/scene_x0_y10_w10_h10.tif",
        ]

        preview = preview_stitch_bounds(paths)

        self.assertIsNotNone(preview)
        assert preview is not None
        self.assertEqual(
            preview.extent,
            "x=0..20, y=0..20 (width=20, height=20)",
        )
        self.assertEqual(
            preview.boundaries,
            "x=0, 10, 20; y=0, 10, 20",
        )


if __name__ == "__main__":
    unittest.main()
