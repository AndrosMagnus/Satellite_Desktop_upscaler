import os
import tempfile
import unittest

try:
    from PySide6 import QtCore, QtGui, QtWidgets

    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is required for UI preview tests")
class TestPreviewAndMetadata(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication([])

    def test_preview_and_metadata_update_on_selection(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = os.path.join(tmpdir, "sample.png")
            image = QtGui.QImage(24, 18, QtGui.QImage.Format.Format_ARGB32)
            image.fill(QtGui.QColor("#ff0000"))
            self.assertTrue(image.save(image_path))

            window.input_list.add_paths([image_path])
            self._select_input_path(window, image_path)
            QtWidgets.QApplication.processEvents()

            pixmap = window.comparison_viewer.side_by_side.before_viewer.pixmap()
            self.assertIsNotNone(pixmap)
            self.assertFalse(pixmap.isNull())

            metadata_values = window.metadata_value_labels
            self.assertEqual(metadata_values["Filename"].text(), "sample.png")
            self.assertEqual(metadata_values["Format"].text(), "PNG")
            self.assertEqual(metadata_values["Dimensions"].text(), "24 x 18 px")
            self.assertIn("Band count", metadata_values)
            self.assertIn("CRS", metadata_values)
            self.assertIn("Acquisition time", metadata_values)
            self.assertIn("Scene ID", metadata_values)
            self.assertTrue(metadata_values["Provider"].text())
            self.assertIn("B", metadata_values["File size"].text())
            self.assertTrue(metadata_values["Modified"].text())

    def test_non_image_shows_placeholder_metadata(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        with tempfile.TemporaryDirectory() as tmpdir:
            text_path = os.path.join(tmpdir, "notes.txt")
            with open(text_path, "w", encoding="utf-8") as handle:
                handle.write("hello")

            window.input_list.add_paths([text_path])
            self._select_input_path(window, text_path)
            QtWidgets.QApplication.processEvents()

            self.assertEqual(window.metadata_value_labels["Format"].text(), "Not an image")
            self.assertEqual(window.metadata_value_labels["Dimensions"].text(), "Unknown")
            self.assertIn("notes.txt", window.metadata_summary.text())

    def test_header_only_image_still_reports_metadata(self) -> None:
        from app.ui import MainWindow

        window = MainWindow()
        with tempfile.TemporaryDirectory() as tmpdir:
            header_path = os.path.join(tmpdir, "header_only.png")
            width, height = 10, 6
            png_header = (
                b"\x89PNG\r\n\x1a\n"
                b"\x00\x00\x00\x0d"
                b"IHDR"
                + width.to_bytes(4, "big")
                + height.to_bytes(4, "big")
                + b"\x08\x02\x00\x00\x00"
                + b"\x00\x00\x00\x00"
            )
            with open(header_path, "wb") as handle:
                handle.write(png_header)

            window.input_list.add_paths([header_path])
            self._select_input_path(window, header_path)
            QtWidgets.QApplication.processEvents()

            self.assertEqual(window.metadata_value_labels["Format"].text(), "PNG")
            self.assertEqual(window.metadata_value_labels["Dimensions"].text(), "10 x 6 px")

    def _select_input_path(self, window: "QtWidgets.QMainWindow", path: str) -> None:
        window.input_list.clearSelection()
        for index in range(window.input_list.count()):
            item = window.input_list.item(index)
            if item is None:
                continue
            if item.text() == path:
                item.setSelected(True)
                window.input_list.setCurrentRow(index)
                return
        self.fail(f"Expected input path not found in list: {path}")


if __name__ == "__main__":
    unittest.main()
