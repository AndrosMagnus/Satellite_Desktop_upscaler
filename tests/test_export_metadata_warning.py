import os
import unittest

try:
    from PySide6 import QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for export warning tests")
class TestExportMetadataWarning(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_warning_shown_for_metadata_loss(self) -> None:
        from app.ui import ExportPresetsPanel

        panel = ExportPresetsPanel()
        panel.show()
        panel.output_format_combo.setCurrentText("PNG")
        panel.set_input_format("GeoTIFF")
        QtWidgets.QApplication.processEvents()

        self.assertTrue(panel.metadata_warning_label.isVisible())
        self.assertIn("geospatial metadata", panel.metadata_warning_label.text())

    def test_warning_hidden_for_geotiff_output(self) -> None:
        from app.ui import ExportPresetsPanel

        panel = ExportPresetsPanel()
        panel.show()
        panel.output_format_combo.setCurrentText("GeoTIFF")
        panel.set_input_format("GeoTIFF")
        QtWidgets.QApplication.processEvents()

        self.assertFalse(panel.metadata_warning_label.isVisible())


if __name__ == "__main__":
    unittest.main()
