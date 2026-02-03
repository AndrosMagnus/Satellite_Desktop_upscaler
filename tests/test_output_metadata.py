import unittest

from app.output_metadata import format_preserves_metadata, metadata_loss_warning


class TestOutputMetadata(unittest.TestCase):
    def test_formats_that_preserve_metadata(self) -> None:
        self.assertTrue(format_preserves_metadata("GeoTIFF"))
        self.assertTrue(format_preserves_metadata("TIF"))
        self.assertTrue(format_preserves_metadata("JP2"))
        self.assertFalse(format_preserves_metadata("PNG"))
        self.assertFalse(format_preserves_metadata("Not an image"))

    def test_metadata_loss_warning_for_geospatial_to_lossy(self) -> None:
        warning = metadata_loss_warning("GeoTIFF", "PNG")
        self.assertIsNotNone(warning)
        self.assertIn("Warning", warning)
        self.assertIn("geospatial metadata", warning)

    def test_metadata_loss_warning_not_shown_for_match_input(self) -> None:
        warning = metadata_loss_warning("GeoTIFF", "Match input")
        self.assertIsNone(warning)

    def test_metadata_loss_warning_not_shown_for_non_geospatial(self) -> None:
        warning = metadata_loss_warning("PNG", "JPEG")
        self.assertIsNone(warning)


if __name__ == "__main__":
    unittest.main()
